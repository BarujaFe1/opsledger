from __future__ import annotations

import copy
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.money import ZERO, as_json_number, money
from app.models import (
    ImportBatch,
    IssueStatusHistory,
    Order,
    OrderLine,
    Payment,
    ReconciliationIssue,
    StockMovement,
)
from app.reconciliation.engine import (
    MONEY_ISSUE_TYPES,
    _mismatch_under_over,
    compute_kpis,
    run_reconciliation,
)
from app.services.csv_validation import (
    CsvValidationError,
    preview_df,
    to_naive_utc,
    validate_orders,
    validate_payments,
    validate_stock,
)


def _persist_frames(
    db: Session,
    batch: ImportBatch,
    orders_df: pd.DataFrame,
    payments_df: pd.DataFrame,
    stock_df: pd.DataFrame,
) -> None:
    # Order is a header; lines live on OrderLine (item grain). One CSV row maps
    # to one OrderLine, but a header (Order) is persisted exactly once per
    # (batch_id, order_id): the first row for an order_id wins the header
    # attributes. Conflicting header attributes across rows of the same order
    # are detected separately by rule_duplicate_order (header_conflict).
    if not orders_df.empty:
        seen_orders: set[str] = set()
        line_seq: dict[str, int] = {}
        for _, row in orders_df.iterrows():
            oid = str(row["order_id"])
            if oid not in seen_orders:
                seen_orders.add(oid)
                db.add(
                    Order(
                        batch_id=batch.id,
                        order_id=oid,
                        order_date=to_naive_utc(row["order_date"]),
                        customer_name=str(row["customer_name"]),
                        customer_document_optional=(
                            None
                            if pd.isna(row.get("customer_document_optional"))
                            else str(row.get("customer_document_optional"))
                        ),
                        channel=str(row["channel"]),
                        status=str(row["status"]),
                    )
                )
            seq = line_seq.get(oid, 0) + 1
            line_seq[oid] = seq
            db.add(
                OrderLine(
                    batch_id=batch.id,
                    order_id=oid,
                    line_id=f"{oid}-L{seq}",
                    sku=str(row["sku"]),
                    product_name=str(row["product_name"]),
                    quantity=int(row["quantity"]),
                    unit_price=money(row["unit_price"]),
                    gross_amount=money(row["gross_amount"]),
                    discount_amount=money(row["discount_amount"]),
                    net_amount=money(row["net_amount"]),
                )
            )
    for _, row in payments_df.iterrows():
        db.add(
            Payment(
                batch_id=batch.id,
                payment_id=str(row["payment_id"]),
                order_id=str(row["order_id"]),
                paid_at=to_naive_utc(row["paid_at"]),
                amount=money(row["amount"]),
                method=str(row["method"]),
                status=str(row["status"]),
                transaction_reference=(
                    None
                    if pd.isna(row.get("transaction_reference"))
                    else str(row.get("transaction_reference"))
                ),
            )
        )
    for _, row in stock_df.iterrows():
        db.add(
            StockMovement(
                batch_id=batch.id,
                movement_id=str(row["movement_id"]),
                sku=str(row["sku"]),
                movement_type=str(row["movement_type"]),
                quantity=int(row["quantity"]),
                movement_date=to_naive_utc(row["movement_date"]),
                reference_order_id=(
                    None
                    if pd.isna(row.get("reference_order_id"))
                    else str(row.get("reference_order_id"))
                ),
                notes=None if pd.isna(row.get("notes")) else str(row.get("notes")),
            )
        )


def process_import(
    db: Session,
    *,
    source_name: str,
    orders_df: pd.DataFrame,
    payments_df: pd.DataFrame,
    stock_df: pd.DataFrame,
) -> tuple[ImportBatch, dict]:
    batch = ImportBatch(source_name=source_name, status="processing")
    db.add(batch)
    db.flush()

    try:
        drafts = run_reconciliation(orders_df, payments_df, stock_df)
        kpi = compute_kpis(orders_df, payments_df, drafts)

        _persist_frames(db, batch, orders_df, payments_df, stock_df)

        for draft in drafts:
            db.add(
                ReconciliationIssue(
                    batch_id=batch.id,
                    issue_type=draft.issue_type,
                    severity=draft.severity,
                    entity_type=draft.entity_type,
                    entity_id=draft.entity_id,
                    title=draft.title,
                    description=draft.description,
                    recommended_action=draft.recommended_action,
                    amount_impact=draft.amount_impact,
                    status="open",
                )
            )

        batch.total_orders = int(len(orders_df))
        batch.total_payments = int(len(payments_df))
        batch.total_stock_movements = int(len(stock_df))
        batch.total_issues = len(drafts)
        batch.total_amount = kpi["eligible_amount"]
        batch.reconciled_amount = kpi["reconciled_amount"]
        batch.unreconciled_amount = kpi["unreconciled_amount"]
        batch.status = "completed"
        db.commit()
        db.refresh(batch)

        preview = {
            "orders": preview_df(orders_df),
            "payments": preview_df(payments_df),
            "stock_movements": preview_df(stock_df),
        }
        return batch, preview
    except Exception:
        db.rollback()
        # recreate failed marker if needed
        failed = ImportBatch(
            source_name=source_name,
            status="failed",
            total_orders=int(len(orders_df)),
            total_payments=int(len(payments_df)),
            total_stock_movements=int(len(stock_df)),
        )
        db.add(failed)
        db.commit()
        raise


