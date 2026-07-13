# Architecture — OpsLedger

## Visão geral

OpsLedger é um monorepo com dois apps desacoplados:

| App | Path | Papel |
|-----|------|-------|
| Web | `apps/web` | Next.js App Router — landing, wizard, dashboard, issues |
| API | `apps/api` | FastAPI — validação CSV, persistência, engine, export/report |

```txt
CSV (demo/upload)
  → validação de schema
  → ImportBatch
  → Order / Payment / StockMovement
  → engine (7 regras) → ReconciliationIssue
  → dashboard / issues / status / CSV / relatório
```

## Fronteiras

- **Domínio puro:** `apps/api/app/reconciliation/engine.py` — funções sobre DataFrames, sem I/O.
- **Aplicação:** `services/import_service.py` — orquestra persistência + engine.
- **API:** `api/routes.py` — HTTP, códigos de erro estáveis.
- **UI:** `apps/web/src` — consome `/api/*` (same-origin em produção).

## Deploy

- **Vercel Services** (`vercel.json`): frontend Next + backend FastAPI; rewrite `/api/*` → backend.
- **SQLite local** em `apps/api/opsledger.db`; em Vercel usa `/tmp` (demo efêmera).
- Demo CSVs empacotados em `apps/api/data/demo/` (espelho em `data/demo/`).

## Limites honestos do MVP

- Sem autenticação / multi-tenant.
- Estoque = saldo simulado do batch (não WMS).
- Dinheiro ainda em `float` (trade-off de velocidade; roadmap: Decimal).
- Sem conciliação bancária nem integrações de marketplace.

## Migração Postgres (v1.1)

1. `DATABASE_URL=postgresql+psycopg://…`
2. Alembic a partir dos models SQLAlchemy.
3. Remover dependência de `/tmp` para qualquer claim de durabilidade.
