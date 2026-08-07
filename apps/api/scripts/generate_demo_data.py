"""Generate realistic synthetic demo CSVs for OpsLedger."""

from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
# Packaged with the API for Vercel; mirrored at repo root for docs/Docker.
DEMO_DIRS = [
    API_ROOT / "data" / "demo",
    REPO_ROOT / "data" / "demo",
]
DEMO_DIR = DEMO_DIRS[0]

PRODUCTS = [
    ("SKU-CAN-01", "Caneca Cerâmica 300ml", 39.9),
    ("SKU-CAM-02", "Camiseta Algodão Oversized", 89.9),
    ("SKU-BON-03", "Boné Aba Reta", 59.9),
    ("SKU-MOC-04", "Mochila Urbana 20L", 179.9),
    ("SKU-GAR-05", "Garrafa Térmica 500ml", 79.9),
    ("SKU-CAD-06", "Caderno Pontilhado A5", 34.9),
    ("SKU-FON-07", "Fone Bluetooth Compacto", 149.9),
    ("SKU-CAR-08", "Carregador USB-C 30W", 99.9),
    ("SKU-MEI-09", "Meia Esportiva Pack 3", 29.9),
    ("SKU-TOA-10", "Toalha Fitness Microfibra", 44.9),
]

CHANNELS_CANON = ["Shopify", "Mercado Livre", "WhatsApp", "Loja Física", "Instagram"]
CHANNEL_VARIANTS = {
    "WhatsApp": ["WhatsApp", "whatsapp", "zap", "wpp"],
    "Mercado Livre": ["Mercado Livre", "mercado livre", "ML"],
    "Shopify": ["Shopify", "shopify"],
    "Loja Física": ["Loja Física", "loja fisica"],
    "Instagram": ["Instagram", "instagram", "IG"],
}
METHODS = ["pix", "credit_card", "debit_card", "cash", "marketplace"]
FIRST_NAMES = [
    "Ana", "Bruno", "Carla", "Diego", "Elena", "Felipe", "Giulia", "Hugo",
    "Iris", "João", "Karen", "Lucas", "Marina", "Nicolas", "Olivia", "Pedro",
    "Rafaela", "Sofia", "Thiago", "Vera",
]
LAST_NAMES = [
    "Almeida", "Barbosa", "Costa", "Dias", "Esteves", "Ferreira", "Gomes",
    "Henrique", "Ibrahim", "Junqueira", "Klein", "Lima", "Moraes", "Nunes",
    "Oliveira", "Pereira", "Queiroz", "Rocha", "Silva", "Teixeira",
]