def run_demo(db: Session) -> tuple[ImportBatch, dict]:
    settings = get_settings()
    demo = settings.demo_dir
    orders_path = demo / "orders.csv"
    payments_path = demo / "payments.csv"
    stock_path = demo / "stock_movements.csv"
    for p in (orders_path, payments_path, stock_path):
        if not p.exists():
            raise CsvValidationError(
                f"Arquivo demo não encontrado: {p.name}. Gere os dados com scripts/generate_demo_data.py",
                code="demo_missing",
            )
    orders_df = validate_orders(orders_path)
    payments_df = validate_payments(payments_path)
    stock_df = validate_stock(stock_path)
    return process_import(
        db,
        source_name="demo:monthly_closing_2026_06",
        orders_df=orders_df,
        payments_df=payments_df,
        stock_df=stock_df,
    )


def run_upload(
    db: Session,
    orders_file: BinaryIO,
    payments_file: BinaryIO,
    stock_file: BinaryIO,
) -> tuple[ImportBatch, dict]:
    orders_df = validate_orders(orders_file)
    payments_df = validate_payments(payments_file)
    stock_df = validate_stock(stock_file)

    settings = get_settings()
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    orders_df.to_csv(settings.processed_dir / f"{stamp}_orders.csv", index=False)
    payments_df.to_csv(settings.processed_dir / f"{stamp}_payments.csv", index=False)
    stock_df.to_csv(settings.processed_dir / f"{stamp}_stock_movements.csv", index=False)

    return process_import(
        db,
        source_name="upload",
        orders_df=orders_df,
        payments_df=payments_df,
        stock_df=stock_df,
    )


def get_batch_or_404(db: Session, batch_id: int) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise LookupError(f"Batch {batch_id} não encontrado.")
    return batch


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def _build_orm_frames(orders_orm, lines_orm, payments_orm):
    """Build order-grain + payment DataFrames from ORM rows for compute_kpis.

    OrderLine money is aggregated to order grain (order_id). Channel/status come
    from the Order header. Needed because the grain split moved money off Order.
    """
    order_meta = {o.order_id: (o.channel, o.status) for o in orders_orm}
    line_rows = [
        {
            "order_id": ln.order_id,
            "sku": ln.sku,
            "quantity": ln.quantity,
            "net_amount": ln.net_amount,
        }
        for ln in lines_orm
    ]
    if line_rows:
        lines_df = pd.DataFrame(line_rows)
        grp = lines_df.groupby("order_id", as_index=False).agg(
            net_amount=("net_amount", "sum"),
            quantity=("quantity", "sum"),
            sku=("sku", "first"),
        )
        grp["channel"] = grp["order_id"].map(lambda oid: order_meta.get(oid, ("", ""))[0])
        grp["status"] = grp["order_id"].map(lambda oid: order_meta.get(oid, ("", ""))[1])
        orders_df = grp
    else:
        orders_df = pd.DataFrame(columns=["order_id", "net_amount", "quantity", "sku", "channel", "status"])

    pay_rows = [
        {
            "payment_id": p.payment_id,
            "order_id": p.order_id,
            "amount": p.amount,
            "status": p.status,
        }
        for p in payments_orm
    ]
    payments_df = (
        pd.DataFrame(pay_rows)
        if pay_rows
        else pd.DataFrame(columns=["payment_id", "order_id", "amount", "status"])
    )
    return orders_df, payments_df


