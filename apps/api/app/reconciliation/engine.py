from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

import pandas as pd

from app.core.money import (
    AMOUNT_HIGH_THRESHOLD,
    AMOUNT_TOLERANCE,
    ZERO,
    money,
    money_sum,
)
from app.services.csv_validation import PAYMENT_KINDS

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
# Issue types that drive the PAYMENT-MATCHING KPI decomposition
# (eligible = reconciled + missing + under). Refunds and chargebacks are NOT
# here: they belong to the separate CASH-REALIZATION dimension
# (net_cash = gross_paid - refunds - active_chargebacks) and must never
# retroactively mark an order as underpaid. They keep their own issue types
# (refund_without_payment / over_refund / chargeback) and are labeled financial
# vs operational via FINANCIAL_ISSUE_TYPES in import_service.
MONEY_ISSUE_TYPES = {
    "missing_payment",
    "orphan_payment",
    "amount_mismatch",
}

# Cash-flow sign per payment kind. `amount` is always the positive magnitude;
# refunds/chargebacks reduce realized revenue (negative sign).
KIND_SIGN = {"payment": 1, "refund": -1, "chargeback": -1}
# Status(es) under which each kind is considered "settled" (counts in netting).
SETTLED_STATUS_BY_KIND = {
    "payment": {"paid"},
    "refund": {"refunded"},
    "chargeback": {"charged_back"},
}


@dataclass
class IssueDraft:
    issue_type: str
    severity: str
    entity_type: str
    entity_id: str
    title: str
    description: str
    recommended_action: str
    amount_impact: Decimal = ZERO
    channel: str | None = None


def _norm_channel(value: str) -> str:
    key = str(value or "").strip().lower()
    return CHANNEL_ALIASES.get(key, str(value or "").strip())


def _approved_payments(payments: pd.DataFrame) -> pd.DataFrame:
    if payments.empty:
        return payments
    return payments[payments["status"].astype(str).str.lower().isin(APPROVED_PAYMENT_STATUSES)].copy()


def _netting_payments(payments: pd.DataFrame) -> pd.DataFrame:
    """Return settled payment/refund/chargeback rows with a `signed_amount`.

    A row is "settled" when its (kind, status) pair is in SETTLED_STATUS_BY_KIND.
    `signed_amount = KIND_SIGN[kind] * amount` so the resulting frame can be
    summed directly to obtain net cash flow per order. Rows whose `kind` is
    missing/blank default to "payment" (legacy CSVs without the column).
    """
    if payments.empty:
        return payments
    df = payments.copy()
    if "kind" not in df.columns:
        df["kind"] = "payment"
    df["kind"] = (
        df["kind"].astype(str).str.lower().str.strip().replace({"": "payment", "nan": "payment"})
    )
    df["status_norm"] = df["status"].astype(str).str.lower().str.strip()

    def _is_settled(row: pd.Series) -> bool:
        kind = str(row["kind"])
        if kind not in SETTLED_STATUS_BY_KIND:
            return False
        return str(row["status_norm"]) in SETTLED_STATUS_BY_KIND[kind]

    settled = df[df.apply(_is_settled, axis=1)].copy()
    if not settled.empty:
        settled["signed_amount"] = settled.apply(
            lambda r: KIND_SIGN.get(str(r["kind"]), 1) * money(r["amount"]), axis=1
        )
    return settled


