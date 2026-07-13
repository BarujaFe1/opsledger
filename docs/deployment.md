# Deploy — OpsLedger

## Live Demo

**https://opsledger-app.vercel.app** → **Rodar demo**

> Nota: `opsledger.vercel.app` estava indisponível na conta; o alias canônico é `opsledger-app.vercel.app`.

## Local

```powershell
.\start.bat
```

Ou manualmente:

1. API: `uvicorn app.main:app --reload --port 8000` em `apps/api`
2. Web: `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` + `npm run dev` em `apps/web`

Health: `http://127.0.0.1:8000/api/health`

## Vercel (produção)

`vercel.json` define dois services:

- `frontend` → `apps/web` (Next.js)
- `backend` → `apps/api` (FastAPI `app.main:app`)
- Rewrite: `/api/(.*)` → backend

Checklist:

1. Root do projeto = raiz do monorepo (não `apps/web`).
2. Em produção, **não** definir `NEXT_PUBLIC_API_URL` (same-origin).
3. Desativar SSO/Deployment Protection se a demo for pública.
4. Demo CSVs em `apps/api/data/demo/`.

## Docker

```powershell
docker compose up --build
```

## Variáveis

Ver `.env.example`, `apps/api/.env.example`, `apps/web/.env.example`.

## Segurança da demo pública

- Sem autenticação (MVP).
- SQLite `/tmp` efêmero.
- Não enviar dados reais de clientes.
- 500s não vazam stack trace para o cliente.
