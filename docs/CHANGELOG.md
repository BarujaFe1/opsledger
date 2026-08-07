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
- `eligible == reconciled + missing + under` validado no dataset dourado (22478.5 = 21152.9 + 1179.1 + 146.5). `overpayment`/`orphan_payment` são exposures payments-side (over=0 no dataset dourado) e ficam de fora do `eligible`.
- `sum(impact por canal) == unreconciled_amount` (sem inflação) no dataset dourado (1325.6 = 1325.6).
- IDs dourados preservados (missing_payment, orphan PAY-ORPH-1..3, amount_mismatch, missing_stock_out, negative_stock SKU-MEI-09). Pedidos multiline ORD-0012/0039 passam a ser multiline legítimo (sem issue) sob o novo grain; `duplicate_line`/`header_conflict` substituem o antigo `duplicate_order` e não ocorrem no dataset dourado.
- Frontend: `tsc --noEmit` limpo, `next lint` limpo, `vitest` 6 passed, `next build` ok.

## Fase 2a.1 (2026-08) — Grain invariants (correção de modelagem pós-review)

### Added
- 6 testes obrigatórios de correção de grain/invariante: `test_legitimate_multiline_order_no_duplicate`, `test_duplicate_line_detected`, `test_header_conflict_detected`, `test_multiline_order_persists_one_header_two_lines`, `test_same_order_id_across_batches_persists_both`, `test_multiline_order_missing_stock_out_per_sku`, `test_overpayment_is_payment_side_exposure`.
- Helper `_mismatch_under_over(orders, payments, order_ids)` → `(under, over)` por pedido (deriva o split de `amount_mismatch`).

### Changed
- `rule_duplicate_order` → 3 saídas: `header_conflict` (alta), `duplicate_line` (alta), ou multiline legítimo (sem issue). Antigo `duplicate_order` removido.
- `rule_missing_stock_out` no grain `(order_id, sku)`: 1 issue por SKU sem `out` (`entity_id="{oid}:{sku}"`, `entity_type="order_line"`).
- Persistência: **1 `Order` por `(batch_id, order_id)`** (1ª linha vence o header) + N `OrderLine`; antes 1 `Order` por linha CSV.
- Constraints únicas incluem `batch_id`: `uq_order_header(batch_id, order_id)`, `uq_order_line(batch_id, order_id, line_id)`.
- `compute_kpis`: invariante corrigido para `eligible = reconciled + missing + under`; `overpayment`/`orphan_payment` são exposures payments-side (fora do `eligible`).
- Dashboard (impacto por canal): exclui overpayment — `amount_mismatch` conta só a parcela **under**.
- Front (`lib/utils.ts`): labels `duplicate_line: "Linha duplicada"`, `header_conflict: "Conflito de cabeçalho"`.
- `total_orders` agora no grain de header: `int(orders_df["order_id"].nunique())` nos 3 caminhos (batch concluído, batch `failed`, demo stateless). Antes `int(len(orders_df))` sobrecontava (contava linhas de pedido, não cabeçalhos).
- `compute_amounts` removido: função legada com definição contraditória de `reconciled` (ainda subtraía overpayment do conciliado) e sem call site relevante. `compute_kpis` é a única fonte financeira.

### Verified
- Backend pytest: **52 passed** (47 da Fase 2a + 5 líquidos de 2a.1).
- `eligible == reconciled + missing + under` no dataset dourado (22478.5 = 21152.9 + 1179.1 + 146.5); over=0.
- `test_overpayment_is_payment_side_exposure`: pedido 100 / pago 110 → `reconciled=100`, `overpayment_amount=10` (invariante sem over).
- `test_multiline_order_total_orders_grain`: upload multiline (2 SKUs) → `batch.total_orders == 1` e `dashboard.total_orders == 1` (não 2). `compute_amounts` removido (sem call site); backend segue **52 passed**.
- Frontend: `tsc`/`lint`/`vitest`(6) verdes; `next build` delegado à CI (ENOSPC local).

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