def _dashboard_from_data(
    batch: ImportBatch, issues: list, orders_df: pd.DataFrame, payments_df: pd.DataFrame
) -> dict:
    """Compute dashboard metrics from already-loaded issues + order/payment frames.

    Shared by the DB-backed path and the stateless public demo path.

    Channel impact is restricted to MONEY_ISSUE_TYPES and deduped by
    (issue_type, entity_id), so it can never exceed unreconciled_amount
    (no financial double-counting). The KPI decomposition comes from
    compute_kpis and satisfies eligible = reconciled + missing + under
    (overpayment/orphan_payment are payments-side exposures, reported separately).
    """
    by_sev: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for issue in issues:
        by_sev[issue.severity] = by_sev.get(issue.severity, 0) + 1
        by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1

    # Channel impact: MONEY_ISSUE_TYPES only, deduped, and EXCLUDING overpayment
    # (payments-side, not an order-side shortfall). Invariant:
    # sum(impact per channel) == unreconciled_amount (missing + under only).
    order_channel = (
        {str(o["order_id"]): str(o.get("channel", "")) for _, o in orders_df.iterrows()}
        if not orders_df.empty
        else {}
    )
    open_statuses = {"open", "reviewing"}
    mismatch_ids = {
        str(i.entity_id)
        for i in issues
        if i.issue_type == "amount_mismatch" and i.status in open_statuses
    }
    under_by_order = _mismatch_under_over(orders_df, payments_df, mismatch_ids)
    channel_stats: dict[str, dict[str, Decimal]] = {}
    seen: set[tuple[str, str]] = set()
    for issue in issues:
        if issue.status not in open_statuses:
            continue
        if issue.issue_type not in MONEY_ISSUE_TYPES:
            continue
        key = (issue.issue_type, issue.entity_id)
        if key in seen:
            continue
        seen.add(key)
        channel = order_channel.get(str(issue.entity_id))
        if not channel:
            continue
        if issue.issue_type == "amount_mismatch":
            impact = under_by_order.get(str(issue.entity_id), (ZERO, ZERO))[0]
        else:
            impact = money(issue.amount_impact or 0)
        if impact <= ZERO:
            continue
        bucket = channel_stats.setdefault(channel, {"impact": ZERO, "issues": 0})
        bucket["impact"] += impact
        bucket["issues"] += 1

    top_channels = sorted(
        [
            {"channel": k, "impact": as_json_number(v["impact"]), "issues": int(v["issues"])}
            for k, v in channel_stats.items()
        ],
        key=lambda x: x["impact"],
        reverse=True,
    )[:5]

    next_action = None
    open_issues = [i for i in issues if i.status in open_statuses]
    if open_issues:
        top = sorted(
            open_issues,
            key=lambda i: (SEVERITY_RANK.get(i.severity, 9), -i.amount_impact),
        )[0]
        next_action = f"{top.title} — {top.recommended_action}"
    elif not issues:
        next_action = "Nenhum problema encontrado. Fechamento operacional pronto para revisão final."
    else:
        next_action = "Todas as issues foram resolvidas ou ignoradas. Fechamento pronto para revisão final."

    kpi = compute_kpis(orders_df, payments_df, issues)

    return {
        "batch_id": batch.id,
        "total_orders": batch.total_orders,
        "total_order_amount": as_json_number(kpi["eligible_amount"]),
        "reconciled_amount": as_json_number(kpi["reconciled_amount"]),
        "unreconciled_amount": as_json_number(kpi["unreconciled_amount"]),
        "eligible_amount": as_json_number(kpi["eligible_amount"]),
        "missing_payment_amount": as_json_number(kpi["missing_payment_amount"]),
        "underpayment_amount": as_json_number(kpi["underpayment_amount"]),
        "overpayment_amount": as_json_number(kpi["overpayment_amount"]),
        "orphan_payment_amount": as_json_number(kpi["orphan_payment_amount"]),
        "pending_excluded_amount": as_json_number(kpi["pending_excluded_amount"]),
        "total_issues": batch.total_issues,
        "open_issues_count": len(open_issues),
        "issues_by_severity": [
            {"severity": k, "count": v}
            for k, v in sorted(by_sev.items(), key=lambda kv: SEVERITY_RANK.get(kv[0], 9))
        ],
        "issues_by_type": [{"issue_type": k, "count": v} for k, v in sorted(by_type.items())],
        "top_channels_with_divergence": top_channels,
        "next_best_action": next_action,
    }


def build_dashboard(db: Session, batch: ImportBatch) -> dict:
    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .all()
    )
    orders_orm = db.query(Order).filter(Order.batch_id == batch.id).all()
    lines_orm = db.query(OrderLine).filter(OrderLine.batch_id == batch.id).all()
    payments_orm = db.query(Payment).filter(Payment.batch_id == batch.id).all()
    orders_df, payments_df = _build_orm_frames(orders_orm, lines_orm, payments_orm)
    return _dashboard_from_data(batch, issues, orders_df, payments_df)


