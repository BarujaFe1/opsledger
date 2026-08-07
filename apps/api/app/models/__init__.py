from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


MoneyCol = Numeric(18, 2)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    source_name: Mapped[str] = mapped_column(String(120), default="upload")
    status: Mapped[str] = mapped_column(String(32), default="pending")
    total_orders: Mapped[int] = mapped_column(Integer, default=0)
    total_payments: Mapped[int] = mapped_column(Integer, default=0)
    total_stock_movements: Mapped[int] = mapped_column(Integer, default=0)
    total_issues: Mapped[int] = mapped_column(Integer, default=0)
    total_amount: Mapped[Decimal] = mapped_column(MoneyCol, default=Decimal("0.00"))
    reconciled_amount: Mapped[Decimal] = mapped_column(MoneyCol, default=Decimal("0.00"))
    unreconciled_amount: Mapped[Decimal] = mapped_column(MoneyCol, default=Decimal("0.00"))

    orders: Mapped[list["Order"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    payments: Mapped[list["Payment"]] = relationship(back_populates="batch", cascade="all, delete-orphan")
    stock_movements: Mapped[list["StockMovement"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    issues: Mapped[list["ReconciliationIssue"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )


class Order(Base):
    """Order header — one row per (batch_id, order_id).

    Money lives on OrderLine (item grain). The header carries only order-level
    identity/dimension columns. `order_id` is intentionally non-unique across
    batches (the same order re-imported lands in a new batch); within a batch it
    is unique (see uq_order_header). OrderLine.order_id is a logical link
    (indexed String), not a DB FK, because genuine duplicate lines are detected
    by rule_duplicate_order, not prevented at insert time.
    """

    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    order_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    customer_name: Mapped[str] = mapped_column(String(160))
    customer_document_optional: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    channel: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="orders")

    __table_args__ = (UniqueConstraint("batch_id", "order_id", name="uq_order_header"),)


class OrderLine(Base):
    """Item-grain line of an Order. Multiple lines may share one order_id.

    `line_id` is generated per (batch_id, order_id) as "{order_id}-L{seq}", so the
    same order re-imported in a different batch must not collide — hence the
    unique constraint spans batch_id as well.
    """

    __tablename__ = "order_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    line_id: Mapped[str] = mapped_column(String(64))
    sku: Mapped[str] = mapped_column(String(64), index=True)
    product_name: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price: Mapped[Decimal] = mapped_column(MoneyCol)
    gross_amount: Mapped[Decimal] = mapped_column(MoneyCol)
    discount_amount: Mapped[Decimal] = mapped_column(MoneyCol, default=Decimal("0.00"))
    net_amount: Mapped[Decimal] = mapped_column(MoneyCol)

    __table_args__ = (
        UniqueConstraint("batch_id", "order_id", "line_id", name="uq_order_line"),
    )


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    payment_id: Mapped[str] = mapped_column(String(64), index=True)
    order_id: Mapped[str] = mapped_column(String(64), index=True)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(MoneyCol)
    method: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(32), index=True)
    transaction_reference: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="payments")


class StockMovement(Base):
    __tablename__ = "stock_movements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    movement_id: Mapped[str] = mapped_column(String(64), index=True)
    sku: Mapped[str] = mapped_column(String(64), index=True)
    movement_type: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer)
    movement_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reference_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="stock_movements")


class ReconciliationIssue(Base):
    __tablename__ = "reconciliation_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    issue_type: Mapped[str] = mapped_column(String(64), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str] = mapped_column(Text)
    amount_impact: Mapped[Decimal] = mapped_column(MoneyCol, default=Decimal("0.00"))
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    batch: Mapped["ImportBatch"] = relationship(back_populates="issues")
    history: Mapped[list["IssueStatusHistory"]] = relationship(
        back_populates="issue", cascade="all, delete-orphan"
    )


class IssueStatusHistory(Base):
    __tablename__ = "issue_status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_issues.id"), index=True)
    previous_status: Mapped[str] = mapped_column(String(32))
    new_status: Mapped[str] = mapped_column(String(32))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    issue: Mapped["ReconciliationIssue"] = relationship(back_populates="history")
