from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.reconciliation.engine import (
    rule_amount_mismatch,
    rule_channel_standardization,
    rule_duplicate_order,
    rule_missing_payment,
    rule_missing_stock_out,
    rule_negative_stock,
    rule_orphan_payment,
    run_reconciliation,
)


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def _orders(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _payments(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _stock(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


BASE_ORDER = {
    "order_id": "ORD-1",
    "order_date": _dt("2026-06-01T10:00:00+00:00"),
    "customer_name": "Ana Silva",
    "channel": "Shopify",
    "sku": "SKU-A",
    "product_name": "Produto A",
    "quantity": 1,
    "unit_price": 100.0,
    "gross_amount": 100.0,
    "discount_amount": 0.0,
    "net_amount": 100.0,
    "status": "paid",
}


def test_missing_payment():
    orders = _orders([{**BASE_ORDER}])
    payments = _payments([])
    issues = rule_missing_payment(orders, payments)
    assert len(issues) == 1
    assert issues[0].issue_type == "missing_payment"
    assert issues[0].severity == "high"
    assert issues[0].amount_impact == 100.0


def test_orphan_payment():
    orders = _orders([])
    payments = _payments(
        [
            {
                "payment_id": "PAY-1",
                "order_id": "ORD-X",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 50.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    issues = rule_orphan_payment(orders, payments)
    assert len(issues) == 1
    assert issues[0].issue_type == "orphan_payment"
    assert issues[0].severity == "high"


def test_amount_mismatch():
    orders = _orders([{**BASE_ORDER, "net_amount": 100.0}])
    payments = _payments(
        [
            {
                "payment_id": "PAY-1",
                "order_id": "ORD-1",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 70.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    issues = rule_amount_mismatch(orders, payments)
    assert len(issues) == 1
    assert issues[0].issue_type == "amount_mismatch"
    assert issues[0].severity == "high"
    assert abs(issues[0].amount_impact - 30.0) < 0.01


def test_duplicate_order():
    orders = _orders(
        [
            {**BASE_ORDER},
            {**BASE_ORDER, "sku": "SKU-B", "product_name": "Produto B", "net_amount": 80.0},
        ]
    )
    issues = rule_duplicate_order(orders)
    assert len(issues) == 1
    assert issues[0].issue_type == "duplicate_order"
    assert issues[0].severity == "high"


def test_missing_stock_out():
    orders = _orders([{**BASE_ORDER, "status": "shipped"}])
    stock = _stock([])
    issues = rule_missing_stock_out(orders, stock)
    assert len(issues) == 1
    assert issues[0].issue_type == "missing_stock_out"
    assert issues[0].severity == "medium"


def test_negative_stock():
    stock = _stock(
        [
            {
                "movement_id": "M1",
                "sku": "SKU-A",
                "movement_type": "in",
                "quantity": 5,
                "movement_date": _dt("2026-06-01T08:00:00+00:00"),
                "reference_order_id": None,
            },
            {
                "movement_id": "M2",
                "sku": "SKU-A",
                "movement_type": "out",
                "quantity": 8,
                "movement_date": _dt("2026-06-01T09:00:00+00:00"),
                "reference_order_id": "ORD-1",
            },
        ]
    )
    issues = rule_negative_stock(stock)
    assert len(issues) == 1
    assert issues[0].issue_type == "negative_stock"
    assert issues[0].severity == "critical"


def test_channel_standardization():
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "channel": "whatsapp"},
            {**BASE_ORDER, "order_id": "ORD-2", "channel": "zap"},
            {**BASE_ORDER, "order_id": "ORD-3", "channel": "WhatsApp"},
        ]
    )
    issues = rule_channel_standardization(orders)
    assert any(i.issue_type == "channel_standardization" for i in issues)
    assert all(i.severity == "low" for i in issues if i.issue_type == "channel_standardization")


def test_batch_without_critical_issues():
    orders = _orders(
        [
            {
                **BASE_ORDER,
                "order_id": "ORD-OK",
                "status": "paid",
                "channel": "Shopify",
                "net_amount": 100.0,
            }
        ]
    )
    payments = _payments(
        [
            {
                "payment_id": "PAY-OK",
                "order_id": "ORD-OK",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 100.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    stock = _stock(
        [
            {
                "movement_id": "M-IN",
                "sku": "SKU-A",
                "movement_type": "in",
                "quantity": 10,
                "movement_date": _dt("2026-05-31T08:00:00+00:00"),
                "reference_order_id": None,
            },
            {
                "movement_id": "M-OUT",
                "sku": "SKU-A",
                "movement_type": "out",
                "quantity": 1,
                "movement_date": _dt("2026-06-01T12:00:00+00:00"),
                "reference_order_id": "ORD-OK",
            },
        ]
    )
    issues = run_reconciliation(orders, payments, stock)
    assert not any(i.severity == "critical" for i in issues)
    assert not any(i.issue_type in {"missing_payment", "orphan_payment", "amount_mismatch"} for i in issues)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Avoid app lifespan touching the real SQLite file
    monkeypatch.setattr("app.main.init_db", lambda: None)

    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    orders = pd.DataFrame(
        [
            {
                **{k: v for k, v in BASE_ORDER.items() if k != "order_date"},
                "order_id": "ORD-DEMO",
                "order_date": "2026-06-01T10:00:00+00:00",
                "customer_document_optional": "",
                "status": "paid",
                "channel": "Shopify",
            }
        ]
    )
    payments = pd.DataFrame(
        [
            {
                "payment_id": "PAY-DEMO",
                "order_id": "ORD-DEMO",
                "paid_at": "2026-06-01T11:00:00+00:00",
                "amount": 100.0,
                "method": "pix",
                "status": "paid",
                "transaction_reference": "TX-1",
            }
        ]
    )
    stock = pd.DataFrame(
        [
            {
                "movement_id": "M1",
                "sku": "SKU-A",
                "movement_type": "in",
                "quantity": 5,
                "movement_date": "2026-05-31T08:00:00+00:00",
                "reference_order_id": "",
                "notes": "",
            },
            {
                "movement_id": "M2",
                "sku": "SKU-A",
                "movement_type": "out",
                "quantity": 1,
                "movement_date": "2026-06-01T12:00:00+00:00",
                "reference_order_id": "ORD-DEMO",
                "notes": "",
            },
        ]
    )
    orders.to_csv(demo_dir / "orders.csv", index=False)
    payments.to_csv(demo_dir / "payments.csv", index=False)
    stock.to_csv(demo_dir / "stock_movements.csv", index=False)

    from app.core.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_dir", demo_dir)
    monkeypatch.setattr(settings, "processed_dir", tmp_path / "processed")
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path.as_posix()}")
    (tmp_path / "processed").mkdir()

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_demo_endpoint(client):
    res = client.post("/api/demo/run")
    assert res.status_code == 200
    body = res.json()
    assert body["batch"]["status"] == "completed"
    assert body["batch"]["total_orders"] == 1
    assert "orders" in body


def test_dashboard_resolve_recalculates_open_amounts(client, tmp_path):
    """Upload a batch with missing_payment, resolve it, assert open KPIs drop."""
    orders = (
        "order_id,order_date,customer_name,customer_document_optional,channel,sku,product_name,"
        "quantity,unit_price,gross_amount,discount_amount,net_amount,status\n"
        "ORD-X,2026-06-01T10:00:00+00:00,Cliente X,,Shopify,SKU-A,Item,1,100,100,0,100,paid\n"
    )
    payments = (
        "payment_id,order_id,paid_at,amount,method,status,transaction_reference\n"
        "PAY-FAIL,ORD-X,2026-06-01T11:00:00+00:00,100,pix,failed,TX-FAIL\n"
    )
    stock = (
        "movement_id,sku,movement_type,quantity,movement_date,reference_order_id,notes\n"
        "M1,SKU-A,in,5,2026-05-31T08:00:00+00:00,,\n"
        "M2,SKU-A,out,1,2026-06-01T12:00:00+00:00,ORD-X,\n"
    )
    files = {
        "orders": ("orders.csv", orders, "text/csv"),
        "payments": ("payments.csv", payments, "text/csv"),
        "stock_movements": ("stock.csv", stock, "text/csv"),
    }
    uploaded = client.post("/api/imports", files=files)
    assert uploaded.status_code == 200, uploaded.text
    batch_id = uploaded.json()["batch"]["id"]
    assert uploaded.json()["batch"]["total_issues"] >= 1

    dash = client.get(f"/api/imports/{batch_id}/dashboard")
    assert dash.status_code == 200
    body = dash.json()
    assert body["open_issues_count"] >= 1
    assert body["unreconciled_amount"] > 0

    issues = client.get(f"/api/imports/{batch_id}/issues").json()
    money = next(i for i in issues if i["issue_type"] == "missing_payment")
    before_open = body["open_issues_count"]
    before_unrec = body["unreconciled_amount"]

    patched = client.patch(
        f"/api/issues/{money['id']}",
        json={"status": "resolved", "note": "pagamento localizado no gateway"},
    )
    assert patched.status_code == 200
    assert patched.json()["status"] == "resolved"
    assert patched.json()["history"]

    dash2 = client.get(f"/api/imports/{batch_id}/dashboard").json()
    assert dash2["open_issues_count"] == before_open - 1
    assert dash2["unreconciled_amount"] < before_unrec


def test_report_orders_by_business_severity(client):
    demo = client.post("/api/demo/run")
    batch_id = demo.json()["batch"]["id"]
    report = client.get(f"/api/imports/{batch_id}/report?format=markdown")
    assert report.status_code == 200
    content = report.json()["content"]
    assert "Relatório de Fechamento" in content
    assert "Issues por severidade" in content


def test_missing_batch_returns_404(client):
    res = client.get("/api/imports/999999/dashboard")
    assert res.status_code == 404
