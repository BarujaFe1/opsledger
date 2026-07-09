# Deploy

## Local (recomendado para demo)

Na raiz do repositório:

```powershell
.\start.bat
```

Ou manualmente: API na porta `8000`, web na `3000`. Sem credenciais externas.

- Health: `http://127.0.0.1:8000/api/health`
- Demo: `http://localhost:3000/wizard?mode=demo`

## Produção (Vercel — web + API no mesmo projeto)

O monorepo usa **Vercel Services** (`vercel.json`):

- `frontend` → `apps/web` (Next.js)
- `backend` → `apps/api` (FastAPI, entrypoint `app.main:app`)
- Rewrite: `/api/*` → backend; demais rotas → frontend

1. Importe o repositório (root = raiz do monorepo, **não** `apps/web`).
2. Não defina `NEXT_PUBLIC_API_URL` em produção (same-origin).
3. Opcional: `CORS_ORIGINS=https://opsledger-app.vercel.app` (já há defaults no código).
4. Deploy: `vercel --prod` (ou Git integration).
5. Alias canônico: `opsledger-app.vercel.app` (`opsledger.vercel.app` estava indisponível na conta).

SQLite em produção usa `/tmp/opsledger.db` (efêmero por cold start — adequado para demo pública one-click). Dados demo vão empacotados em `apps/api/data/demo/`.

## Backend separado (Render / Railway) — opcional

1. Root directory: `apps/api`.
2. Build: `pip install -r requirements.txt`.
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Variáveis:
   - `DATABASE_URL` (SQLite persistente ou Postgres)
   - `CORS_ORIGINS` com a URL do frontend
5. No frontend Vercel, defina `NEXT_PUBLIC_API_URL=https://<sua-api>` (rotas já incluem `/api/...`).

## Docker

```powershell
docker compose up --build
```

- API: `http://localhost:8000/api/health`
- Web: `http://localhost:3000`

Para Postgres, veja `docs/architecture.md`.

## Checklist pré-deploy

- [ ] `pytest` passando
- [ ] `/api/health` ok
- [ ] `/api/demo/run` ok
- [ ] CORS liberado para o domínio do front (ou same-origin)
- [ ] Sem `.env` com segredos commitado
- [ ] Screenshots atualizados (opcional)
