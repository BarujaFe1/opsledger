from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models import ReconciliationIssue
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
from app.services.csv_validation import CsvValidationError
from app.services.import_service import (
    build_dashboard,
    build_report_markdown,
    get_batch_or_404,
    issues_to_csv_rows,
    run_demo,
    run_upload,
    update_issue_status,
)

router = APIRouter()


def _http_from_validation(exc: CsvValidationError) -> HTTPException:
    return HTTPException(status_code=400, detail={"message": exc.message, "code": exc.code})


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse()


@router.post("/demo/run", response_model=ImportPreviewOut)
def demo_run(db: Session = Depends(get_db)) -> ImportPreviewOut:
    try:
        batch, preview = run_demo(db)
    except CsvValidationError as exc:
        raise _http_from_validation(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail={"message": "Falha ao rodar demo.", "code": "demo_failed"}) from exc
    return ImportPreviewOut(
        batch=ImportBatchOut.model_validate(batch),
        orders=PreviewRow(**preview["orders"]),
        payments=PreviewRow(**preview["payments"]),
        stock_movements=PreviewRow(**preview["stock_movements"]),
    )


@router.post("/imports", response_model=ImportPreviewOut)
async def create_import(
    orders: UploadFile = File(...),
    payments: UploadFile = File(...),
    stock_movements: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportPreviewOut:
    try:
        batch, preview = run_upload(
            db,
            orders.file,
            payments.file,
            stock_movements.file,
        )
    except CsvValidationError as exc:
        raise _http_from_validation(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=500,
            detail={"message": "Falha no processamento da importação.", "code": "import_failed"},
        ) from exc
    return ImportPreviewOut(
        batch=ImportBatchOut.model_validate(batch),
        orders=PreviewRow(**preview["orders"]),
        payments=PreviewRow(**preview["payments"]),
        stock_movements=PreviewRow(**preview["stock_movements"]),
    )


@router.get("/imports/{batch_id}", response_model=ImportBatchOut)
def get_import(batch_id: int, db: Session = Depends(get_db)) -> ImportBatchOut:
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc
    return ImportBatchOut.model_validate(batch)


@router.get("/imports/{batch_id}/dashboard", response_model=DashboardOut)
def get_dashboard(batch_id: int, db: Session = Depends(get_db)) -> DashboardOut:
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc
    return DashboardOut(**build_dashboard(db, batch))


@router.get("/imports/{batch_id}/issues", response_model=list[IssueOut])
def list_issues(
    batch_id: int,
    severity: str | None = Query(None),
    issue_type: str | None = Query(None),
    status: str | None = Query(None),
    channel: str | None = Query(None),
    db: Session = Depends(get_db),
) -> list[IssueOut]:
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc

    q = db.query(ReconciliationIssue).filter(ReconciliationIssue.batch_id == batch.id)
    if severity:
        q = q.filter(ReconciliationIssue.severity == severity.lower())
    if issue_type:
        q = q.filter(ReconciliationIssue.issue_type == issue_type)
    if status:
        q = q.filter(ReconciliationIssue.status == status.lower())

    issues = q.order_by(ReconciliationIssue.amount_impact.desc()).all()

    if channel:
        from app.models import Order

        order_ids = {
            o.order_id
            for o in db.query(Order).filter(Order.batch_id == batch.id, Order.channel == channel).all()
        }
        channel_lower = channel.lower()
        filtered = []
        for issue in issues:
            if issue.entity_type == "order" and issue.entity_id in order_ids:
                filtered.append(issue)
            elif issue.issue_type == "channel_standardization" and issue.entity_id.lower() == channel_lower:
                filtered.append(issue)
        issues = filtered

    return [IssueOut.model_validate(i) for i in issues]


@router.get("/issues/{issue_id}", response_model=IssueDetailOut)
def get_issue(issue_id: int, db: Session = Depends(get_db)) -> IssueDetailOut:
    issue = (
        db.query(ReconciliationIssue)
        .options(joinedload(ReconciliationIssue.history))
        .filter(ReconciliationIssue.id == issue_id)
        .first()
    )
    if not issue:
        raise HTTPException(status_code=404, detail={"message": f"Issue {issue_id} não encontrada.", "code": "not_found"})
    return IssueDetailOut.model_validate(issue)


@router.patch("/issues/{issue_id}", response_model=IssueDetailOut)
def patch_issue(issue_id: int, body: IssueUpdateIn, db: Session = Depends(get_db)) -> IssueDetailOut:
    issue = (
        db.query(ReconciliationIssue)
        .options(joinedload(ReconciliationIssue.history))
        .filter(ReconciliationIssue.id == issue_id)
        .first()
    )
    if not issue:
        raise HTTPException(status_code=404, detail={"message": f"Issue {issue_id} não encontrada.", "code": "not_found"})
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
def export_issues_csv(batch_id: int, db: Session = Depends(get_db)) -> StreamingResponse:
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc

    issues = (
        db.query(ReconciliationIssue)
        .filter(ReconciliationIssue.batch_id == batch.id)
        .order_by(ReconciliationIssue.id)
        .all()
    )
    rows = issues_to_csv_rows(issues)
    output = io.StringIO()
    fieldnames = [
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
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="opsledger_issues_batch_{batch_id}.csv"'},
    )


@router.get("/imports/{batch_id}/report", response_model=ReportOut)
def get_report(
    batch_id: int,
    format: str = Query("markdown", pattern="^(markdown|html)$"),
    db: Session = Depends(get_db),
) -> ReportOut | PlainTextResponse:
    try:
        batch = get_batch_or_404(db, batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail={"message": str(exc), "code": "not_found"}) from exc

    md = build_report_markdown(db, batch)
    if format == "html":
        html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head><meta charset="utf-8"><title>Relatório OpsLedger #{batch_id}</title>
<style>
body{{font-family:Georgia,serif;max-width:820px;margin:40px auto;padding:0 20px;color:#1a1a1a;line-height:1.5}}
h1{{font-size:1.6rem}} pre,code{{font-family:ui-monospace,monospace}}
</style></head>
<body><pre style="white-space:pre-wrap;font-family:inherit">{md}</pre></body></html>"""
        return ReportOut(
            batch_id=batch_id,
            format="html",
            content=html,
            generated_at=datetime.now(timezone.utc),
        )
    return ReportOut(
        batch_id=batch_id,
        format="markdown",
        content=md,
        generated_at=datetime.now(timezone.utc),
    )
