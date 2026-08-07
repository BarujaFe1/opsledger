"""Regression tests for Decimal money helpers."""

from decimal import Decimal

import pandas as pd

from app.core.money import AMOUNT_TOLERANCE, money
from app.reconciliation.engine import IssueDraft, rule_amount_mismatch


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


