# PORTFOLIO_HANDOFF — OpsLedger (elevação 2026-07)

**Branch:** `chore/portfolio-quality-pass`  
**Autor:** Felipe Alírio Baruja  
**Demo canônica:** https://opsledger-one.vercel.app  
**Repo:** https://github.com/BarujaFe1/opsledger

---

## Resumo

Elevação do MVP de reconciliação operacional (~8.5 após quality pass) com foco em **rigor monetário (Decimal)**, **cenário de fechamento mensal reproduzível**, **E2E Playwright do caminho crítico** e **documentação honesta de portfólio**.

## Before → After

| Dimensão | Antes | Depois |
|----------|-------|--------|
| Dinheiro | `float` / `Float` | `Decimal` + `Numeric(18,2)` + `app/core/money.py` |
| Demo | `source_name=demo` | `demo:monthly_closing_2026_06` + `scenario.json` |
| E2E | Ausente | Playwright: ingest → issues → report |
| Hero KPIs | Números inventados sem label | Mock explícito “ilustração” |
| ADR-005 | Float temporário | Decimal como fonte de verdade |
| CI | pytest + web gates | + job E2E |
| Testes API | 13 | 16 (+ money Decimal) |

## Bugs / inconsistências corrigidos neste pass

- Hero com R$ 48.2k / 24 issues como se fossem live.
- Claim README de Zod (deps já removidas).
- Claim float money desatualizado após migração.
- CORS sem portas 3100 (quebrava Playwright).
- Vitest coletava specs Playwright (`e2e/`).

## Comandos de evidência

```text
cd apps/api && .venv\Scripts\python -m pytest -q     → 16 passed
cd apps/web && npm test                              → 6 passed
cd apps/web && npm run lint && npm run typecheck && npm run build
cd apps/web && set PLAYWRIGHT_CHANNEL=chrome && npm run test:e2e  → 1 passed
```

## Limitações remanescentes

- Sem auth / rate limit (lab demo).
- Persistência Vercel = SQLite `/tmp` efêmero.
- JSON money ainda é `number` (quantizado) na borda HTTP.
- Deploy público pode servir build anterior até redeploy da branch.
- Screenshots em `assets/screenshots/` podem refletir UI pré-hero-honest — re-capturar com [`docs/screenshots/ROTEIRO.md`](screenshots/ROTEIRO.md).

## Próximos passos (honestos)

1. Redeploy Vercel a partir deste tip.
2. Postgres + Alembic se claimar durabilidade.
3. Auth mínima + rate limit na demo pública.
4. Recaptura de screenshots pós-hero.

## Recomendação de portfólio

**Selecionado / quase destaque** para Analytics Engineering e full-stack analítico — desde que a demo live esteja no tip e as limitações permaneçam explícitas. Não vender como produto enterprise ou produção multi-tenant.
