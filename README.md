# OpsLedger

Reconciliação operacional para pequenos e-commerces: importe pedidos, pagamentos e estoque, cruze com regras testáveis e saia com issues acionáveis + impacto financeiro.

## Problema

Pedidos, pagamentos e baixas de estoque vivem em planilhas diferentes. No fechamento diário/semanal aparecem:

- pedido marcado como pago sem pagamento;
- pagamento sem pedido;
- valores que não batem;
- duplicidades de exportação;
- venda sem baixa de estoque;
- saldo negativo estimado;
- canais escritos de formas diferentes (`whatsapp`, `zap`, `wpp`).

Sem um cruzamento sistemático, a operação perde dinheiro e confiança.

## Solução

OpsLedger é uma aplicação full-stack que:

1. carrega uma **demo sintética** ou **CSVs do usuário**;
2. valida schema mínimo;
3. executa uma **engine de reconciliação** com 7 regras;
4. mostra **dashboard executivo**, **issues filtráveis**, status, exportação CSV e relatório de fechamento.

Não é ERP, não é clone de e-commerce e não é dashboard decorativo.

## Stack

| Camada | Tecnologia |
|--------|------------|
| Frontend | Next.js (App Router), TypeScript, Tailwind CSS, Recharts, TanStack Table, Zod |
| Backend | FastAPI, Python 3.12, Pandas, Pydantic, SQLAlchemy |
| Banco | SQLite (MVP) — migração para PostgreSQL documentada |
| Testes | pytest (engine + API), Vitest (utils frontend) |
| Deploy | Frontend → Vercel; Backend → Render/Railway/Docker |

## Arquitetura

```txt
opsledger/
  apps/web/          # Next.js UI
  apps/api/          # FastAPI + engine
  data/demo/         # CSVs sintéticos
  data/processed/    # uploads processados
  docs/              # arquitetura, regras, dicionário, deploy
```

Fluxo: CSV → validação → `ImportBatch` → engine → `ReconciliationIssue` → dashboard / issues / export / report.

Detalhes em [`docs/architecture.md`](docs/architecture.md).

## Como rodar (local)

### Pré-requisitos

- Python 3.12+
- Node.js 20+
- (opcional) Docker

### 1) Backend

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/generate_demo_data.py
uvicorn app.main:app --reload --port 8000
```

Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

### 2) Frontend

```powershell
cd apps/web
npm install
copy .env.example .env.local
npm run dev
```

Abra [http://localhost:3000](http://localhost:3000).

### Docker (opcional)

```powershell
docker compose up --build
```

> No Docker, monte/garanta `data/demo` acessível à API (compose já mapeia `./data`).

## Como rodar testes

```powershell
# Backend
cd apps/api
.\.venv\Scripts\Activate.ps1
pytest -q

# Frontend (funções puras)
cd apps/web
npm test
```

## Como usar a demo

1. Abra a home e clique em **Rodar demo**.
2. O backend carrega `data/demo/*.csv`, valida e reconcilia.
3. Veja o preview → dashboard → Issues Register.
4. Altere status de uma issue, exporte CSV e gere o relatório.

Dados demo (seed fixo):

- ~150 pedidos (+ duplicatas intencionais);
- ~140–155 pagamentos;
- ~200–260 movimentações;
- 15–30 divergências propositalmente injetadas.

## Regras de reconciliação

1. `missing_payment` — pedido pago/enviado sem pagamento aprovado  
2. `orphan_payment` — pagamento aprovado sem pedido  
3. `amount_mismatch` — diferença > R$ 0,05  
4. `duplicate_order` — `order_id` repetido inconsistente  
5. `missing_stock_out` — venda sem baixa `out`  
6. `negative_stock` — saldo simulado negativo  
7. `channel_standardization` — variações de canal  

Detalhamento: [`docs/reconciliation-rules.md`](docs/reconciliation-rules.md).

## Screenshots

Adicione capturas em `docs/screenshots/` (opcional):

- `01-home.png`
- `02-wizard-demo.png`
- `03-dashboard.png`
- `04-issues.png`
- `05-issue-detail.png`

Enquanto não houver imagens, use a demo local como evidência visual.

## APIs

```txt
GET    /health
POST   /demo/run
POST   /imports
GET    /imports/{batch_id}
GET    /imports/{batch_id}/dashboard
GET    /imports/{batch_id}/issues
GET    /issues/{issue_id}
PATCH  /issues/{issue_id}
GET    /imports/{batch_id}/export/issues.csv
GET    /imports/{batch_id}/report
```

## Limitações honestas

- Sem autenticação / multiempresa.
- SQLite local (não pensado para concorrência alta).
- Estoque é **simulação de saldo** a partir dos movimentos do batch, não WMS.
- Sem integração real com marketplace/gateway.
- Canal no filtro de issues usa match simples no backend.

## Próximos passos

- Auth + workspaces por loja.
- PostgreSQL + migrations (Alembic).
- Regras configuráveis por tenant.
- Matching fuzzy de `order_id` entre canais.
- Alertas (Slack/e-mail) para issues críticas.
- Histórico de batches e comparação semana a semana.

## Portfólio

Texto pronto em [`HANDOFF_PORTFOLIO.md`](HANDOFF_PORTFOLIO.md).

## Licença

Projeto de portfólio — use e adapte livremente com atribuição.
