"""Regression tests for Decimal money helpers and compute_amounts."""

from decimal import Decimal

import pandas as pd

from app.core.money import AMOUNT_TOLERANCE, money
from app.reconciliation.engine import IssueDraft, compute_amounts, rule_amount_mismatch


def test_money_avoids_binary_float_trap():
    # Classic IEEE trap: 0.1 + 0.2 != 0.3 as float
    assert money("0.1") + money("0.2") == money("0.3")
    assert money(0.1) + money(0.2) == money("0.3")  # str() path still quantizes


def test_amount_mismatch_tolerance_is_decimal():
    orders = pd.DataFrame(
        [
            {
                "order_id": "ORD-1",
                "net_amount": "100.00",
                "channel": "Shopify",
                "status": "paid",
            }
        ]
    )
    payments = pd.DataFrame(
        [
            {
                "payment_id": "PAY-1",
                "order_id": "ORD-1",
                "amount": "100.04",
                "status": "paid",
            }
        ]
    )
    # 0.04 < 0.05 tolerance → no issue
    assert rule_amount_mismatch(orders, payments) == []

    payments.loc[0, "amount"] = "100.06"
    issues = rule_amount_mismatch(orders, payments)
    assert len(issues) == 1
    assert issues[0].amount_impact == money("0.06")
    assert issues[0].amount_impact > AMOUNT_TOLERANCE


def test_compute_amounts_quantizes_and_dedupes():
    orders = pd.DataFrame([{"order_id": "A", "net_amount": "10.10"}, {"order_id": "B", "net_amount": "20.20"}])
    drafts = [
        IssueDraft(
            issue_type="missing_payment",
            severity="high",
            entity_type="order",
            entity_id="A",
            title="t",
            description="d",
            recommended_action="a",
            amount_impact=money("10.10"),
        ),
        IssueDraft(
            issue_type="missing_payment",
            severity="high",
            entity_type="order",
            entity_id="A",
            title="t2",
            description="d",
            recommended_action="a",
            amount_impact=money("10.10"),
        ),
    ]
    total, reconciled, unreconciled = compute_amounts(orders, pd.DataFrame(), drafts)
    assert total == money("30.30")
    assert unreconciled == money("10.10")
    assert reconciled == money("20.20")
    assert isinstance(total, Decimal)
