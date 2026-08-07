"""Security helpers: safe errors, request ids, PII masking, output escaping.

These are defense-in-depth controls for the public demo surface. They never
leak stack traces, file paths, SQL or environment internals to clients.
"""

from __future__ import annotations

import html
import uuid
from typing import Any

from app.core.config import get_settings

# Characters that, at the start of a CSV cell, can be interpreted as a formula
# by spreadsheet software (CSV/formula injection).
_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r", "\n")

PII_MASK = "***"


def new_request_id() -> str:
    """Generate a correlation id for logs and client error responses."""
    return uuid.uuid4().hex


def is_public_demo() -> bool:
    """True when the API is serving the read-only public demo (no uploads/mutations)."""
    return get_settings().public_demo_mode


def escape_html(text: str) -> str:
    """Escape data-derived text before placing it inside HTML."""
    return html.escape(text or "", quote=True)


def sanitize_csv_cell(value: Any) -> str:
    """Neutralize formula-injection in a CSV cell.

    A cell whose first character is a formula trigger (= + - @ tab CR/NF) is
    prefixed with a single quote so spreadsheets treat it as literal text.
    """
    s = "" if value is None else str(value)
    if s and s[0] in _FORMULA_PREFIXES:
        return "'" + s
    return s


def mask_pii(value: Any) -> str:
    """Mask a PII field for public previews/logs."""
    if value is None or (isinstance(value, float) and value != value):  # NaN guard
        return ""
    text = str(value).strip()
    return PII_MASK if text else ""


def mask_pii_row(row: dict) -> dict:
    """Return a copy of a preview row with KNOWN sensitive fields masked.

    This is a deliberate allowlist of structured PII columns, not generic PII
    masking:
      - customer_name
      - customer_document_optional
    Free-text / operator-authored fields (description, recommended_action,
    notes, transaction_reference, and any imported extra columns) are NOT
    masked on purpose: they are not structured PII in this dataset and masking
    them would corrupt report/export fidelity. If the dataset ever ingests PII
    into free text, extend this allowlist intentionally rather than masking
    everything generically.
    """
    masked = dict(row)
    if "customer_name" in masked:
        masked["customer_name"] = mask_pii(masked["customer_name"])
    if "customer_document_optional" in masked:
        masked["customer_document_optional"] = mask_pii(masked["customer_document_optional"])
    return masked


def safe_error(message: str, code: str, request_id: str | None = None) -> dict:
    """Build a public-safe error detail dict. Never include internals."""
    detail: dict[str, Any] = {"message": message, "code": code}
    if request_id:
        detail["request_id"] = request_id
    return detail
