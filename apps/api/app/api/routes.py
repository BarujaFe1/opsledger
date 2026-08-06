from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.core.security import (
    escape_html,
    is_public_demo,
    mask_pii_row,
    sanitize_csv_cell,
    safe_error,
)
from app.db.session import get_db
from app.models import Order, ReconciliationIssue
from app.schemas import (
    DashboardOut,
    HealthResponse,
    ImportBatchOut,
    ImportPreviewOut,
    IssueDetailOut,
    IssueOut,
    IssueUpdateIn,
    PreviewRow,
    ReportOut,
)
from app.services.csv_validation import CsvValidationError, preview_df
from app.services.import_service import (
    SEVERITY_RANK,
    build_dashboard,
    build_report_markdown,
    get_batch_or_404,
    get_demo_issue,
    is_demo_batch_id,
    issues_to_csv_rows,
    money,
    run_demo,
    run_demo_stateless,
    run_upload,
    update_issue_status,
)

logger = logging.getLogger("opsledger")

router = APIRouter()

CSV_FIELDS = [
    "id",
    "batch_id",
    "issue_type",
    "severity",
    "entity_type",
    "entity_id",
    "title",
    "description",
    "recommended_action",
    "amount_impact",
    "status",
    "created_at",
    "updated_at",
    "resolved_at",
    "resolution_note",
]


def _http_from_validation(exc: CsvValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail=safe_error(exc.message, exc.code))


def _not_found(request: Request, message: str = "Recurso não encontrado.") -> HTTPException:
    rid = getattr(request.state, "request_id", None)
    return HTTPException(status_code=404, detail=safe_error(message, "not_found", rid))


def _masked_preview(df) -> dict:
    preview = preview_df(df)
    preview["sample"] = [mask_pii_row(r) for r in preview["sample"]]
    return preview


def _filter_issues(issues, severity, issue_type, status, channel, order_channel):
    result = list(issues)
    if severity:
        result = [i for i in result if i.severity == severity.lower()]
    if issue_type:
        result = [i for i in result if i.issue_type == issue_type]
    if status:
        result = [i for i in result if i.status == status.lower()]
    if channel:
        ch = channel.lower()
        filtered = []
        for i in result:
            if i.entity_type == "order" and i.entity_id in order_channel:
                filtered.append(i)
            elif i.issue_type == "channel_standardization" and i.entity_id.lower() == ch:
                filtered.append(i)
        result = filtered
    return result


def _sorted_issues(issues):
    return sorted(
        issues,
        key=lambda i: (SEVERITY_RANK.get(i.severity, 9), -float(money(i.amount_impact or 0))),
    )


def _csv_response(rows: list[dict], batch_id: int) -> StreamingResponse:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS, quoting=csv.QUOTE_MINIMAL)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: sanitize_csv_cell(v) for k, v in row.items()})
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="opsledger_issues_batch_{batch_id}.csv"'},
    )


@router.get("/mode")
def mode() -> dict:
    return {"public_demo": is_public_demo()}


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/demo/run", response_model=ImportPreviewOut)
def demo_run(request: Request, db: Session = Depends(get_db)) -> ImportPreviewOut:
    if is_public_demo():
        try:
            payload = run_demo_stateless()
        except CsvValidationError as exc:
            raise _http_from_validation(exc) from exc
        except Exception as exc:  # noqa: BLE001
            rid = getattr(request.state, "request_id", None)
            logger.exception("demo_failed request_id=%s", rid)
            raise HTTPException(
                status_code=500, detail=safe_error("Falha ao rodar demo.", "demo_failed", rid)
            ) from exc
        batch = payload["batch"]
        preview = {
            "orders": _masked_preview(payload["orders_df"]),
            "payments": preview_df(payload["payments_df"]),
            "stock_movements": preview_df(payload["stock_df"]),
        }
        return ImportPreviewOut(
            batch=ImportBatchOut.model_validate(batch),
            orders=PreviewRow(**preview["orders"]),
            payments=PreviewRow(**preview["payments"]),
            stock_movements=PreviewRow(**preview["stock_movements"]),
        )

    try:
        batch, preview = run_demo(db)
    except CsvValidationError as exc:
        raise _http_from_validation(exc) from exc
    except Exception as exc:  # noqa: BLE001
        rid = getattr(request.state, "request_id", None)
        logger.exception("demo_failed request_id=%s", rid)
        raise HTTPException(
            status_code=500, detail=safe_error("Falha ao rodar demo.", "demo_failed", rid)
        ) from exc
    return ImportPreviewOut(
        batch=ImportBatchOut.model_validate(batch),
        orders=PreviewRow(**preview["orders"]),
        payments=PreviewRow(**preview["payments"]),
        stock_movements=PreviewRow(**preview["stock_movements"]),
    )


