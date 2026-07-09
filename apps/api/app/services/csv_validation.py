from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

ORDER_REQUIRED = [
    "order_id",
    "order_date",
    "customer_name",
    "channel",
    "sku",
    "product_name",
    "quantity",
    "unit_price",
    "gross_amount",
    "discount_amount",
    "net_amount",
    "status",
]

PAYMENT_REQUIRED = [
    "payment_id",
    "order_id",
    "paid_at",
    "amount",
    "method",
    "status",
]

STOCK_REQUIRED = [
    "movement_id",
    "sku",
    "movement_type",
    "quantity",
    "movement_date",
]


class CsvValidationError(Exception):
    def __init__(self, message: str, code: str = "csv_validation_error"):
        super().__init__(message)
        self.code = code
        self.message = message


def _read_csv(path_or_buffer: Any) -> pd.DataFrame:
    try:
        df = pd.read_csv(path_or_buffer)
    except Exception as exc:  # noqa: BLE001
        raise CsvValidationError(f"Não foi possível ler o CSV: {exc}", code="invalid_csv") from exc
    if df.empty:
        raise CsvValidationError("O arquivo CSV está vazio.", code="empty_csv")
    # normalize column names
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df


def _require_columns(df: pd.DataFrame, required: list[str], label: str) -> None:
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise CsvValidationError(
            f"Colunas ausentes em {label}: {', '.join(missing)}",
            code="missing_columns",
        )


def _parse_datetime_series(series: pd.Series, field: str) -> pd.Series:
    parsed = pd.to_datetime(series, errors="coerce", utc=True)
    if parsed.isna().any():
        bad = int(parsed.isna().sum())
        raise CsvValidationError(
            f"{bad} valor(es) inválido(s) em '{field}'. Use ISO 8601 ou YYYY-MM-DD.",
            code="invalid_datetime",
        )
    return parsed


def validate_orders(path_or_buffer: Any) -> pd.DataFrame:
    df = _read_csv(path_or_buffer)
    _require_columns(df, ORDER_REQUIRED, "orders")
    if "customer_document_optional" not in df.columns:
        df["customer_document_optional"] = None
    df["order_date"] = _parse_datetime_series(df["order_date"], "order_date")
    for col in ["quantity"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in ["unit_price", "gross_amount", "discount_amount", "net_amount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    if df[["quantity", "unit_price", "gross_amount", "discount_amount", "net_amount"]].isna().any().any():
        raise CsvValidationError("Valores numéricos inválidos em orders.", code="invalid_number")
    df["status"] = df["status"].astype(str).str.lower().str.strip()
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["sku"] = df["sku"].astype(str).str.strip()
    df["channel"] = df["channel"].astype(str).str.strip()
    return df


def validate_payments(path_or_buffer: Any) -> pd.DataFrame:
    df = _read_csv(path_or_buffer)
    _require_columns(df, PAYMENT_REQUIRED, "payments")
    if "transaction_reference" not in df.columns:
        df["transaction_reference"] = None
    df["paid_at"] = _parse_datetime_series(df["paid_at"], "paid_at")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if df["amount"].isna().any():
        raise CsvValidationError("Valores numéricos inválidos em payments.", code="invalid_number")
    df["status"] = df["status"].astype(str).str.lower().str.strip()
    df["method"] = df["method"].astype(str).str.lower().str.strip()
    df["order_id"] = df["order_id"].astype(str).str.strip()
    df["payment_id"] = df["payment_id"].astype(str).str.strip()
    return df


def validate_stock(path_or_buffer: Any) -> pd.DataFrame:
    df = _read_csv(path_or_buffer)
    _require_columns(df, STOCK_REQUIRED, "stock_movements")
    if "reference_order_id" not in df.columns:
        df["reference_order_id"] = None
    if "notes" not in df.columns:
        df["notes"] = None
    df["movement_date"] = _parse_datetime_series(df["movement_date"], "movement_date")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    if df["quantity"].isna().any():
        raise CsvValidationError("Valores numéricos inválidos em stock_movements.", code="invalid_number")
    df["movement_type"] = df["movement_type"].astype(str).str.lower().str.strip()
    df["sku"] = df["sku"].astype(str).str.strip()
    df["movement_id"] = df["movement_id"].astype(str).str.strip()
    df["reference_order_id"] = df["reference_order_id"].apply(
        lambda x: None if pd.isna(x) or str(x).strip() == "" else str(x).strip()
    )
    return df


def preview_df(df: pd.DataFrame, limit: int = 5) -> dict:
    sample = df.head(limit).copy()
    for col in sample.columns:
        if pd.api.types.is_datetime64_any_dtype(sample[col]):
            sample[col] = sample[col].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    records = sample.where(pd.notnull(sample), None).to_dict(orient="records")
    return {"rows": int(len(df)), "columns": list(df.columns), "sample": records}


def to_naive_utc(dt: datetime | pd.Timestamp) -> datetime:
    ts = pd.Timestamp(dt)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.to_pydatetime()