def rule_missing_payment(orders: pd.DataFrame, payments: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    approved = _approved_payments(payments)
    paid_order_ids = set(approved["order_id"].astype(str)) if not approved.empty else set()
    # Aggregate at order grain: one issue per order_id, net = sum of its lines.
    fulfilled = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
    if fulfilled.empty:
        return issues
    order_net = fulfilled.groupby("order_id", as_index=False).agg(
        net_amount=("net_amount", "sum"),
        channel=("channel", "first"),
        status=("status", "first"),
    )
    for _, row in order_net.iterrows():
        oid = str(row["order_id"])
        if oid not in paid_order_ids:
            impact = money(row["net_amount"])
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
            impact = money(row["amount"])
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
    order_net = orders.groupby("order_id", as_index=False).agg(
        net_amount=("net_amount", "sum"),
        channel=("channel", "first"),
        status=("status", "first"),
    )
    merged = order_net.merge(pay_sum, on="order_id", how="inner")
    for _, row in merged.iterrows():
        net = money(row["net_amount"])
        paid = money(row["paid_sum"])
        diff = money(abs(net - paid))
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
                        f"Valor líquido do pedido R$ {net:.2f} vs "
                        f"pagamentos aprovados R$ {paid:.2f} "
                        f"(diferença R$ {diff:.2f})."
                    ),
                    recommended_action="Revisar desconto, frete, taxa ou reembolso.",
                    amount_impact=diff,
                    channel=str(row.get("channel", "")),
                )
            )
    return issues


def _header_key(row: pd.Series) -> tuple:
    """Canonical key of order-level (header) attributes used for conflict detection."""
    order_date = row["order_date"]
    try:
        order_date = pd.Timestamp(order_date).isoformat()
    except Exception:  # noqa: BLE001
        order_date = str(order_date)
    return (
        str(row["customer_name"]).strip().lower(),
        str(row.get("customer_document_optional", None) or "").strip().lower(),
        str(row["channel"]).strip().lower(),
        str(row["status"]).strip().lower(),
        order_date,
    )


def _line_key(row: pd.Series) -> tuple:
    """Canonical key of item-level (line) attributes used for duplicate detection."""
    return (
        str(row["sku"]).strip().lower(),
        str(row["product_name"]).strip().lower(),
        int(row["quantity"]),
        str(money(row["unit_price"])),
        str(money(row["gross_amount"])),
        str(money(row["discount_amount"])),
        str(money(row["net_amount"])),
    )


def rule_duplicate_order(orders: pd.DataFrame) -> list[IssueDraft]:
    """Classify repeated order_ids at item grain.

    Three outcomes per order_id with >1 line:
    - header_conflict: conflicting customer/channel/status/date across rows -> high.
    - duplicate_line: at least one line repeated verbatim -> high.
    - legitimate multi-line: consistent header + distinct lines -> valid (no issue).
    """
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    for oid, group in orders.groupby("order_id"):
        if len(group) <= 1:
            continue
        oid = str(oid)
        header_keys = {_header_key(r) for _, r in group.iterrows()}
        line_keys = [_line_key(r) for _, r in group.iterrows()]
        distinct_lines = set(line_keys)
        if len(header_keys) > 1:
            issues.append(
                IssueDraft(
                    issue_type="header_conflict",
                    severity="high",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Conflito de cabeçalho no pedido {oid}",
                    description=(
                        f"order_id '{oid}' aparece com atributos de cabeçalho conflitantes "
                        f"(cliente/canal/status/data): {len(header_keys)} variantes."
                    ),
                    recommended_action="Revisar exportação: um mesmo order_id deve ter identidade única.",
                    amount_impact=ZERO,
                    channel=str(group.iloc[0].get("channel", "")),
                )
            )
        elif len(distinct_lines) < len(line_keys):
            issues.append(
                IssueDraft(
                    issue_type="duplicate_line",
                    severity="high",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Linha duplicada no pedido {oid}",
                    description=(
                        f"order_id '{oid}' tem {len(line_keys) - len(distinct_lines)} "
                        f"linha(s) idêntica(s) repetida(s) (mesmo SKU/valor)."
                    ),
                    recommended_action="Remover linha duplicada da exportação do pedido.",
                    amount_impact=ZERO,
                    channel=str(group.iloc[0].get("channel", "")),
                )
            )
        # else: consistent header + distinct lines => legitimate multi-line order (valid).
    return issues