@router.post("/imports", response_model=ImportPreviewOut)
async def create_import(
    request: Request,
    orders: UploadFile = File(...),
    payments: UploadFile = File(...),
    stock_movements: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportPreviewOut:
    if is_public_demo():
        raise HTTPException(
            status_code=403,
            detail=safe_error(
                "Upload desabilitado na demo pública. Execute o OpsLedger localmente para importar arquivos.",
                "upload_disabled",
            ),
        )
    try:
        batch, preview = run_upload(db, orders.file, payments.file, stock_movements.file)
    except CsvValidationError as exc:
        raise _http_from_validation(exc) from exc
    except Exception as exc:  # noqa: BLE001
        rid = getattr(request.state, "request_id", None)
        logger.exception("import_failed request_id=%s", rid)
        raise HTTPException(
            status_code=500,
            detail=safe_error("Falha no processamento da importação.", "import_failed", rid),
        ) from exc
    return ImportPreviewOut(
        batch=ImportBatchOut.model_validate(batch),
        orders=PreviewRow(**preview["orders"]),
        payments=PreviewRow(**preview["payments"]),
        stock_movements=PreviewRow(**preview["stock_movements"]),
    )


@router.get("/imports/{batch_id}", response_model=ImportBatchOut)
def get_import(batch_id: int, request: Request, db: Session = Depends(get_db)) -> ImportBatchOut:
    if is_public_demo() and is_demo_batch_id(batch_id):
        return ImportBatchOut.model_validate(run_demo_stateless()["batch"])
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise _not_found(request) from exc
    return ImportBatchOut.model_validate(batch)


@router.get("/imports/{batch_id}/dashboard", response_model=DashboardOut)
def get_dashboard(batch_id: int, request: Request, db: Session = Depends(get_db)) -> DashboardOut:
    if is_public_demo() and is_demo_batch_id(batch_id):
        return DashboardOut(**run_demo_stateless()["dashboard"])
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise _not_found(request) from exc
    return DashboardOut(**build_dashboard(db, batch))


@router.get("/imports/{batch_id}/issues", response_model=list[IssueOut])
def list_issues(
    batch_id: int,
    request: Request,
    severity: str | None = Query(None),
    issue_type: str | None = Query(None),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    if is_public_demo() and is_demo_batch_id(batch_id):
        payload = run_demo_stateless()
        issues = payload["issues"]
        order_channel = {o.order_id: o.channel for o in payload["orders"]}
    else:
        try:
            batch = get_batch_or_404(db, batch_id)
        except LookupError as exc:
            raise _not_found(request) from exc
        issues = (
            db.query(ReconciliationIssue).filter(ReconciliationIssue.batch_id == batch.id).all()
        )
        order_channel = {
            o.order_id: o.channel
            for o in db.query(Order).filter(Order.batch_id == batch.id).all()
        }

    issues = _filter_issues(issues, severity, issue_type, status, channel, order_channel)
    issues = _sorted_issues(issues)
    return [IssueOut.model_validate(i) for i in issues]


@router.get("/issues/{issue_id}", response_model=IssueDetailOut)
def get_issue(issue_id: int, request: Request, db: Session = Depends(get_db)) -> IssueDetailOut:
    if is_public_demo():
        issue = get_demo_issue(issue_id)
        if issue is None:
            raise _not_found(request, f"Issue {issue_id} não encontrada.")
        base = IssueOut.model_validate(issue).model_dump()
        return IssueDetailOut(**base, history=[])
    issue = (
        db.query(ReconciliationIssue)
        .options(joinedload(ReconciliationIssue.history))
        .filter(ReconciliationIssue.id == issue_id)
        .first()
    )
    if not issue:
        raise _not_found(request, f"Issue {issue_id} não encontrada.")
    return IssueDetailOut.model_validate(issue)


@router.patch("/issues/{issue_id}", response_model=IssueDetailOut)
def patch_issue(
    issue_id: int,
    body: IssueUpdateIn,
    request: Request,
    db: Session = Depends(get_db),
) -> IssueDetailOut:
    if is_public_demo():
        raise HTTPException(
            status_code=403,
            detail=safe_error(
                "Mudança de status desabilitada na demo pública (modo somente-leitura).",
                "mutation_disabled",
            ),
        )
    issue = (
        db.query(ReconciliationIssue)
        .options(joinedload(ReconciliationIssue.history))
        .filter(ReconciliationIssue.id == issue_id)
        .first()
    )
    if not issue:
        raise _not_found(request, f"Issue {issue_id} não encontrada.")
    update_issue_status(db, issue, body.status, body.note)
    db.refresh(issue)
    issue = (
        db.query(ReconciliationIssue)
        .options(joinedload(ReconciliationIssue.history))
        .filter(ReconciliationIssue.id == issue_id)
        .first()
    )
    return IssueDetailOut.model_validate(issue)


@router.get("/imports/{batch_id}/export/issues.csv")
def export_issues_csv(batch_id: int, request: Request, db: Session = Depends(get_db)) -> StreamingResponse:
    if is_public_demo() and is_demo_batch_id(batch_id):
        issues = run_demo_stateless()["issues"]
        return _csv_response(issues_to_csv_rows(issues), batch_id)
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise _not_found(request) from exc
    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .order_by(ReconciliationIssue.id)
        .all()
    )
    return _csv_response(issues_to_csv_rows(issues), batch_id)


@router.get("/imports/{batch_id}/report", response_model=ReportOut)
def get_report(
    batch_id: int,
    request: Request,
    format: str = Query("markdown", pattern="^(markdown|html)$"),
    db: Session = Depends(get_db),
) -> ReportOut:
    if is_public_demo() and is_demo_batch_id(batch_id):
        md = run_demo_stateless()["report_md"]
        generated_at = datetime.now(timezone.utc)
        if format == "html":
            html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Relatório OpsLedger #{batch_id}</title>
<style>
body{{font-family:Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.5}}
h1{{font-size:1.6rem}} pre,code{{font-family:ui-monospace,monospace}}
</style></head>
<body><pre style="white-space:pre-wrap;font-family:inherit">{escape_html(md)}</pre></body></html>"""
            return ReportOut(batch_id=batch_id, format="html", content=html, generated_at=generated_at)
        return ReportOut(batch_id=batch_id, format="markdown", content=md, generated_at=generated_at)

    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise _not_found(request) from exc
    md = build_report_markdown(db, batch)
    generated_at = datetime.now(timezone.utc)
    if format == "html":
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Relatório OpsLedger #{batch_id}</title>
<style>
body{{font-family:Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.5}}
h1{{font-size:1.6rem}} pre,code{{font-family:ui-monospace,monospace}}
</style></head>
<body><pre style="white-space:pre-wrap;font-family:inherit">{escape_html(md)}</pre></body></html>"""
        return ReportOut(batch_id=batch_id, format="html", content=html, generated_at=generated_at)
    return ReportOut(batch_id=batch_id, format="markdown", content=md, generated_at=generated_at)
