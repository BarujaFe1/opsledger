from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

import pandas as pd

AMOUNT_TOLERANCE = 0.05
AMOUNT_HIGH_THRESHOLD = 20.0

CHANNEL_ALIASES = {
    "whatsapp": "WhatsApp",
    "zap": "WhatsApp",
    "wpp": "WhatsApp",
    "wa": "WhatsApp",
    "shopify": "Shopify",
    "mercado livre": "Mercado Livre",
    "mercadolivre": "Mercado Livre",
    "ml": "Mercado Livre",
    "loja fisica": "Loja Física",
    "loja física": "Loja Física",
    "instagram": "Instagram",
    "ig": "Instagram",
}

APPROVED_PAYMENT_STATUSES = {"paid"}
FULFILLED_ORDER_STATUSES = {"paid", "shipped"}


@dataclass
class IssueDraft:
    issue_type: str
    severity: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    recommended_action: str
    amount_impact: float = 0.0
    channel: str | None = None


def _norm_channel(value: str) -> str:
    key = str(value or "").strip().lower()
    return CHANNEL_ALIASES.get(key, str(value or "").strip())


def _approved_payments(payments: pd.DataFrame) -> pd.DataFrame:
    if payments.empty:
        return payments
    return payments[payments["status"].astype(str).str.lower().isin(APPROVED_PAYMENT_STATUSES)].copy()


