# Cenário: fechamento mensal reproduzível — junho/2026

## Identidade

| Campo | Valor |
|-------|--------|
| `source_name` | `demo:monthly_closing_2026_06` |
| Período | 2026-06-01 → 2026-06-30 (UTC) |
| Seed | `42` (`scripts/generate_demo_data.py`) |
| CSVs | `apps/api/data/demo/{orders,payments,stock_movements}.csv` |
| Metadados | `apps/api/data/demo/scenario.json` |

## Persona

Marina fecha o mês omnichannel (Shopify, Mercado Livre, WhatsApp, Instagram, loja física) com três exports manuais.

## O que a demo injeta de propósito

Com seed fixo, o gerador cria ~150 pedidos e divergências intencionais:

- pedidos `paid`/`shipped` sem pagamento aprovado;
- pagamentos órfãos;
- mismatches de valor acima da tolerância de R$ 0,05;
- `order_id` duplicados inconsistentes;
- vendas sem `stock out`;
- SKU com saldo estimado negativo;
- canais não canônicos (`zap`, `wpp`, `ML`, …).

## Como reproduzir

```bash
cd apps/api
.venv\Scripts\python scripts/generate_demo_data.py   # seed=42
.venv\Scripts\python -c "from app.db.session import SessionLocal; from app.services.import_service import run_demo; db=SessionLocal(); b,_=run_demo(db); print(b.source_name, b.total_orders, b.total_issues)"
```

Ou na UI: **Rodar demo** → o batch nasce com `source_name=demo:monthly_closing_2026_06`.

## Contrato de honestidade

- Números do hero da home são **ilustrativos**; KPIs reais vêm deste batch.
- SQLite local persiste entre runs; no Vercel o DB em `/tmp` é efêmero.
- Dinheiro interno: `Decimal` quantizado (2 casas); JSON ainda serializa `number`.