def update_issue_status(
    db: Session,
    issue: ReconciliationIssue,
    new_status: str,
    note: str | None = None,
) -> ReconciliationIssue:
    previous = issue.status
    if previous == new_status and not note:
        return issue
    issue.status = new_status
    issue.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    if new_status == "resolved":
        issue.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        issue.resolution_note = note
    elif note:
        issue.resolution_note = note
    db.add(
        IssueStatusHistory(
            issue_id=issue.id,
            previous_status=previous,
            new_status=new_status,
            note=note,
        )
    )
    db.commit()
    db.refresh(issue)
    return issue


def _report_from_data(batch: ImportBatch, issues: list, orders_df: pd.DataFrame, payments_df: pd.DataFrame) -> str:
    """Build the closing-report markdown from already-loaded issues/order frames."""
    dash = _dashboard_from_data(batch, issues, orders_df, payments_df)
    issues_sorted = sorted(
        issues,
        key=lambda i: (SEVERITY_RANK.get(i.severity, 9), -float(money(i.amount_impact or 0))),
    )
    lines = [
        f"# Relatório de Fechamento Operacional — Batch #{batch.id}",
        "",
        f"**Fonte:** {batch.source_name}  ",
        f"**Status do batch:** {batch.status}  ",
        f"**Gerado em:** {(batch.created_at or datetime.now(timezone.utc)).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Indicadores",
        "",
        f"- Pedidos: **{dash['total_orders']}**",
        f"- Valor elegível (pagos/enviados): **R$ {dash['eligible_amount']:.2f}**",
        f"- Valor conciliado (issues abertas): **R$ {dash['reconciled_amount']:.2f}**",
        f"- Valor em divergência (issues abertas): **R$ {dash['unreconciled_amount']:.2f}**",
        f"- Issues totais: **{dash['total_issues']}**",
        f"- Issues abertas/em revisão: **{dash['open_issues_count']}**",
        "",
        "## Decomposição de valor elegível",
        "",
        f"- Elegível: **R$ {dash['eligible_amount']:.2f}**",
        f"- Conciliado: **R$ {dash['reconciled_amount']:.2f}**",
        f"- Pagamento ausente: **R$ {dash['missing_payment_amount']:.2f}**",
        f"- Subpagamento (under): **R$ {dash['underpayment_amount']:.2f}**",
        f"- Superpagamento (over): **R$ {dash['overpayment_amount']:.2f}**",
        f"- Pagamento órfão (sem pedido): **R$ {dash['orphan_payment_amount']:.2f}**",
        f"- Pendentes excluídos (criado/cancelado/devolvido): **R$ {dash['pending_excluded_amount']:.2f}**",
        "",
        "## Issues por severidade",
        "",
    ]
    if dash["issues_by_severity"]:
        for item in dash["issues_by_severity"]:
            lines.append(f"- {item['severity']}: {item['count']}")
    else:
        lines.append("- Nenhum problema encontrado.")
    lines.extend(["", "## Próxima melhor ação", "", dash.get("next_best_action") or "—", "", "## Top issues", ""])
    for issue in issues_sorted[:15]:
        impact = money(issue.amount_impact or 0)
        lines.append(
            f"- **[{issue.severity}] {issue.title}** — impacto R$ {impact:.2f} — status `{issue.status}`"
        )
        lines.append(f"  - {issue.recommended_action}")
    if not issues:
        lines.append("- Sem issues abertas.")
    lines.extend(["", "---", "_Gerado por OpsLedger MVP_"])
    return "\n".join(lines)


def build_report_markdown(db: Session, batch: ImportBatch) -> str:
    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .all()
    )
    orders_orm = db.query(Order).filter(Order.batch_id == batch.id).all()
    lines_orm = db.query(OrderLine).filter(OrderLine.batch_id == batch.id).all()
    payments_orm = db.query(Payment).filter(Payment.batch_id == batch.id).all()
    orders_df, payments_df = _build_orm_frames(orders_orm, lines_orm, payments_orm)
    return _report_from_data(batch, issues, orders_df, payments_df)


