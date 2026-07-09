from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

import pandas as pd
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    ImportBatch,
    IssueStatusHistory,
    Order,
    Payment,
    ReconciliationIssue,
    StockMovement,
)
from app.reconciliation.engine import compute_amounts, run_reconciliation
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
    for _, row in orders_df.iterrows():
        db.add(
            Order(
                batch_id=batch.id,
                order_id=str(row["order_id"]),
                order_date=to_naive_utc(row["order_date"]),
                customer_name=str(row["customer_name"]),
                customer_document_optional=(
                    None
                    if pd.isna(row.get("customer_document_optional"))
                    else str(row.get("customer_document_optional"))
                ),
                channel=str(row["channel"]),
                sku=str(row["sku"]),
                product_name=str(row["product_name"]),
                quantity=int(row["quantity"]),
                unit_price=float(row["unit_price"]),
                gross_amount=float(row["gross_amount"]),
                discount_amount=float(row["discount_amount"]),
                net_amount=float(row["net_amount"]),
                status=str(row["status"]),
            )
        )
    for _, row in payments_df.iterrows():
        db.add(
            Payment(
                batch_id=batch.id,
                payment_id=str(row["payment_id"]),
                order_id=str(row["order_id"]),
                paid_at=to_naive_utc(row["paid_at"]),
                amount=float(row["amount"]),
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
                reference_order_id=row.get("reference_order_id"),
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
        total_amount, reconciled, unreconciled = compute_amounts(orders_df, payments_df, drafts)

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
        batch.total_amount = total_amount
        batch.reconciled_amount = reconciled
        batch.unreconciled_amount = unreconciled
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
        source_name="demo",
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


def build_dashboard(db: Session, batch: ImportBatch) -> dict:
    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .all()
    )
    orders = db.query(Order).filter(Order.batch_id == batch.id).all()

    by_sev: dict[str, int] = {}
    by_type: dict[str, int] = {}
    for issue in issues:
        by_sev[issue.severity] = by_sev.get(issue.severity, 0) + 1
        by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1

    # channel impact from order-linked issues
    order_channel = {o.order_id: o.channel for o in orders}
    channel_stats: dict[str, dict[str, float]] = {}
    for issue in issues:
        channel = None
        if issue.entity_type == "order":
            channel = order_channel.get(issue.entity_id)
        if issue.issue_type == "channel_standardization":
            channel = issue.entity_id
        if not channel:
            continue
        bucket = channel_stats.setdefault(channel, {"impact": 0.0, "issues": 0})
        bucket["impact"] += float(issue.amount_impact or 0)
        bucket["issues"] += 1

    top_channels = sorted(
        [
            {"channel": k, "impact": v["impact"], "issues": int(v["issues"])}
            for k, v in channel_stats.items()
        ],
        key=lambda x: x["impact"],
        reverse=True,
    )[:5]

    next_action = None
    priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    open_issues = [i for i in issues if i.status in {"open", "reviewing"}]
    if open_issues:
        top = sorted(open_issues, key=lambda i: (priority.get(i.severity, 9), -i.amount_impact))[0]
        next_action = f"{top.title} — {top.recommended_action}"
    elif not issues:
        next_action = "Nenhum problema encontrado. Fechamento operacional pronto para revisão final."

    return {
        "batch_id": batch.id,
        "total_orders": batch.total_orders,
        "total_order_amount": batch.total_amount,
        "reconciled_amount": batch.reconciled_amount,
        "unreconciled_amount": batch.unreconciled_amount,
        "total_issues": batch.total_issues,
        "issues_by_severity": [{"severity": k, "count": v} for k, v in sorted(by_sev.items())],
        "issues_by_type": [{"issue_type": k, "count": v} for k, v in sorted(by_type.items())],
        "top_channels_with_divergence": top_channels,
        "next_best_action": next_action,
    }


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


def build_report_markdown(db: Session, batch: ImportBatch) -> str:
    dash = build_dashboard(db, batch)
    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .order_by(ReconciliationIssue.severity.desc(), ReconciliationIssue.amount_impact.desc())
        .all()
    )
    lines = [
        f"# Relatório de Fechamento Operacional — Batch #{batch.id}",
        "",
        f"**Fonte:** {batch.source_name}  ",
        f"**Status do batch:** {batch.status}  ",
        f"**Gerado em:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "## Indicadores",
        "",
        f"- Pedidos: **{dash['total_orders']}**",
        f"- Valor total: **R$ {dash['total_order_amount']:.2f}**",
        f"- Valor conciliado: **R$ {dash['reconciled_amount']:.2f}**",
        f"- Valor em divergência: **R$ {dash['unreconciled_amount']:.2f}**",
        f"- Issues: **{dash['total_issues']}**",
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
    for issue in issues[:15]:
        lines.append(
            f"- **[{issue.severity}] {issue.title}** — impacto R$ {issue.amount_impact:.2f} — status `{issue.status}`"
        )
        lines.append(f"  - {issue.recommended_action}")
    if not issues:
        lines.append("- Sem issues abertas.")
    lines.extend(["", "---", "_Gerado por OpsLedger MVP_"])
    return "\n".join(lines)


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