def rule_missing_stock_out(orders: pd.DataFrame, stock: pd.DataFrame) -> list[IssueDraft]:
    issues: list[IssueDraft] = []
    if orders.empty:
        return issues
    fulfilled = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
    if fulfilled.empty:
        return issues
    outs = stock[stock["movement_type"].astype(str).str.lower() == "out"] if not stock.empty else stock
    out_keys = set()
    if not outs.empty:
        for _, row in outs.iterrows():
            ref = str(row.get("reference_order_id") or "")
            sku = str(row.get("sku") or "")
            if ref:
                out_keys.add((ref, sku))
    # (order_id, sku) grain: expected qty/net = sum of that SKU's lines.
    grp = fulfilled.groupby(["order_id", "sku"], as_index=False).agg(
        quantity=("quantity", "sum"),
        net_amount=("net_amount", "sum"),
        channel=("channel", "first"),
        status=("status", "first"),
    )
    for _, row in grp.iterrows():
        oid = str(row["order_id"])
        sku = str(row["sku"])
        key = (oid, sku)
        if key not in out_keys:
            impact = money(row["net_amount"])
            issues.append(
                IssueDraft(
                    issue_type="missing_stock_out",
                    severity="medium",
                    entity_type="order_line",
                    entity_id=f"{oid}:{sku}",
                    title=f"Pedido {oid} (SKU {sku}) sem baixa de estoque",
                    description=(
                        f"Pedido {row['status']} do SKU {sku} (qtd {int(row['quantity'])}) "
                        "não possui movimento 'out' vinculado ao order_id."
                    ),
                    recommended_action="Revisar baixa de estoque.",
                    amount_impact=impact,
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
                    amount_impact=ZERO,
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
        lowered = {v.lower().strip() for v in variants}
        alias_hits = any(v.lower().strip() in CHANNEL_ALIASES for v in variants)
        if len(variants) > 1 or (alias_hits and any(v.lower().strip() != canonical.lower() for v in variants)):
            if len(variants) == 1 and not alias_hits:
                continue
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
                        amount_impact=ZERO,
                        channel=canonical,
                    )
                )
    return issues