def rule_missing_payment(orders: pd.DataFrame, payments: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    approved = _approved_payments(payments)
    paid_orders = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
    paid_order_ids = set(approved["order_id"].astype(str)) if not approved.empty else set()
    for _, row in paid_orders.iterrows():
        oid = str(row["order_id"])
        if oid not in paid_order_ids:
            impact = float(row["net_amount"])
            issues.append(
                IssueDraft(
                    issue_type="missing_payment",
                    severity="high",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Pedido {oid} sem pagamento correspondente",
                    description=(
                        f"Pedido com status '{row['status']}' e valor líquido R$ {impact:.2f} "
                        "não possui pagamento aprovado."
                    ),
                    recommended_action="Verificar gateway, marketplace ou status do pedido.",
                    amount_impact=impact,
                    channel=str(row.get("channel", "")),
                )
            )
    return issues


def rule_orphan_payment(orders: pd.DataFrame, payments: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if payments.empty:
        return issues
    approved = _approved_payments(payments)
    order_ids = set(orders["order_id"].astype(str)) if not orders.empty else set()
    for _, row in approved.iterrows():
        oid = str(row["order_id"])
        if oid not in order_ids:
            impact = float(row["amount"])
            issues.append(
                IssueDraft(
                    issue_type="orphan_payment",
                    severity="high",
                    entity_type="payment",
                    entity_id=str(row["payment_id"]),
                    title=f"Pagamento {row['payment_id']} sem pedido correspondente",
                    description=(
                        f"Pagamento aprovado de R$ {impact:.2f} referencia order_id '{oid}' "
                        "inexistente na base de pedidos."
                    ),
                    recommended_action="Verificar ID de pedido, importação ou duplicidade de canal.",
                    amount_impact=impact,
                )
            )
    return issues


def rule_amount_mismatch(orders: pd.DataFrame, payments: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty or payments.empty:
        return issues
    approved = _approved_payments(payments)
    if approved.empty:
        return issues
    pay_sum = approved.groupby("order_id", as_index=False)["amount"].sum().rename(columns={"amount": "paid_sum"})
    # Use first order row per order_id for net amount comparison
    order_net = (
        orders.groupby("order_id", as_index=False)
        .agg(net_amount=("net_amount", "sum"), channel=("channel", "first"), status=("status", "first"))
    )
    merged = order_net.merge(pay_sum, on="order_id", how="inner")
    for _, row in merged.iterrows():
        diff = abs(float(row["net_amount"]) - float(row["paid_sum"]))
        if diff > AMOUNT_TOLERANCE:
            severity = "high" if diff >= AMOUNT_HIGH_THRESHOLD else "medium"
            oid = str(row["order_id"])
            issues.append(
                IssueDraft(
                    issue_type="amount_mismatch",
                    severity=severity,
                    entity_type="order",
                    entity_id=oid,
                    title=f"Divergência de valor no pedido {oid}",
                    description=(
                        f"Valor líquido do pedido R$ {float(row['net_amount']):.2f} vs "
                        f"pagamentos aprovados R$ {float(row['paid_sum']):.2f} "
                        f"(diferença R$ {diff:.2f})."
                    ),
                    recommended_action="Revisar desconto, frete, taxa ou reembolso.",
                    amount_impact=diff,
                    channel=str(row.get("channel", "")),
                )
            )
    return issues


def rule_duplicate_order(orders: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    grouped = orders.groupby("order_id")
    for oid, group in grouped:
        if len(group) <= 1:
            continue
        skus = set(group["sku"].astype(str))
        nets = set(round(float(x), 2) for x in group["net_amount"])
        inconsistent = len(skus) > 1 or len(nets) > 1
        if not inconsistent and len(group) > 1:
            # Exact duplicates still flagged as medium
            severity = "medium"
            desc = f"order_id '{oid}' aparece {len(group)} vezes com os mesmos valores."
        else:
            severity = "high"
            desc = (
                f"order_id '{oid}' aparece {len(group)} vezes com SKUs/valores inconsistentes "
                f"(SKUs={sorted(skus)}, nets={sorted(nets)})."
            )
        issues.append(
            IssueDraft(
                issue_type="duplicate_order",
                severity=severity,
                entity_type="order",
                entity_id=str(oid),
                title=f"Pedido duplicado {oid}",
                description=desc,
                recommended_action="Verificar duplicidade de exportação.",
                amount_impact=float(group["net_amount"].sum()),
                channel=str(group.iloc[0].get("channel", "")),
            )
        )
    return issues


def rule_missing_stock_out(orders: pd.DataFrame, stock: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    fulfilled = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
    outs = stock[stock["movement_type"].astype(str).str.lower() == "out"] if not stock.empty else stock
    out_keys = set()
    if not outs.empty:
        for _, row in outs.iterrows():
            ref = str(row.get("reference_order_id") or "")
            sku = str(row.get("sku") or "")
            if ref:
                out_keys.add((ref, sku))
    for _, row in fulfilled.iterrows():
        key = (str(row["order_id"]), str(row["sku"]))
        if key not in out_keys:
            issues.append(
                IssueDraft(
                    issue_type="missing_stock_out",
                    severity="medium",
                    entity_type="order",
                    entity_id=str(row["order_id"]),
                    title=f"Pedido {row['order_id']} sem baixa de estoque",
                    description=(
                        f"Pedido {row['status']} do SKU {row['sku']} não possui movimento 'out' "
                        "vinculado ao order_id."
                    ),
                    recommended_action="Revisar baixa de estoque.",
                    amount_impact=float(row["net_amount"]),
                    channel=str(row.get("channel", "")),
                )
            )
    return issues


def rule_negative_stock(stock: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if stock.empty:
        return issues
    df = stock.copy()
    df = df.sort_values(["sku", "movement_date", "movement_id"])
    balances: dict[str, int] = defaultdict(int)
    negative_skus: set[str] = set()
    for _, row in df.iterrows():
        sku = str(row["sku"])
        qty = int(row["quantity"])
        mtype = str(row["movement_type"]).lower()
        if mtype in {"in", "return"}:
            balances[sku] += abs(qty)
        elif mtype == "out":
            balances[sku] -= abs(qty)
        elif mtype == "adjustment":
            # signed quantity: positive increases, negative decreases
            balances[sku] += qty
        if balances[sku] < 0 and sku not in negative_skus:
            negative_skus.add(sku)
            issues.append(
                IssueDraft(
                    issue_type="negative_stock",
                    severity="critical",
                    entity_type="sku",
                    entity_id=sku,
                    title=f"Estoque negativo estimado para {sku}",
                    description=(
                        f"Saldo simulado do SKU {sku} ficou negativo ({balances[sku]}) "
                        "após processar movimentações em ordem cronológica."
                    ),
                    recommended_action="Revisar cadastro, contagem física ou baixa duplicada.",
                    amount_impact=0.0,
                )
            )
    return issues


def rule_channel_standardization(orders: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    raw_channels = sorted({str(c) for c in orders["channel"].dropna().unique()})
    buckets: dict[str, set[str]] = defaultdict(set)
    for ch in raw_channels:
        buckets[_norm_channel(ch)].add(ch)
    for canonical, variants in buckets.items():
        # Flag when aliases/variants collapse to same canonical and more than one spelling exists
        lowered = {v.lower().strip() for v in variants}
        alias_hits = any(v.lower().strip() in CHANNEL_ALIASES for v in variants)
        if len(variants) > 1 or (alias_hits and any(v.lower().strip() != canonical.lower() for v in variants)):
            if len(variants) == 1 and not alias_hits:
                continue
            # Only raise if there are non-canonical spellings or multiple variants
            non_canonical = [v for v in variants if v != canonical]
            if not non_canonical and len(variants) == 1:
                continue
            if len(variants) > 1 or non_canonical:
                sample = ", ".join(sorted(variants))
                issues.append(
                    IssueDraft(
                        issue_type="channel_standardization",
                        severity="low",
                        entity_type="batch",
                        entity_id=canonical or "channel",
                        title=f"Canal não padronizado: {canonical}",
                        description=f"Variações detectadas para o canal '{canonical}': {sample}.",
                        recommended_action="Padronizar dimensão de canal.",
                        amount_impact=0.0,
                        channel=canonical,
                    )
                )
    return issues


def run_reconciliation(
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    stock: pd.DataFrame,
) -> list[IssueDraft]:
    """Execute all reconciliation rules and return issue drafts."""
    drafts: list[IssueDraft] = []
    drafts.extend(rule_missing_payment(orders, payments))
    drafts.extend(rule_orphan_payment(orders, payments))
    drafts.extend(rule_amount_mismatch(orders, payments))
    drafts.extend(rule_duplicate_order(orders))
    drafts.extend(rule_missing_stock_out(orders, stock))
    drafts.extend(rule_negative_stock(stock))
    drafts.extend(rule_channel_standardization(orders))
    return drafts


def compute_amounts(
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    issues: Iterable[IssueDraft],
) -> tuple[float, float, float]:
    total_amount = float(orders["net_amount"].sum()) if not orders.empty else 0.0
    issue_list = list(issues)
    # Unreconciled = sum of financial impacts from open money-related issues (dedup by entity for missing/mismatch)
    money_types = {"missing_payment", "orphan_payment", "amount_mismatch"}
    unreconciled = 0.0
    seen: set[tuple[str, str]] = set()
    for issue in issue_list:
        if issue.issue_type in money_types:
            key = (issue.issue_type, issue.entity_id)
            if key not in seen:
                seen.add(key)
                unreconciled += float(issue.amount_impact)
    unreconciled = min(unreconciled, total_amount) if total_amount else unreconciled
    reconciled = max(total_amount - unreconciled, 0.0)
    return total_amount, reconciled, unreconciled
