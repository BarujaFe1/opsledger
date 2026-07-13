from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str = "opsledger-api"


class ImportBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    source_name: str
    status: str
    total_orders: int
    total_payments: int
    total_stock_movements: int
    total_issues: int
    total_amount: float
    reconciled_amount: float
    unreconciled_amount: float


class IssueOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    batch_id: int
    issue_type: str
    severity: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    recommended_action: str
    amount_impact: float
    status: str
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None


class IssueStatusHistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    issue_id: int
    previous_status: str
    new_status: str
    changed_at: datetime
    note: Optional[str] = None


class IssueDetailOut(IssueOut):
    history: list[IssueStatusHistoryOut] = Field(default_factory=list)


class IssueUpdateIn(BaseModel):
    status: Literal["open", "reviewing", "resolved", "ignored"]
    note: Optional[str] = None


class SeverityCount(BaseModel):
    severity: str
    count: int


class TypeCount(BaseModel):
    issue_type: str
    count: int


class ChannelImpact(BaseModel):
    channel: str
    impact: float
    issues: int


class DashboardOut(BaseModel):
    batch_id: int
    total_orders: int
    total_order_amount: float
    reconciled_amount: float
    unreconciled_amount: float
    total_issues: int
    open_issues_count: int = 0
    issues_by_severity: list[SeverityCount]
    issues_by_type: list[TypeCount]
    top_channels_with_divergence: list[ChannelImpact]
    next_best_action: Optional[str] = None


class PreviewRow(BaseModel):
    rows: int
    columns: list[str]
    sample: list[dict]


class ImportPreviewOut(BaseModel):
    batch: ImportBatchOut
    orders: PreviewRow
    payments: PreviewRow
    stock_movements: PreviewRow


class ReportOut(BaseModel):
    batch_id: int
    format: str
    content: str
    generated_at: datetime


class ErrorOut(BaseModel):
    detail: str
    code: Optional[str] = None
