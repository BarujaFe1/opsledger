"""Money helpers — Decimal with cent quantization (BRL-style).

Never construct Decimal from a binary float. Prefer str/int inputs.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

TWOPLACES = Decimal("0.01")
ZERO = Decimal("0.00")
AMOUNT_TOLERANCE = Decimal("0.05")
AMOUNT_HIGH_THRESHOLD = Decimal("20.00")


def money(value: Any) -> Decimal:
    """Parse a money value into a quantized Decimal (2 places, half-up)."""
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid money value")
    if isinstance(value, int):
        return Decimal(value).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    # Avoid Decimal(float(...)) — use string form of the display value.
    text = str(value).strip().replace(",", ".")
    if text == "" or text.lower() in {"nan", "none", "null"}:
        return ZERO
    return Decimal(text).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def money_sum(values: list[Decimal] | tuple[Decimal, ...]) -> Decimal:
    total = ZERO
    for v in values:
        total += money(v)
    return money(total)


def as_json_number(value: Decimal | float | int | None) -> float:
    """Serialize quantized money for JSON (FE keeps number + formatBRL)."""
    return float(money(value))
