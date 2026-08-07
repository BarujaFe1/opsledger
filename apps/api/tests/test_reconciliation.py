from __future__ import annotations

import io
from datetime import datetime, timezone

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.money import ZERO, money
from app.db.session import Base, get_db
from app.main import app
from app.models import ImportBatch, Order, OrderLine, Payment
from app.reconciliation.engine import (
    compute_kpis,
    rule_amount_mismatch,
    rule_channel_standardization,
    rule_duplicate_order,
    rule_missing_payment,
    rule_missing_stock_out,
    rule_negative_stock,
    rule_orphan_payment,
    rule_refund_anomalies,
    run_reconciliation,
)
from app.services.csv_validation import CsvValidationError, validate_payments
from app.services.import_service import _build_orm_frames, _persist_frames, issue_impact_term


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
    assert issues[0].amount_impact == money("100.00")


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
    assert issues[0].amount_impact == money("30.00")


def test_legitimate_multiline_order_no_duplicate():
    """Same order_id with consistent header + distinct SKUs is a VALID multi-line
    order, not a duplicate."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-B", "net_amount": 50.0},
        ]
    )
    issues = rule_duplicate_order(orders)
    assert issues == []


def test_duplicate_line_detected():
    """Two identical lines for the same order_id is a genuine duplicate line."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0},
        ]
    )
    issues = rule_duplicate_order(orders)
    assert len(issues) == 1
    assert issues[0].issue_type == "duplicate_line"
    assert issues[0].severity == "high"


def test_header_conflict_detected():
    """Same order_id with conflicting header attributes (channel) is a conflict."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "channel": "Shopify", "sku": "SKU-A", "net_amount": 100.0},
            {**BASE_ORDER, "order_id": "ORD-1", "channel": "Loja Física", "sku": "SKU-B", "net_amount": 50.0},
        ]
    )
    issues = rule_duplicate_order(orders)
    assert len(issues) == 1
    assert issues[0].issue_type == "header_conflict"
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


@pytest.fixture()
def dbsession(tmp_path):
    db_path = tmp_path / "t.db"
    eng = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    with SessionLocal() as s:
        yield s
    eng.dispose()


def test_health(client):
    res = client.get("/api/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_demo_endpoint(client):
    res = client.post("/api/demo/run")
    assert res.status_code == 200
    body = res.json()
    assert body["batch"]["status"] == "completed"
    assert body["batch"]["source_name"] == "demo:monthly_closing_2026_06"
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


def test_issue_impact_term_distinguishes_financial_from_operational():
    assert issue_impact_term("missing_payment") == "impacto"
    assert issue_impact_term("orphan_payment") == "impacto"
    assert issue_impact_term("amount_mismatch") == "impacto"
    assert issue_impact_term("duplicate_line") == "impacto"
    assert issue_impact_term("header_conflict") == "impacto"
    assert issue_impact_term("missing_stock_out") == "valor associado"
    assert issue_impact_term("negative_stock") == "valor associado"
    assert issue_impact_term("channel_standardization") == "valor associado"


def test_missing_batch_returns_404(client):
    res = client.get("/api/imports/999999/dashboard")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Fase 2a: order/order_line grain + dedup
# ---------------------------------------------------------------------------


def test_multiline_order_dedups_missing_payment():
    """Two lines for the same order_id -> one missing_payment issue, net = sum."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0, "quantity": 1, "status": "paid"},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-B", "net_amount": 50.0, "quantity": 2, "status": "paid"},
        ]
    )
    payments = _payments([])
    issues = rule_missing_payment(orders, payments)
    assert len(issues) == 1
    assert issues[0].entity_id == "ORD-1"
    assert issues[0].amount_impact == money("150.00")


