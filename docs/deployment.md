# Deploy

## Local (recomendado para demo)

Siga o README: API na porta 8000, web na 3000. Sem credenciais externas.

## Frontend (Vercel)

1. Importe o repositório e defina root `apps/web`.
2. Environment variable: `NEXT_PUBLIC_API_URL=https://<sua-api>`.
3. Build: `npm run build` / Output: Next padrão.

## Backend (Render / Railway)

1. Root directory: `apps/api`.
2. Build: `pip install -r requirements.txt`.
3. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
4. Variáveis:
   - `DATABASE_URL` (SQLite file persistente ou Postgres)
   - `CORS_ORIGINS` com a URL do frontend
5. Garanta que `data/demo` esteja no deploy (ou rode `python scripts/generate_demo_data.py` no build).

## Docker

```powershell
docker compose up --build
```

- API: `http://localhost:8000`
- Web: `http://localhost:3000`

Para Postgres, veja `docs/architecture.md`.

## Checklist pré-deploy

- [ ] `pytest` passando
- [ ] `/health` ok
- [ ] `/demo/run` ok
- [ ] CORS liberado para o domínio do front
- [ ] Sem `.env` com segredos commitado
- [ ] Screenshots atualizados (opcional)