def rule_refund_anomalies(orders: pd.DataFrame, payments: pd.DataFrame) -> list[IssueDraft]:
    """Detect refund/chargeback anomalies. Regular (well-explained) refunds and
    chargebacks stay SILENT here — they only net the KPIs via compute_kpis. Only
    the following anomalies become issues:

    - refund_without_payment (FINANCIAL): a settled refund/chargeback exists for
      an order that has no settled payment at all. The business gave money back
      it never collected.
    - over_refund (FINANCIAL): total refunded/charged back exceeds total paid for
      the order (amount_impact = refund_sum - paid_gross).
    - chargeback (OPERACIONAL — "valor associado"): a settled chargeback exists
      for an order that also has a settled payment. It nets the KPIs but is
      labeled as an operational/risk fact, not a financial divergence.
    """
    issues: list[IssueDraft] = []
    if orders.empty or payments.empty:
        return issues
    settled = _netting_payments(payments)
    if settled.empty:
        return issues
    fulfilled = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
    if fulfilled.empty:
        return issues
    order_net = fulfilled.groupby("order_id")["net_amount"].sum()
    order_channel = fulfilled.groupby("order_id")["channel"].first()

    # Per-order magnitude sums by kind.
    per_order: dict[str, dict[str, Decimal]] = defaultdict(
        lambda: {"paid": ZERO, "refund": ZERO, "chargeback": ZERO}
    )
    for _, row in settled.iterrows():
        oid = str(row["order_id"])
        kind = str(row["kind"])
        amt = money(row["amount"])
        if kind == "payment":
            per_order[oid]["paid"] += amt
        elif kind in ("refund", "chargeback"):
            per_order[oid]["refund"] += amt
            if kind == "chargeback":
                per_order[oid]["chargeback"] += amt

    for oid, net in order_net.items():
        oid = str(oid)
        info = per_order.get(oid)
        if not info or info["refund"] <= ZERO:
            continue
        paid_gross = info["paid"]
        refund_sum = info["refund"]
        channel = str(order_channel.get(oid, "") or "")
        if paid_gross <= ZERO:
            impact = money(refund_sum)
            issues.append(
                IssueDraft(
                    issue_type="refund_without_payment",
                    severity="high",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Reembolso sem pagamento no pedido {oid}",
                    description=(
                        f"Pedido com valor líquido R$ {money(net):.2f} possui reembolso/chargeback "
                        f"liquidado de R$ {impact:.2f} mas nenhum pagamento liquidado."
                    ),
                    recommended_action="Verificar estorno, gateway ou pedido cancelado indevidamente.",
                    amount_impact=impact,
                    channel=channel,
                )
            )
        elif refund_sum > paid_gross:
            impact = money(refund_sum - paid_gross)
            issues.append(
                IssueDraft(
                    issue_type="over_refund",
                    severity="high",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Reembolso acima do recebido no pedido {oid}",
                    description=(
                        f"Total reembolsado/chargeback de R$ {money(refund_sum):.2f} excede o recebido "
                        f"de R$ {money(paid_gross):.2f} (excesso R$ {impact:.2f})."
                    ),
                    recommended_action="Revisar política de reembolso e possível fraude.",
                    amount_impact=impact,
                    channel=channel,
                )
            )
        if info["chargeback"] > ZERO:
            issues.append(
                IssueDraft(
                    issue_type="chargeback",
                    severity="medium",
                    entity_type="order",
                    entity_id=oid,
                    title=f"Chargeback no pedido {oid}",
                    description=(
                        f"Pedido com valor líquido R$ {money(net):.2f} teve chargeback liquidado de "
                        f"R$ {money(info['chargeback']):.2f} (reduz o realizado, mas é tratado como "
                        "fato operacional)."
                    ),
                    recommended_action="Acionar disputa de chargeback junto à operadora.",
                    amount_impact=money(info["chargeback"]),
                    channel=channel,
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
    drafts.extend(rule_refund_anomalies(orders, payments))
    return drafts


def _mismatch_under_over(
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    order_ids: Iterable[str],
) -> dict[str, tuple[Decimal, Decimal]]:
    """Return {order_id: (under, over)} for the supplied order_ids with amount mismatch.

    `under` = net exceeds paid (order shortfall); `over` = paid exceeds net
    (excess cash). Both are magnitude-only; the caller decides the accounting
    bucket (over is payments-side, not subtracted from eligible).
    """
    result: dict[str, tuple[Decimal, Decimal]] = {}
    ids = set(order_ids)
    if not ids or orders.empty or payments.empty:
        return result
    approved = _approved_payments(payments)
    if approved.empty:
        return result
    pay_sum = approved.groupby("order_id", as_index=False)["amount"].sum().rename(
        columns={"amount": "paid_sum"}
    )
    order_net = orders.groupby("order_id", as_index=False)["net_amount"].sum()
    merged = order_net.merge(pay_sum, on="order_id", how="inner")
    for _, row in merged.iterrows():
        oid = str(row["order_id"])
        if oid not in ids:
            continue
        net = money(row["net_amount"])
        paid = money(row["paid_sum"])
        diff = net - paid
        if diff > AMOUNT_TOLERANCE:
            result[oid] = (money(diff), ZERO)
        elif -diff > AMOUNT_TOLERANCE:
            result[oid] = (ZERO, money(-diff))
        else:
            result[oid] = (ZERO, ZERO)
    return result


def _cash_realization(payments: pd.DataFrame) -> dict[str, Decimal]:
    """CASH-REALIZATION dimension (separate from PAYMENT MATCHING).

    Refunds and chargebacks are posterior cash reversals, not original-order
    coverage gaps, so they must NOT reduce `reconciled` or inflate `under`.
    They live here:

        gross_paid           = sum of settled normal payments (kind=payment)
        refunded_amount      = sum of settled refunds (kind=refund)
        active_chargeback_amount = sum of settled chargebacks (kind=chargeback)
                                   — current EXPOSURE, not necessarily a realized loss
        net_cash_amount      = gross_paid - refunded_amount - active_chargeback_amount

    net_cash can go negative when refunds/chargebacks exceed what was collected
    (e.g. refund_without_payment / over_refund) — that is the honest cash truth.
    """
    result = {
        "gross_paid_amount": ZERO,
        "refunded_amount": ZERO,
        "active_chargeback_amount": ZERO,
        "net_cash_amount": ZERO,
    }
    if payments.empty:
        return result
    settled = _netting_payments(payments)
    if settled.empty:
        return result
    for _, row in settled.iterrows():
        kind = str(row["kind"])
        amt = money(row["amount"])
        if kind == "payment":
            result["gross_paid_amount"] += amt
        elif kind == "refund":
            result["refunded_amount"] += amt
        elif kind == "chargeback":
            result["active_chargeback_amount"] += amt
    result["net_cash_amount"] = (
        result["gross_paid_amount"] - result["refunded_amount"] - result["active_chargeback_amount"]
    )
    return result


def compute_kpis(
    orders: pd.DataFrame,
    payments: pd.DataFrame,
    issues: Iterable,
) -> dict:
    """Decomposed, non-inflationary financial KPIs on the eligible (order) grain.

    Base = fulfilled orders (paid/shipped). Canceled/returned/created are
    `pending_excluded` and live outside the reconciliation base.
    Invariant: eligible = reconciled + missing + under.
    `overpayment` and `orphan_payment` are payments-side exposures (money
    received in excess of / without an order) and are reported separately, never
    subtracted from eligible. An overpaid order is fully matched (its net amount
    is covered); only the excess cash is an exposure.
    Under/over are derived from the data for OPEN amount_mismatch order_ids so
    the split stays consistent with the live issue set.
    """
    if orders.empty:
        eligible = ZERO
        pending_excluded = ZERO
    else:
        fulfilled = orders[orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
        excluded = orders[~orders["status"].astype(str).str.lower().isin(FULFILLED_ORDER_STATUSES)]
        eligible = (
            money_sum([money(v) for v in fulfilled["net_amount"].tolist()])
            if not fulfilled.empty
            else ZERO
        )
        pending_excluded = (
            money_sum([money(v) for v in excluded["net_amount"].tolist()])
            if not excluded.empty
            else ZERO
        )

    seen: set[tuple[str, str]] = set()
    missing = ZERO
    orphan = ZERO
    mismatch_order_ids: set[str] = set()
    open_statuses = {"open", "reviewing"}
    for issue in issues:
        st = getattr(issue, "status", "open")
        if st not in open_statuses:
            continue
        it = issue.issue_type
        if it not in MONEY_ISSUE_TYPES:
            continue
        key = (it, issue.entity_id)
        if key in seen:
            continue
        seen.add(key)
        amt = money(issue.amount_impact)
        if it == "missing_payment":
            missing += amt
        elif it == "orphan_payment":
            orphan += amt
        elif it == "amount_mismatch":
            mismatch_order_ids.add(str(issue.entity_id))

    under = ZERO
    over = ZERO
    if mismatch_order_ids:
        split = _mismatch_under_over(orders, payments, mismatch_order_ids)
        for u, o in split.values():
            under += u
            over += o

    # PAYMENT-MATCHING invariant: eligible == reconciled + missing + under.
    # Refunds/chargebacks deliberately do NOT enter `under` — they are a separate
    # cash-realization fact (see _cash_realization), not an original-coverage gap.
    unreconciled = money(missing + under)
    reconciled = money(max(eligible - unreconciled, ZERO))

    # CASH-REALIZATION dimension (independent of the matching invariant above).
    cash = _cash_realization(payments)

    return {
        "eligible_amount": eligible,
        "reconciled_amount": reconciled,
        "unreconciled_amount": unreconciled,
        "missing_payment_amount": missing,
        "underpayment_amount": under,
        "overpayment_amount": over,
        "orphan_payment_amount": orphan,
        "gross_paid_amount": cash["gross_paid_amount"],
        "refunded_amount": cash["refunded_amount"],
        "active_chargeback_amount": cash["active_chargeback_amount"],
        "net_cash_amount": cash["net_cash_amount"],
        "pending_excluded_amount": pending_excluded,
    }