def issues_to_csv_rows(issues: list[ReconciliationIssue]) -> list[dict]:
    rows = []
    for i in issues:
        rows.append(
            {
                "id": i.id,
                "batch_id": i.batch_id,
                "issue_type": i.issue_type,
                "severity": i.severity,
                "entity_type": i.entity_type,
                "entity_id": i.entity_id,
                "title": i.title,
                "description": i.description,
                "recommended_action": i.recommended_action,
                "amount_impact": i.amount_impact,
                "status": i.status,
                "created_at": i.created_at.isoformat() if i.created_at else "",
                "updated_at": i.updated_at.isoformat() if i.updated_at else "",
                "resolved_at": i.resolved_at.isoformat() if i.resolved_at else "",
                "resolution_note": i.resolution_note or "",
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Stateless public demo (no SQLite write, deterministic, reconstructible)
# ---------------------------------------------------------------------------

DEMO_BATCH_ID = -1
# Fixed closing instant for the golden demo dataset. Keeps the stateless public
# output deterministic (timestamps don't drift between serverless cold starts).
DEMO_CLOSED_AT = datetime(2026, 6, 30, 23, 59, 59, tzinfo=timezone.utc)
_DEMO_CACHE: dict[str, dict] = {}
_DEMO_LOCK = threading.Lock()


def _build_demo_payload() -> dict:
    """Reconcile the committed golden demo dataset fully in memory.

    No row is written to SQLite. The result is cached by dataset version so it
    survives serverless cold starts/instance routing (the dataset is fixed and
    deterministic, so every rebuild is identical).
    """
    settings = get_settings()
    demo = settings.demo_dir
    for name in ("orders.csv", "payments.csv", "stock_movements.csv"):
        p = demo / name
        if not p.exists():
            raise CsvValidationError(
                f"Arquivo demo não encontrado: {p.name}.",
                code="demo_missing",
            )
    orders_df = validate_orders(demo / "orders.csv")
    payments_df = validate_payments(demo / "payments.csv")
    stock_df = validate_stock(demo / "stock_movements.csv")
    drafts = run_reconciliation(orders_df, payments_df, stock_df)
    kpi = compute_kpis(orders_df, payments_df, drafts)

    issues = [
        ReconciliationIssue(
            id=idx + 1,
            batch_id=DEMO_BATCH_ID,
            issue_type=d.issue_type,
            severity=d.severity,
            entity_type=d.entity_type,
            entity_id=d.entity_id,
            title=d.title,
            description=d.description,
            recommended_action=d.recommended_action,
            amount_impact=d.amount_impact,
            status="open",
            created_at=DEMO_CLOSED_AT,
            updated_at=DEMO_CLOSED_AT,
        )
        for idx, d in enumerate(drafts)
    ]
    orders = [
        Order(
            order_id=str(r["order_id"]),
            order_date=to_naive_utc(r["order_date"]),
            customer_name=str(r["customer_name"]),
            channel=str(r["channel"]),
            status=str(r["status"]),
        )
        for _, r in orders_df.iterrows()
    ]
    batch = ImportBatch(
        id=DEMO_BATCH_ID,
        source_name="demo:monthly_closing_2026_06",
        status="completed",
        created_at=DEMO_CLOSED_AT,
        total_orders=int(len(orders_df)),
        total_payments=int(len(payments_df)),
        total_stock_movements=int(len(stock_df)),
        total_issues=len(drafts),
        total_amount=kpi["eligible_amount"],
        reconciled_amount=kpi["reconciled_amount"],
        unreconciled_amount=kpi["unreconciled_amount"],
    )
    dashboard = _dashboard_from_data(batch, issues, orders_df, payments_df)
    report_md = _report_from_data(batch, issues, orders_df, payments_df)
    return {
        "batch": batch,
        "issues": issues,
        "orders": orders,
        "dashboard": dashboard,
        "report_md": report_md,
        "orders_df": orders_df,
        "payments_df": payments_df,
        "stock_df": stock_df,
    }


def run_demo_stateless() -> dict:
    """Build (and cache by dataset version) the read-only public demo payload.

    Returns a defensive deep copy so callers can never mutate the cached
    payload by reference. The public demo is shared read-only state: every
    visitor (and every serverless instance / cold start) must observe the
    exact same deterministic dataset, so the cache is the single source of
    truth and is never handed out by reference.
    """
    key = get_settings().demo_dataset_version
    with _DEMO_LOCK:
        payload = _DEMO_CACHE.get(key)
        if payload is None:
            payload = _build_demo_payload()
            _DEMO_CACHE[key] = payload
    return copy.deepcopy(payload)


def is_demo_batch_id(batch_id: int) -> bool:
    return batch_id == DEMO_BATCH_ID


def get_demo_issue(issue_id: int):
    for issue in run_demo_stateless()["issues"]:
        if issue.id == issue_id:
            return issue
    return None
