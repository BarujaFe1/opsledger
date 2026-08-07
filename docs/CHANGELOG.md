# Changelog — portfolio elevation (2026-07)

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
