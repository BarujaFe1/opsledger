# Handoff — Portfolio Quality Pass (OpsLedger)

**Branch:** `chore/portfolio-quality-pass`  
**Date:** 2026-07-13

---

## O que foi encontrado

- MVP já forte (engine testável, demo, README bilingue, deploy Vercel).
- Bugs reais: loading infinito em IDs inválidos; ordenação lexicográfica de severidade no relatório; 500s vazando `str(exc)`; KPIs financeiros congelados após resolver issues; wizard sem retry; labels de status em inglês; sem CI; deps mortas (`zod`, `lucide-react`).

**Nota pré-pass:** ~7.2/10 — ver `docs/AUDIT_REPORT.md`.

---

## O que foi corrigido

| Item | Detalhe |
|------|---------|
| Invalid route IDs | `parsePositiveInt` + erro humano (não hang) |
| Report severity | Ordenação critical → low |
| Dashboard KPIs | Recalcula conciliado/divergência com issues `open`/`reviewing` |
| API 500 | Mensagens genéricas + logging |
| `reference_order_id` | Guard `pd.isna` |
| Wizard | Retry explícito em falha de demo |
| UX labels | Status/severidade em PT-BR |
| Nav | Link “Último batch” via sessionStorage |
| Relatório | Download `.md` |
| a11y básica | Skip link, `role=alert/status` |
| CI | `.github/workflows/ci.yml` |
| Deps | Removidos `zod` e `lucide-react` não usados |
| Scripts | `typecheck` no web |

---

## O que foi melhorado (docs)

- `docs/AUDIT_REPORT.md`
- `docs/architecture.md` (atualizado)
- `docs/TECHNICAL_DECISIONS.md`
- `docs/TESTING.md`
- `docs/deployment.md` (atualizado)
- `docs/HANDOFF.md` (este arquivo)
- README: seções “O que demonstra” + “Como apresentar em entrevista”

---

## Comandos rodados

```text
pytest -q                          → 13 passed
npm test                           → vitest (routing + utils)
npm run typecheck
npm run lint
npm run build                      → OK
```

---

## O que ainda falta (não bloqueante)

- Playwright smoke E2E.
- `Decimal`/`Numeric` para dinheiro.
- Postgres + Alembic + auth/workspaces.
- Rate limit na demo pública.
- `next/font` no lugar de `@import` Google Fonts.
- Recalcular também snapshot do `ImportBatch` (hoje o batch guarda o run; dashboard usa issues abertas).

---

## Riscos restantes

- Demo pública sem auth.
- SQLite `/tmp` efêmero no Vercel.
- Float money.

---

## Sugestões de portfólio

- Lead com Marina → demo → `engine.py` + pytest.
- Link canônico: https://opsledger-app.vercel.app
- Posicionar como Ops/Analytics Engineering, não fintech.

---

## Mensagem de commit sugerida

```text
chore: improve portfolio quality, docs, tests and stability
```

## Push

```bash
git push -u origin chore/portfolio-quality-pass
```
