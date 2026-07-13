# Testing — OpsLedger

## Pirâmide atual

| Camada | Ferramenta | Onde | O que cobre |
|--------|------------|------|-------------|
| Unit (domínio) | Pytest | `apps/api/tests/test_reconciliation.py` | 7 regras + happy path |
| API | Pytest + TestClient | mesmo arquivo | health, demo, dashboard, patch status, report, 404 |
| Unit (UI helpers) | Vitest | `apps/web/src/lib/*.test.ts` | formatação, labels, parse de IDs |
| E2E | — | — | Roadmap (Playwright): home → demo → dashboard → issue |

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

### CI
GitHub Actions (`.github/workflows/ci.yml`) roda API + Web em PRs/`main`/`chore/**`.

## Convenções

- Novos bugs de regra → teste unitário na engine.
- Novos contratos de API → TestClient com assert de status + shape mínimo.
- Helpers de UI usados em rotas críticas → Vitest.
- Não mockar a engine nos testes de regra; use DataFrames mínimos.
