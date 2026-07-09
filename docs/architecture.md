# Arquitetura — OpsLedger

## Visão geral

OpsLedger é um monorepo com dois apps:

- `apps/web` — interface Next.js (App Router) para demo, upload, dashboard, issues e relatório.
- `apps/api` — API FastAPI com validação CSV (Pandas), persistência SQLAlchemy/SQLite e engine de reconciliação.

Dados demo ficam em `data/demo/`. Uploads processados são espelhados em `data/processed/`.

```txt
CSV (demo/upload)
    → validação de schema
    → ImportBatch (status processing → completed/failed)
    → persistência Order / Payment / StockMovement
    → engine de regras → ReconciliationIssue
    → dashboard / issues / export CSV / report
```

## Decisões de stack

| Decisão | Motivo |
|---------|--------|
| FastAPI + Pandas | Prototipagem rápida de regras tabulares e tipagem com Pydantic |
| SQLite | Zero setup para demo de portfólio; suficiente para MVP single-user |
| Next.js App Router | UI moderna, deploy simples na Vercel |
| Recharts + TanStack Table | KPIs e investigação sem over-engineering |
| Regras em funções puras | Testabilidade unitária sem banco |

## Fluxo de dados

1. `POST /api/demo/run` ou `POST /api/imports` lê/valida três CSVs.
2. `process_import` cria o batch, persiste linhas e executa `run_reconciliation`.
3. Issues são gravadas com tipo, severidade, impacto e ação recomendada.
4. Dashboard agrega KPIs do batch + contagens por severidade/tipo + impacto por canal.
5. `PATCH /issues/{id}` registra histórico em `IssueStatusHistory`.

## Limites do MVP

- Sem autenticação, multi-tenant ou RBAC.
- Estoque negativo é saldo **estimado** só com movimentos do batch.
- Sem conciliação bancária real nem integração marketplace.
- Um usuário local por vez é o cenário esperado.

## Migração para PostgreSQL

1. Defina `DATABASE_URL=postgresql+psycopg://user:pass@host:5432/opsledger`.
2. Instale driver (`psycopg[binary]`) e ajuste `connect_args` (remover `check_same_thread`).
3. Introduza Alembic para migrations a partir dos models SQLAlchemy.
4. Troque o volume SQLite no Docker por um serviço `postgres` no `docker-compose.yml`.
5. Mantenha a engine de reconciliação inalterada — ela opera em DataFrames, não no dialeto SQL.

Exemplo de serviço Compose:

```yaml
postgres:
  image: postgres:16
  environment:
    POSTGRES_DB: opsledger
    POSTGRES_USER: ops
    POSTGRES_PASSWORD: ops
  ports:
    - "5432:5432"
```

## Observabilidade e erros

A API não devolve stack trace cru ao frontend. Erros de CSV usam códigos (`missing_columns`, `invalid_csv`, etc.). Falhas inesperadas retornam `internal_error`.
