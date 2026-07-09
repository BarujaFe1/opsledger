"""Generate realistic synthetic demo CSVs for OpsLedger."""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
DEMO_DIR = REPO_ROOT / "data" / "demo"

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

    # 4) Duplicate order (2 inconsistent)
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

    # Pad payments into 140-155 range with pending/failed (non-approved) rows
    while len(payments) < 148:
        n = len(payments) + 1
        payments.append(
            {
                "payment_id": f"PAY-PAD-{n:04d}",
                "order_id": f"ORD-{(n % 150) + 1:04d}",
                "paid_at": (base + timedelta(days=n % 30)).isoformat(),
                "amount": round(random.uniform(20, 120), 2),
                "method": random.choice(METHODS),
                "status": random.choice(["pending", "failed", "refunded"]),
                "transaction_reference": f"TX-PAD-{n}",
            }
        )

    orders_df = pd.DataFrame(orders)
    payments_df = pd.DataFrame(payments)
    stock_df = pd.DataFrame(stock)

    orders_df.to_csv(DEMO_DIR / "orders.csv", index=False)
    payments_df.to_csv(DEMO_DIR / "payments.csv", index=False)
    stock_df.to_csv(DEMO_DIR / "stock_movements.csv", index=False)

    print(f"orders: {len(orders_df)}")
    print(f"payments: {len(payments_df)}")
    print(f"stock_movements: {len(stock_df)}")
    print(f"missing_payment: {missing_payment_ids}")
    print(f"amount_mismatch: {amount_mismatch_ids}")
    print(f"missing_stock: {missing_stock_ids}")
    print(f"duplicates: {duplicate_ids}")


if __name__ == "__main__":
    generate()
