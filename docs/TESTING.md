# Testing — OpsLedger

## Pirâmide atual

| Camada | Ferramenta | Onde | O que cobre |
|--------|------------|------|-------------|
| Unit (domínio) | Pytest | `apps/api/tests/` | 8 funções de regra (até 11 issue types) + Decimal money + happy path |
| API | Pytest + TestClient | mesmo | health, demo, dashboard, patch status, report, 404 |
| Unit (UI helpers) | Vitest | `apps/web/src/lib/*.test.ts` | formatação, labels, parse de IDs |
| E2E | Playwright | `apps/web/e2e/` | home → demo → dashboard → issues → relatório |

## Como rodar

### API
```bash
cd apps/api
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
pytest -q
```

### Web
```bash
cd apps/web
npm install
npm test
npm run typecheck
npm run lint
npm run build
```

### E2E (Playwright)
```bash
cd apps/web
npm run build
# Windows local (Chrome instalado):
set PLAYWRIGHT_CHANNEL=chrome
npm run test:e2e
# Ou baixar Chromium do Playwright:
npm run test:e2e:install
npm run test:e2e
```

Requer API Python em `apps/api/.venv` (ou `OPSLEDGER_API_PYTHON`).

### CI
GitHub Actions (`.github/workflows/ci.yml`) roda API + Web em PRs/`main`/`chore/**`. Job E2E opcional sobe uvicorn + `next start`.

## Convenções

- Novos bugs de regra → teste unitário na engine.
- Novos contratos de API → TestClient com assert de status + shape mínimo.
- Helpers de UI usados em rotas críticas → Vitest.
- Caminho crítico de fechamento → Playwright.
- Não mockar a engine nos testes de regra; use DataFrames mínimos.