def _customer() -> str:
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def generate(seed: int = 42) -> None:
    random.seed(seed)
    DEMO_DIR.mkdir(parents=True, exist_ok=True)
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)

    orders: list[dict] = []
    payments: list[dict] = []
    stock: list[dict] = []

    # Initial stock in for all SKUs
    for idx, (sku, name, _) in enumerate(PRODUCTS, start=1):
        stock.append(
            {
                "movement_id": f"MOV-IN-{idx:03d}",
                "sku": sku,
                "movement_type": "in",
                "quantity": random.randint(40, 80),
                "movement_date": (base - timedelta(days=2)).isoformat(),
                "reference_order_id": "",
                "notes": f"Entrada inicial {name}",
            }
        )

    # Track intentional divergence order ids
    missing_payment_ids: list[str] = []
    amount_mismatch_ids: list[str] = []
    missing_stock_ids: list[str] = []
    duplicate_ids: list[str] = []

    for i in range(1, 151):
        oid = f"ORD-{i:04d}"
        sku, product_name, unit_price = random.choice(PRODUCTS)
        qty = random.randint(1, 3)
        discount = round(random.choice([0, 0, 0, 5, 10, 15]), 2)
        gross = round(unit_price * qty, 2)
        net = round(max(gross - discount, 0), 2)
        day = random.randint(0, 29)
        hour = random.randint(8, 21)
        order_date = base + timedelta(days=day, hours=hour, minutes=random.randint(0, 59))
        channel_canon = random.choice(CHANNELS_CANON)
        # Inject channel variants for ~12 orders
        if i in {11, 22, 33, 44, 55, 66, 77, 88, 99, 110, 121, 132}:
            channel = random.choice(CHANNEL_VARIANTS[channel_canon])
        else:
            channel = channel_canon

        status = random.choices(
            ["created", "paid", "shipped", "canceled", "returned"],
            weights=[4, 50, 38, 5, 3],
        )[0]

        orders.append(
            {
                "order_id": oid,
                "order_date": order_date.isoformat(),
                "customer_name": _customer(),
                "customer_document_optional": "",
                "channel": channel,
                "sku": sku,
                "product_name": product_name,
                "quantity": qty,
                "unit_price": unit_price,
                "gross_amount": gross,
                "discount_amount": discount,
                "net_amount": net,
                "status": status,
            }
        )

        # Default payment for paid/shipped
        if status in {"paid", "shipped"}:
            pay_amount = net
            pay_status = "paid"
            method = random.choice(METHODS)
            if channel_canon == "Mercado Livre":
                method = "marketplace"
            payments.append(
                {
                    "payment_id": f"PAY-{i:04d}",
                    "order_id": oid,
                    "paid_at": (order_date + timedelta(hours=random.randint(0, 6))).isoformat(),
                    "amount": pay_amount,
                    "method": method,
                    "status": pay_status,
                    "transaction_reference": f"TX-{10000 + i}",
                    "kind": "payment",
                }
            )
            # Default stock out
            stock.append(
                {
                    "movement_id": f"MOV-OUT-{i:04d}",
                    "sku": sku,
                    "movement_type": "out",
                    "quantity": qty,
                    "movement_date": (order_date + timedelta(hours=1)).isoformat(),
                    "reference_order_id": oid,
                    "notes": "Baixa automática",
                }
            )

    # --- Intentional divergences ---
    # 1) Missing payments (5)
    for oid in ["ORD-0005", "ORD-0017", "ORD-0031", "ORD-0048", "ORD-0063"]:
        for o in orders:
            if o["order_id"] == oid:
                o["status"] = "paid"
                missing_payment_ids.append(oid)
        payments[:] = [p for p in payments if p["order_id"] != oid]

    # 2) Orphan payments (3)
    for j, fake_oid in enumerate(["ORD-9991", "ORD-9992", "ORD-9993"], start=1):
        payments.append(
            {
                "payment_id": f"PAY-ORPH-{j}",
                "order_id": fake_oid,
                "paid_at": (base + timedelta(days=10 + j)).isoformat(),
                "amount": round(random.uniform(40, 180), 2),
                "method": "pix",
                "status": "paid",
                "transaction_reference": f"TX-ORPH-{j}",
                "kind": "payment",
            }
        )

    # 3) Amount mismatch (4) — force paid + payment first
    for oid, delta in [("ORD-0008", 25.0), ("ORD-0025", 8.5), ("ORD-0042", 35.0), ("ORD-0070", 3.2)]:
        order = next(o for o in orders if o["order_id"] == oid)
        order["status"] = "paid"
        existing = next((p for p in payments if p["order_id"] == oid and p["status"] == "paid"), None)
        if not existing:
            payments.append(
                {
                    "payment_id": f"PAY-MM-{oid}",
                    "order_id": oid,
                    "paid_at": order["order_date"],
                    "amount": round(order["net_amount"] - delta, 2),
                    "method": "pix",
                    "status": "paid",
                    "transaction_reference": f"TX-MM-{oid}",
                    "kind": "payment",
                }
            )
        else:
            existing["amount"] = round(float(order["net_amount"]) - delta, 2)
        # ensure stock out exists
        if not any(s.get("reference_order_id") == oid and s["movement_type"] == "out" for s in stock):
            stock.append(
                {
                    "movement_id": f"MOV-MM-{oid}",
                    "sku": order["sku"],
                    "movement_type": "out",
                    "quantity": order["quantity"],
                    "movement_date": order["order_date"],
                    "reference_order_id": oid,
                    "notes": "Baixa para mismatch demo",
                }
            )
        amount_mismatch_ids.append(oid)

    # 4) Multi-line order (2 SKUs) — demonstrates the item grain. Under the
    #    order/line model these two rows for the same order_id are a VALID
    #    multi-line order, not a duplicate (duplicate_line/header_conflict are
    #    exercised by the test suite instead).
    for src_oid, dup_oid in [("ORD-0012", "ORD-0012"), ("ORD-0039", "ORD-0039")]:
        src = next(o for o in orders if o["order_id"] == src_oid)
        dup = dict(src)
        dup["sku"] = PRODUCTS[(PRODUCTS.index(next(p for p in PRODUCTS if p[0] == src["sku"])) + 1) % len(PRODUCTS)][0]
        dup["product_name"] = next(p[1] for p in PRODUCTS if p[0] == dup["sku"])
        dup["unit_price"] = next(p[2] for p in PRODUCTS if p[0] == dup["sku"])
        dup["quantity"] = 1
        dup["gross_amount"] = dup["unit_price"]
        dup["discount_amount"] = 0
        dup["net_amount"] = dup["unit_price"]
        orders.append(dup)
        duplicate_ids.append(dup_oid)

    # 5) Missing stock out (5)
    for oid in ["ORD-0015", "ORD-0028", "ORD-0052", "ORD-0081", "ORD-0095"]:
        for o in orders:
            if o["order_id"] == oid:
                o["status"] = "shipped"
                missing_stock_ids.append(oid)
        stock[:] = [
            s
            for s in stock
            if not (s.get("reference_order_id") == oid and s["movement_type"] == "out")
        ]
        # ensure payment exists
        if not any(p["order_id"] == oid for p in payments):
            o = next(x for x in orders if x["order_id"] == oid)
            payments.append(
                {
                    "payment_id": f"PAY-FIX-{oid}",
                    "order_id": oid,
                    "paid_at": o["order_date"],
                    "amount": o["net_amount"],
                    "method": "pix",
                    "status": "paid",
                    "transaction_reference": f"TX-FIX-{oid}",
                    "kind": "payment",
                }
            )

    # 6) Negative stock — extra outs on one SKU
    target_sku = "SKU-MEI-09"
    for k in range(1, 6):
        stock.append(
            {
                "movement_id": f"MOV-NEG-{k}",
                "sku": target_sku,
                "movement_type": "out",
                "quantity": 30,
                "movement_date": (base + timedelta(days=20 + k)).isoformat(),
                "reference_order_id": "",
                "notes": "Ajuste manual excessivo (demo)",
            }
        )

    # Extra random stock adjustments / returns for volume (target 200-260)
    for k in range(1, 110):
        sku, name, _ = random.choice(PRODUCTS)
        mtype = random.choice(["in", "return", "adjustment"])
        qty = random.randint(1, 8) if mtype != "adjustment" else random.randint(-3, 5)
        stock.append(
            {
                "movement_id": f"MOV-XTRA-{k:03d}",
                "sku": sku,
                "movement_type": mtype,
                "quantity": qty if mtype == "adjustment" else abs(qty),
                "movement_date": (base + timedelta(days=random.randint(0, 29))).isoformat(),
                "reference_order_id": "",
                "notes": f"{mtype} {name}",
            }
        )

    # 7) Refund / chargeback / multi-payment scenarios (Fase 2b.1).
    #    Each scenario targets a *clean* paid order (exactly one default payment,
    #    not already part of another divergence) so the demo exercises the new
    #    cash-realization + refund-anomaly rules without disturbing the existing
    #    payment-matching divergences.
    refund_ids: list[str] = []
    chargeback_ids: list[str] = []
    over_refund_ids: list[str] = []
    multi_pay_ids: list[str] = []
    refund_without_payment_ids: list[str] = []

    _divergence_oids = (
        set(missing_payment_ids)
        | set(amount_mismatch_ids)
        | set(missing_stock_ids)
        | set(duplicate_ids)
    )

    def _clean_paid_order(exclude: set[str]) -> str | None:
        for o in orders:
            oid = o["order_id"]
            if o["status"] != "paid" or oid in _divergence_oids or oid in exclude:
                continue
            pays = [
                p
                for p in payments
                if p["order_id"] == oid and p.get("status") == "paid" and p.get("kind", "payment") == "payment"
            ]
            if len(pays) == 1:
                return oid
        return None

    # (a) Regular refund (Case B): order stays reconciled 100%; only cash net is reduced.
    oid = _clean_paid_order(exclude=set())
    if oid:
        o = next(x for x in orders if x["order_id"] == oid)
        amt = round(float(o["net_amount"]) * 0.4, 2)
        payments.append(
            {
                "payment_id": f"PAY-REF-{oid}",
                "order_id": oid,
                "paid_at": (datetime.fromisoformat(o["order_date"]) + timedelta(days=2)).isoformat(),
                "amount": amt,
                "method": "pix",
                "status": "refunded",
                "transaction_reference": f"TX-REF-{oid}",
                "kind": "refund",
            }
        )
        refund_ids.append(oid)

    # (b) Chargeback (operational exposure): full reversal, net_cash -> 0 for this order.
    oid = _clean_paid_order(exclude=set(refund_ids))
    if oid:
        o = next(x for x in orders if x["order_id"] == oid)
        payments.append(
            {
                "payment_id": f"PAY-CB-{oid}",
                "order_id": oid,
                "paid_at": (datetime.fromisoformat(o["order_date"]) + timedelta(days=3)).isoformat(),
                "amount": round(float(o["net_amount"]), 2),
                "method": "credit_card",
                "status": "charged_back",
                "transaction_reference": f"TX-CB-{oid}",
                "kind": "chargeback",
            }
        )
        chargeback_ids.append(oid)

    # (c) Over-refund (FINANCIAL): two refunds summing to > what was paid.
    oid = _clean_paid_order(exclude=set(refund_ids) | set(chargeback_ids))
    if oid:
        o = next(x for x in orders if x["order_id"] == oid)
        net_base = round(float(o["net_amount"]), 2)
        for k, ramt in enumerate([round(net_base * 0.6, 2), round(net_base * 0.7, 2)], start=1):
            payments.append(
                {
                    "payment_id": f"PAY-OVR-{oid}-{k}",
                    "order_id": oid,
                    "paid_at": (datetime.fromisoformat(o["order_date"]) + timedelta(days=1, hours=k)).isoformat(),
                    "amount": ramt,
                    "method": "pix",
                    "status": "refunded",
                    "transaction_reference": f"TX-OVR-{oid}-{k}",
                    "kind": "refund",
                }
            )
        over_refund_ids.append(oid)

    # (d) Multi-payment (split, fully covered): split the default payment into two.
    oid = _clean_paid_order(exclude=set(refund_ids) | set(chargeback_ids) | set(over_refund_ids))
    if oid:
        o = next(x for x in orders if x["order_id"] == oid)
        default_pay = next(p for p in payments if p["order_id"] == oid and p.get("status") == "paid")
        total = float(default_pay["amount"])
        p1 = round(total * 0.6, 2)
        p2 = round(total - p1, 2)
        default_pay["amount"] = p1
        default_pay["kind"] = "payment"
        payments.append(
            {
                "payment_id": f"PAY-SPLIT-{oid}",
                "order_id": oid,
                "paid_at": (datetime.fromisoformat(o["order_date"]) + timedelta(hours=2)).isoformat(),
                "amount": p2,
                "method": default_pay.get("method", "pix"),
                "status": "paid",
                "transaction_reference": f"TX-SPLIT-{oid}",
                "kind": "payment",
            }
        )
        multi_pay_ids.append(oid)

    # (e) Refund without payment (FINANCIAL): refund an order that has no payment.
    #     ORD-0005 is a missing_payment order (status "paid", payments removed),
    #     so a refund on it means cash went out that was never collected.
    for oid in ["ORD-0005"]:
        o = next(x for x in orders if x["order_id"] == oid)
        amt = round(float(o["net_amount"]) * 0.5, 2)
        payments.append(
            {
                "payment_id": f"PAY-RWP-{oid}",
                "order_id": oid,
                "paid_at": (base + timedelta(days=15)).isoformat(),
                "amount": amt,
                "method": "pix",
                "status": "refunded",
                "transaction_reference": f"TX-RWP-{oid}",
                "kind": "refund",
            }
        )
        refund_without_payment_ids.append(oid)

    # Pad payments into 140-155 range with pending/failed (non-approved) rows.
    # NOTE: kind defaults to "payment" here, so status must stay a valid
    # payment status (paid/pending/failed) — "refunded" would be an invalid
    # (kind, status) pair under the data contract and make the demo CSV fail.
    while len(payments) < 148:
        n = len(payments) + 1
        payments.append(
            {
                "payment_id": f"PAY-PAD-{n:04d}",
                "order_id": f"ORD-{(n % 150) + 1:04d}",
                "paid_at": (base + timedelta(days=n % 30)).isoformat(),
                "amount": round(random.uniform(20, 120), 2),
                "method": random.choice(METHODS),
                "status": random.choice(["pending", "failed"]),
                "transaction_reference": f"TX-PAD-{n}",
                "kind": "payment",
            }
        )

    orders_df = pd.DataFrame(orders)
    payments_df = pd.DataFrame(payments)
    stock_df = pd.DataFrame(stock)

    scenario = {
        "id": "monthly_closing_2026_06",
        "source_name": "demo:monthly_closing_2026_06",
        "label": "Fechamento mensal junho/2026",
        "period_start": "2026-06-01",
        "period_end": "2026-06-30",
        "seed": seed,
        "orders": len(orders_df),
        "payments": len(payments_df),
        "stock_movements": len(stock_df),
        "intentional": {
            "missing_payment": missing_payment_ids,
            "amount_mismatch": amount_mismatch_ids,
            "missing_stock": missing_stock_ids,
            "duplicates": duplicate_ids,
            "refund": refund_ids,
            "chargeback": chargeback_ids,
            "over_refund": over_refund_ids,
            "multi_payment": multi_pay_ids,
            "refund_without_payment": refund_without_payment_ids,
        },
    }

    for out_dir in DEMO_DIRS:
        out_dir.mkdir(parents=True, exist_ok=True)
        orders_df.to_csv(out_dir / "orders.csv", index=False)
        payments_df.to_csv(out_dir / "payments.csv", index=False)
        stock_df.to_csv(out_dir / "stock_movements.csv", index=False)
        (out_dir / "scenario.json").write_text(json.dumps(scenario, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote demo CSVs -> {out_dir}")

    print(f"orders: {len(orders_df)}")
    print(f"payments: {len(payments_df)}")
    print(f"stock_movements: {len(stock_df)}")
    print(f"missing_payment: {missing_payment_ids}")
    print(f"amount_mismatch: {amount_mismatch_ids}")
    print(f"missing_stock: {missing_stock_ids}")
    print(f"duplicates: {duplicate_ids}")
    print(f"refund: {refund_ids}")
    print(f"chargeback: {chargeback_ids}")
    print(f"over_refund: {over_refund_ids}")
    print(f"multi_payment: {multi_pay_ids}")
    print(f"refund_without_payment: {refund_without_payment_ids}")


if __name__ == "__main__":
    generate()