def test_multiline_order_missing_stock_out_per_sku():
    """Multi-SKU shipped order with no 'out' -> one missing_stock_out PER SKU."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0, "quantity": 2, "status": "shipped"},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-B", "net_amount": 50.0, "quantity": 3, "status": "shipped"},
        ]
    )
    stock = _stock([])
    issues = rule_missing_stock_out(orders, stock)
    assert len(issues) == 2
    assert {i.entity_id for i in issues} == {"ORD-1:SKU-A", "ORD-1:SKU-B"}
    # Only SKU-B gets an 'out' movement -> only SKU-A remains missing.
    stock2 = _stock(
        [
            {
                "movement_id": "M1",
                "sku": "SKU-B",
                "movement_type": "out",
                "quantity": 3,
                "movement_date": _dt("2026-06-01T09:00:00+00:00"),
                "reference_order_id": "ORD-1",
            }
        ]
    )
    issues2 = rule_missing_stock_out(orders, stock2)
    assert len(issues2) == 1
    assert issues2[0].entity_id == "ORD-1:SKU-A"


# ---------------------------------------------------------------------------
# Fase 2a.1: grain invariants (persistence + multi-line correctness)
# ---------------------------------------------------------------------------


def test_multiline_order_persists_one_header_two_lines(dbsession):
    """One Order header per order_id, N OrderLines — not N headers."""
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-B", "net_amount": 50.0},
        ]
    )
    batch = ImportBatch(source_name="t", status="processing")
    dbsession.add(batch)
    dbsession.flush()
    _persist_frames(dbsession, batch, orders, pd.DataFrame(), pd.DataFrame())
    dbsession.commit()
    headers = dbsession.query(Order).filter(Order.batch_id == batch.id).all()
    lines = dbsession.query(OrderLine).filter(OrderLine.batch_id == batch.id).all()
    assert len(headers) == 1
    assert headers[0].order_id == "ORD-1"
    assert len(lines) == 2
    assert {l.sku for l in lines} == {"SKU-A", "SKU-B"}


def test_multiline_order_total_orders_grain(client):
    """Fase 2a.1 residual fix: total_orders counts headers, not order-line rows.

    ORD-1 has 2 SKU lines (one header). The persisted Order table has 1 header /
    2 lines; batch.total_orders and dashboard.total_orders must both be 1, not 2.
    """
    orders = (
        "order_id,order_date,customer_name,customer_document_optional,channel,sku,product_name,"
        "quantity,unit_price,gross_amount,discount_amount,net_amount,status\n"
        "ORD-1,2026-06-01T10:00:00+00:00,Ana Silva,,Shopify,SKU-A,Item A,1,100,100,0,100,paid\n"
        "ORD-1,2026-06-01T10:05:00+00:00,Ana Silva,,Shopify,SKU-B,Item B,1,50,50,0,50,paid\n"
    )
    payments = (
        "payment_id,order_id,paid_at,amount,method,status,transaction_reference\n"
        "PAY-1,ORD-1,2026-06-01T11:00:00+00:00,150,pix,paid,TX-1\n"
    )
    stock = (
        "movement_id,sku,movement_type,quantity,movement_date,reference_order_id,notes\n"
        "M1,SKU-A,out,1,2026-06-01T12:00:00+00:00,ORD-1,\n"
        "M2,SKU-B,out,1,2026-06-01T12:05:00+00:00,ORD-1,\n"
    )
    files = {
        "orders": ("orders.csv", orders, "text/csv"),
        "payments": ("payments.csv", payments, "text/csv"),
        "stock_movements": ("stock.csv", stock, "text/csv"),
    }
    uploaded = client.post("/api/imports", files=files)
    assert uploaded.status_code == 200, uploaded.text
    body = uploaded.json()
    # 2 SKU lines, 1 header -> total_orders must be 1 (header grain), not 2.
    assert body["batch"]["total_orders"] == 1
    batch_id = body["batch"]["id"]
    dash = client.get(f"/api/imports/{batch_id}/dashboard").json()
    assert dash["total_orders"] == 1


def test_same_order_id_across_batches_persists_both(dbsession):
    """Same order_id re-imported in a different batch must not hit the unique constraint."""
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0}])
    b1 = ImportBatch(source_name="t1", status="processing")
    b2 = ImportBatch(source_name="t2", status="processing")
    dbsession.add(b1)
    dbsession.add(b2)
    dbsession.flush()
    # Would raise IntegrityError if uq_order_line / uq_order_header lacked batch_id.
    _persist_frames(dbsession, b1, orders, pd.DataFrame(), pd.DataFrame())
    _persist_frames(dbsession, b2, orders, pd.DataFrame(), pd.DataFrame())
    dbsession.commit()
    h1 = dbsession.query(Order).filter(Order.batch_id == b1.id).all()
    h2 = dbsession.query(Order).filter(Order.batch_id == b2.id).all()
    assert len(h1) == 1 and len(h2) == 1
    assert {h.order_id for h in h1 + h2} == {"ORD-1"}


# ---------------------------------------------------------------------------
# Fase 2a: KPI decomposition (no inflation)
# ---------------------------------------------------------------------------


def test_compute_kpis_missing_payment_invariant():
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments([])
    issues = run_reconciliation(orders, payments, _stock([]))
    kpi = compute_kpis(orders, payments, issues)
    assert kpi["eligible_amount"] == money("100.00")
    assert kpi["missing_payment_amount"] == money("100.00")
    assert kpi["reconciled_amount"] == money("0.00")
    assert kpi["pending_excluded_amount"] == ZERO
    assert kpi["eligible_amount"] == (
        kpi["reconciled_amount"] + kpi["missing_payment_amount"] + kpi["underpayment_amount"]
    )


def test_compute_kpis_underpayment_multiline_invariant():
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0, "status": "paid"},
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-B", "net_amount": 50.0, "status": "paid"},
            {**BASE_ORDER, "order_id": "ORD-2", "sku": "SKU-A", "net_amount": 200.0, "status": "canceled"},
        ]
    )
    payments = _payments(
        [
            {
                "payment_id": "PAY-1",
                "order_id": "ORD-1",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 100.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    kpi = compute_kpis(orders, payments, issues)
    # Only ORD-1 is eligible (ORD-2 canceled -> pending_excluded).
    assert kpi["eligible_amount"] == money("150.00")
    assert kpi["pending_excluded_amount"] == money("200.00")
    # ORD-1 paid 100 of 150 net -> underpayment 50.
    assert kpi["underpayment_amount"] == money("50.00")
    assert kpi["reconciled_amount"] == money("100.00")
    assert kpi["eligible_amount"] == (
        kpi["reconciled_amount"] + kpi["missing_payment_amount"] + kpi["underpayment_amount"]
    )


def test_compute_kpis_orphan_separate_from_eligible():
    orders = _orders([])
    payments = _payments(
        [
            {
                "payment_id": "PAY-X",
                "order_id": "ORD-GHOST",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 77.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    kpi = compute_kpis(orders, payments, issues)
    assert kpi["orphan_payment_amount"] == money("77.00")
    # orphan is payments-side; eligible stays 0 and invariant holds trivially.
    assert kpi["eligible_amount"] == ZERO
    assert kpi["reconciled_amount"] == ZERO


def test_overpayment_is_payment_side_exposure():
    """Order net R$100 with payment R$110: fully matched (100), R$10 excess cash.

    Overpayment is a payments-side exposure, NOT subtracted from the matched
    order amount — reconciled must stay 100, not drop to 90.
    """
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments(
        [
            {
                "payment_id": "PAY-1",
                "order_id": "ORD-1",
                "paid_at": _dt("2026-06-01T11:00:00+00:00"),
                "amount": 110.0,
                "method": "pix",
                "status": "paid",
            }
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    kpi = compute_kpis(orders, payments, issues)
    assert kpi["eligible_amount"] == money("100.00")
    assert kpi["reconciled_amount"] == money("100.00")
    assert kpi["missing_payment_amount"] == ZERO
    assert kpi["underpayment_amount"] == ZERO
    assert kpi["overpayment_amount"] == money("10.00")
    # Invariant: eligible == reconciled + missing + under (over is separate).
    assert kpi["eligible_amount"] == (
        kpi["reconciled_amount"] + kpi["missing_payment_amount"] + kpi["underpayment_amount"]
    )


# ---------------------------------------------------------------------------
# Fase 2a: channel double-counting fix (dashboard)
# ---------------------------------------------------------------------------


def test_channel_impact_excludes_non_money_issues(client):
    """A shipped order with no payment and no stock-out yields missing_payment
    AND missing_stock_out. Channel impact must reflect only the money issue,
    so it equals (not exceeds) unreconciled_amount."""
    orders = (
        "order_id,order_date,customer_name,customer_document_optional,channel,sku,product_name,"
        "quantity,unit_price,gross_amount,discount_amount,net_amount,status\n"
        "ORD-SHIP,2026-06-01T10:00:00+00:00,Cliente X,,Shopify,SKU-A,Item,1,100,100,0,100,shipped\n"
    )
    payments = (
        "payment_id,order_id,paid_at,amount,method,status,transaction_reference\n"
        "PAY-ORPH,ORD-NOPE,2026-06-01T11:00:00+00:00,50,pix,paid,TX-ORPH\n"
    )
    stock = (
        "movement_id,sku,movement_type,quantity,movement_date,reference_order_id,notes\n"
        "M1,SKU-A,in,5,2026-05-31T08:00:00+00:00,,\n"
    )
    files = {
        "orders": ("orders.csv", orders, "text/csv"),
        "payments": ("payments.csv", payments, "text/csv"),
        "stock_movements": ("stock.csv", stock, "text/csv"),
    }
    uploaded = client.post("/api/imports", files=files)
    assert uploaded.status_code == 200, uploaded.text
    batch_id = uploaded.json()["batch"]["id"]

    dash = client.get(f"/api/imports/{batch_id}/dashboard").json()
    chan_sum = sum(c["impact"] for c in dash["top_channels_with_divergence"])
    # Channel impact == unreconciled (only the money issue counts); no inflation.
    # The orphan payment (PAY-ORPH -> ORD-NOPE) is excluded from channel impact
    # because its entity_id is a payment id, not an order id.
    assert chan_sum == dash["unreconciled_amount"]
    assert dash["unreconciled_amount"] == 100.0
    # missing_stock_out exists but must NOT inflate channel impact.
    issue_types = [i["issue_type"] for i in client.get(f"/api/imports/{batch_id}/issues").json()]
    assert "missing_stock_out" in issue_types
    assert "missing_payment" in issue_types


def test_dashboard_exposes_kpi_decomposition(client):
    orders = (
        "order_id,order_date,customer_name,customer_document_optional,channel,sku,product_name,"
        "quantity,unit_price,gross_amount,discount_amount,net_amount,status\n"
        "ORD-A,2026-06-01T10:00:00+00:00,Cliente X,,Shopify,SKU-A,Item,1,100,100,0,100,paid\n"
    )
    payments = (
        "payment_id,order_id,paid_at,amount,method,status,transaction_reference\n"
        "PAY-A,ORD-A,2026-06-01T11:00:00+00:00,100,pix,paid,TX-A\n"
    )
    stock = (
        "movement_id,sku,movement_type,quantity,movement_date,reference_order_id,notes\n"
        "M1,SKU-A,in,5,2026-05-31T08:00:00+00:00,,\n"
    )
    files = {
        "orders": ("orders.csv", orders, "text/csv"),
        "payments": ("payments.csv", payments, "text/csv"),
        "stock_movements": ("stock.csv", stock, "text/csv"),
    }
    uploaded = client.post("/api/imports", files=files)
    assert uploaded.status_code == 200, uploaded.text
    batch_id = uploaded.json()["batch"]["id"]
    dash = client.get(f"/api/imports/{batch_id}/dashboard").json()
    for field in [
        "eligible_amount",
        "missing_payment_amount",
        "underpayment_amount",
        "overpayment_amount",
        "orphan_payment_amount",
        "pending_excluded_amount",
    ]:
        assert field in dash
    # Fully reconciled order: eligible == reconciled, no divergence.
    assert dash["eligible_amount"] == 100.0
    assert dash["reconciled_amount"] == 100.0
    assert dash["unreconciled_amount"] == 0.0


# ---------------------------------------------------------------------------
# Fase 2b.1: multi-pagamentos + refunds/chargebacks
# ---------------------------------------------------------------------------


def _payment_row(pid, oid, amount, status, kind="payment"):
    return {
        "payment_id": pid,
        "order_id": oid,
        "paid_at": _dt("2026-06-01T11:00:00+00:00"),
        "amount": amount,
        "method": "pix",
        "status": status,
        "kind": kind,
    }


def test_multi_payment_order_covered():
    """Two payments summing to the order net are a VALID multi-payment, not a
    missing_payment (order_id is intentionally non-unique on Payment)."""
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments(
        [
            _payment_row("PAY-1", "ORD-1", 60.0, "paid"),
            _payment_row("PAY-2", "ORD-1", 40.0, "paid"),
        ]
    )
    issues = rule_missing_payment(orders, payments)
    assert issues == []
    kpi = compute_kpis(orders, payments, run_reconciliation(orders, payments, _stock([])))
    assert kpi["missing_payment_amount"] == ZERO
    assert kpi["reconciled_amount"] == money("100.00")


def test_refund_does_not_reduce_reconciled():
    """Order net R$100, paid R$100, refunded R$20.

    The order was paid CORRECTLY, then cash was reversed. Refunds must NOT be
    shown as 'underpayment' and must NOT reduce reconciled. They live in the
    separate cash-realization dimension (net_cash).
    """
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments(
        [
            _payment_row("PAY-1", "ORD-1", 100.0, "paid"),
            _payment_row("PAY-R", "ORD-1", 20.0, "refunded", "refund"),
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    # No refund anomaly issue for a well-formed refund.
    assert not any(i.issue_type in {"refund_without_payment", "over_refund", "chargeback"} for i in issues)
    kpi = compute_kpis(orders, payments, issues)
    # PAYMENT MATCHING dimension — refund does not touch it.
    assert kpi["eligible_amount"] == money("100.00")
    assert kpi["reconciled_amount"] == money("100.00")
    assert kpi["missing_payment_amount"] == ZERO
    assert kpi["underpayment_amount"] == ZERO
    # CASH REALIZATION dimension.
    assert kpi["gross_paid_amount"] == money("100.00")
    assert kpi["refunded_amount"] == money("20.00")
    assert kpi["active_chargeback_amount"] == ZERO
    assert kpi["net_cash_amount"] == money("80.00")
    # Original invariant still holds (refunds aren't in it).
    assert kpi["eligible_amount"] == (
        kpi["reconciled_amount"] + kpi["missing_payment_amount"] + kpi["underpayment_amount"]
    )


def test_chargeback_in_cash_dimension():
    """Order net R$100, paid R$100, chargeback R$30.

    The order was matched correctly (reconciled R$100, under R$0); the chargeback
    is a posterior cash reversal shown as active exposure in the cash dimension,
    never as an underpayment.
    """
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments(
        [
            _payment_row("PAY-1", "ORD-1", 100.0, "paid"),
            _payment_row("PAY-C", "ORD-1", 30.0, "charged_back", "chargeback"),
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    cb = [i for i in issues if i.issue_type == "chargeback"]
    assert len(cb) == 1
    assert cb[0].severity == "medium"
    # Chargeback is operational, not a financial divergence issue.
    assert issue_impact_term("chargeback") == "valor associado"
    kpi = compute_kpis(orders, payments, issues)
    # PAYMENT MATCHING — chargeback does not touch it.
    assert kpi["reconciled_amount"] == money("100.00")
    assert kpi["underpayment_amount"] == ZERO
    # CASH REALIZATION — chargeback is current exposure, reduces net_cash.
    assert kpi["gross_paid_amount"] == money("100.00")
    assert kpi["active_chargeback_amount"] == money("30.00")
    assert kpi["net_cash_amount"] == money("70.00")


def test_over_refund():
    """Order net R$100, paid R$100, refunded R$130 -> over_refund anomaly (R$30).

    The excess refund is a financial anomaly; it does NOT reduce reconciled
    (the order was matched correctly). It shows in the cash dimension.
    """
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments(
        [
            _payment_row("PAY-1", "ORD-1", 100.0, "paid"),
            _payment_row("PAY-R", "ORD-1", 130.0, "refunded", "refund"),
        ]
    )
    issues = rule_refund_anomalies(orders, payments)
    over = [i for i in issues if i.issue_type == "over_refund"]
    assert len(over) == 1
    assert over[0].amount_impact == money("30.00")
    assert over[0].severity == "high"
    kpi = compute_kpis(orders, payments, run_reconciliation(orders, payments, _stock([])))
    assert kpi["reconciled_amount"] == money("100.00")
    assert kpi["underpayment_amount"] == ZERO
    assert kpi["gross_paid_amount"] == money("100.00")
    assert kpi["refunded_amount"] == money("130.00")
    assert kpi["net_cash_amount"] == money("-30.00")


def test_refund_without_payment():
    """Refund with no settled payment -> refund_without_payment anomaly.

    The order genuinely has no payment, so it is ALSO a missing_payment in the
    matching dimension (reconciled R$0); the refund is a separate cash anomaly.
    """
    orders = _orders([{**BASE_ORDER, "order_id": "ORD-1", "net_amount": 100.0, "status": "paid"}])
    payments = _payments([_payment_row("PAY-R", "ORD-1", 50.0, "refunded", "refund")])
    issues = run_reconciliation(orders, payments, _stock([]))
    types = {i.issue_type for i in issues}
    assert "refund_without_payment" in types
    # No payment at all -> also a missing_payment (matching dimension).
    assert "missing_payment" in types
    rwp = next(i for i in issues if i.issue_type == "refund_without_payment")
    assert rwp.amount_impact == money("50.00")
    kpi = compute_kpis(orders, payments, issues)
    # CASH REALIZATION — gross paid is 0, refund 50 -> net cash negative.
    assert kpi["gross_paid_amount"] == ZERO
    assert kpi["refunded_amount"] == money("50.00")
    assert kpi["net_cash_amount"] == money("-50.00")
    # PAYMENT MATCHING — order never paid -> reconciled 0, missing 100.
    assert kpi["missing_payment_amount"] == money("100.00")
    assert kpi["reconciled_amount"] == ZERO


def test_refund_two_dimension_invariants():
    """Mixed batch: a regular refund+chargeback order, a clean order, and a
    partial-refund order. Both invariants must hold:
      PAYMENT MATCHING: eligible == reconciled + missing + under
      CASH REALIZATION: net_cash == gross_paid - refunded - chargeback
    """
    orders = _orders(
        [
            {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0, "status": "paid"},
            {**BASE_ORDER, "order_id": "ORD-2", "sku": "SKU-A", "net_amount": 50.0, "status": "paid"},
            {**BASE_ORDER, "order_id": "ORD-3", "sku": "SKU-A", "net_amount": 30.0, "status": "paid"},
        ]
    )
    payments = _payments(
        [
            _payment_row("P1", "ORD-1", 100.0, "paid"),
            _payment_row("PR", "ORD-1", 20.0, "refunded", "refund"),
            _payment_row("PC", "ORD-1", 5.0, "charged_back", "chargeback"),
            _payment_row("P2", "ORD-2", 50.0, "paid"),
            # ORD-3: paid 30 + refunded 10 -> regular refund, reconciled stays 30.
            _payment_row("P3", "ORD-3", 30.0, "paid"),
            _payment_row("P3R", "ORD-3", 10.0, "refunded", "refund"),
        ]
    )
    issues = run_reconciliation(orders, payments, _stock([]))
    kpi = compute_kpis(orders, payments, issues)
    # PAYMENT MATCHING: every order fully paid -> reconciled == eligible.
    assert kpi["eligible_amount"] == money("180.00")
    assert kpi["reconciled_amount"] == money("180.00")
    assert kpi["missing_payment_amount"] == ZERO
    assert kpi["underpayment_amount"] == ZERO
    assert kpi["eligible_amount"] == (
        kpi["reconciled_amount"] + kpi["missing_payment_amount"] + kpi["underpayment_amount"]
    )
    # CASH REALIZATION.
    assert kpi["gross_paid_amount"] == money("180.00")
    assert kpi["refunded_amount"] == money("30.00")  # 20 + 10
    assert kpi["active_chargeback_amount"] == money("5.00")
    assert kpi["net_cash_amount"] == money("145.00")  # 180 - 30 - 5
    assert kpi["net_cash_amount"] == (
        kpi["gross_paid_amount"] - kpi["refunded_amount"] - kpi["active_chargeback_amount"]
    )


def test_refund_path_parity(tmp_path):
    """CRITICAL: stateless CSV path must equal the DB-backed `_build_orm_frames`
    path for refund/chargeback netting (the no-Alembic parity gotcha)."""
    eng = create_engine(
        f"sqlite:///{(tmp_path / 'parity.db').as_posix()}",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=eng)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=eng)
    with SessionLocal() as dbsession:
        orders = _orders(
            [
                {**BASE_ORDER, "order_id": "ORD-1", "sku": "SKU-A", "net_amount": 100.0, "status": "paid"},
                {**BASE_ORDER, "order_id": "ORD-2", "sku": "SKU-A", "net_amount": 50.0, "status": "paid"},
            ]
        )
        payments = _payments(
            [
                _payment_row("P1", "ORD-1", 100.0, "paid"),
                _payment_row("PR", "ORD-1", 20.0, "refunded", "refund"),
                _payment_row("PC", "ORD-1", 5.0, "charged_back", "chargeback"),
                _payment_row("P2", "ORD-2", 50.0, "paid"),
            ]
        )
        # Stateless (CSV) path.
        issues_s = run_reconciliation(orders, payments, _stock([]))
        kpi_s = compute_kpis(orders, payments, issues_s)

        # DB-backed path.
        batch = ImportBatch(source_name="t", status="processing")
        dbsession.add(batch)
        dbsession.flush()
        _persist_frames(dbsession, batch, orders, payments, _stock([]))
        dbsession.commit()
        orders_orm = dbsession.query(Order).all()
        lines_orm = dbsession.query(OrderLine).all()
        payments_orm = dbsession.query(Payment).all()
        o_df, p_df = _build_orm_frames(orders_orm, lines_orm, payments_orm)
        issues_d = run_reconciliation(o_df, p_df, _stock([]))
        kpi_d = compute_kpis(o_df, p_df, issues_d)

        assert kpi_s == kpi_d
        assert {i.issue_type for i in issues_s} == {i.issue_type for i in issues_d}


# ---------------------------------------------------------------------------
# Fase 2b.1: CSV validation for kind / sign
# ---------------------------------------------------------------------------


def test_validate_payments_defaults_kind_to_payment():
    csv = (
        "payment_id,order_id,paid_at,amount,method,status,transaction_reference\n"
        "PAY-1,ORD-1,2026-06-01T11:00:00+00:00,100,pix,paid,TX-1\n"
    )
    df = validate_payments(io.StringIO(csv))
    assert (df["kind"] == "payment").all()


def test_validate_payments_accepts_refund_and_chargeback_kinds():
    csv = (
        "payment_id,order_id,paid_at,amount,method,status,kind,transaction_reference\n"
        "PAY-R,ORD-1,2026-06-01T11:00:00+00:00,20,pix,refunded,refund,TX-R\n"
        "PAY-C,ORD-1,2026-06-01T12:00:00+00:00,30,pix,charged_back,chargeback,TX-C\n"
    )
    df = validate_payments(io.StringIO(csv))
    assert set(df["kind"]) == {"refund", "chargeback"}


def test_validate_payments_rejects_invalid_kind():
    csv = (
        "payment_id,order_id,paid_at,amount,method,status,kind,transaction_reference\n"
        "PAY-1,ORD-1,2026-06-01T11:00:00+00:00,100,pix,paid,bogus,TX-1\n"
    )
    with pytest.raises(CsvValidationError) as exc:
        validate_payments(io.StringIO(csv))
    assert exc.value.code == "invalid_payment_kind"


def test_validate_payments_rejects_negative_amount():
    csv = (
        "payment_id,order_id,paid_at,amount,method,status,kind,transaction_reference\n"
        "PAY-1,ORD-1,2026-06-01T11:00:00+00:00,-100,pix,paid,refund,TX-1\n"
    )
    with pytest.raises(CsvValidationError) as exc:
        validate_payments(io.StringIO(csv))
    assert exc.value.code == "negative_amount"
