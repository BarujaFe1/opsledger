# Changelog — portfolio elevation (2026-07 → 2026-08)

## Fase 2a (2026-08) — Grain + money policy + KPI decomposition

### Added
- `OrderLine` model (item grain: sku, quantity, unit_price, gross/discount/net) com `uq_order_line(order_id, line_id)`.
- `compute_kpis(orders, payments, issues)` — KPIs financeiros decompostos e sem double-counting.
- Campos de KPI no `DashboardOut` (schema) e no tipo `Dashboard` do front (`eligible_amount`, `missing_payment_amount`, `underpayment_amount`, `overpayment_amount`, `orphan_payment_amount`, `pending_excluded_amount`).
- 7 testes de Fase 2a: dedup multiline (missing_payment / missing_stock_out), invariante de `compute_kpis` (missing/orphan/under-over), exclusão de issues não-financeiras do impacto por canal, exposição da decomposição no dashboard.

### Changed
- `Order` vira cabeçalho (remove sku/quantidade/valor; mantém identidade/dimensão). Persistência grava `Order` + N `OrderLine` por pedido (`line_id = "{order_id}-L{seq}"`).
- `rule_missing_payment` e `rule_missing_stock_out` agregam por `order_id` (uma issue por pedido, soma de linhas) — elimina emissão duplicada por linha.
- `rule_missing_stock_out` usa quantidade/valor esperados = soma das linhas do pedido.
- Dashboard: impacto por canal restrito a `MONEY_ISSUE_TYPES` + dedup por `(issue_type, entity_id)`; `total_order_amount` expõe `eligible_amount`.
- `ImportBatch.total_amount` passa a refletir `eligible_amount`; `reconciled_amount`/`unreconciled_amount` vêm de `compute_kpis`.
- Relatório Markdown ganha seção "Decomposição de valor elegível" e data determinística (`batch.created_at`).
- Front (`batches/[batchId]`): card "Valor total de pedidos" → "Valor elegível (pagos/enviados)" + grade de KPIs (missing/under/over/orphan/pending-excluded) com texto do invariante.

### Verified
- Backend pytest: **47 passed** (40 existentes + 7 novos).
- `eligible == reconciled + missing + under + over` validado no dataset dourado (22478.5 = 21152.9 + 1179.1 + 146.5 + 0).
- `sum(impact por canal) == unreconciled_amount` (sem inflação) no dataset dourado (1325.6 = 1325.6).
- IDs dourados preservados (missing_payment, orphan PAY-ORPH-1..3, amount_mismatch, duplicate, missing_stock_out, negative_stock SKU-MEI-09).
- Frontend: `tsc --noEmit` limpo, `next lint` limpo, `vitest` 6 passed, `next build` ok.

## Added

- `app/core/money.py` — Decimal helpers (`money`, `money_sum`, `as_json_number`, tolerance).
- Scenario `demo:monthly_closing_2026_06` + `docs/scenarios/monthly_closing.md` + `scenario.json`.
- Playwright E2E: ingest → issues → report (`apps/web/e2e/closing-flow.spec.ts`).
- Regression tests `tests/test_money_decimal.py`.
- `docs/PORTFOLIO_HANDOFF.md`, `docs/screenshots/ROTEIRO.md`.

## Changed

- Money columns → SQLAlchemy `Numeric(18, 2)` / `Decimal` in models + engine.
- Dashboard/report paths use Decimal; JSON still exposes quantized numbers for the UI.
- Landing hero KPIs labeled illustrative (no fake R$ 48.2k as if live).
- ADR-005 updated: Decimal is the domain source of truth.
- Wizard success copy recognizes `demo:*` source names.

## Honest scope (unchanged)

- No auth / rate limit.
- Vercel demo persists on ephemeral SQLite `/tmp`.
- Not ERP / WMS / bank reconciliation.
