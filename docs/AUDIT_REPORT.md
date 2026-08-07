# OpsLedger — Audit Report (Portfolio Quality Pass)

**Branch:** `chore/portfolio-quality-pass`  
**Date:** 2026-07-13  
**Auditor role:** architecture · full-stack · QA · UX · DX · security · recruiter lens

---

## 1. Resumo executivo

OpsLedger já é um MVP de portfólio **acima da média**: domínio operacional crível (reconciliação pedidos/pagamentos/estoque), engine testável, demo one-click, README bilingue e deploy público no Vercel.

A revisão encontrou **gaps reais** que enfraquecem a credibilidade sob escrutínio de recrutador técnico: hang de loading em IDs inválidos, ordenação lexicográfica de severidade no relatório, vazamento parcial de exceções em 500, KPIs financeiros congelados após resolver issues, ausência de CI, testes de API/UI finos, e DX incompleta (lint/typecheck scripts).

**Nota atual (pré-pass):** **7.2 / 10**  
**Nota alvo deste pass:** **8.5+ / 10** (com CI, bugs P0/P1 corrigidos, docs e UX endurecidas)

---

## 2. Stack real

| Camada | Tecnologia |
|--------|------------|
| Web | Next.js 15 App Router, React 19, TypeScript, Tailwind, Recharts, TanStack Table |
| API | FastAPI, Pydantic v2, SQLAlchemy, Pandas, SQLite |
| Deploy | Vercel Services (`vercel.json`) — same-origin `/api/*` |
| Local | `start.bat` · Docker Compose |
| Testes | Pytest (engine + health/demo) · Vitest (utils) |

---

## 3. Principais riscos

| Risco | Severidade | Notas |
|-------|------------|-------|
| Demo pública sem auth | Alto (produto) / Aceitável (MVP) | Qualquer um pode POST `/api/demo/run` e mutar issues |
| SQLite em `/tmp` no Vercel | Médio | Efêmero por cold start — ok se narrado como demo |
| Dinheiro como `float` | Médio | Red flag em entrevista financeira |
| KPI ≠ status após resolve | Médio | Dashboard mostra snapshot do import |
| Sem CI | Médio | Testes existem mas não são enforced |
| Upload sem limite de tamanho | Médio | Abuse surface em demo pública |

---

## 4. Bugs encontrados (pré-correção)

1. **P0** — IDs inválidos (`/batches/abc`) deixam a UI em loading infinito (`Number` → `NaN`, early return).
2. **P0** — Relatório ordena severidade por string DESC (`medium > low > high > critical`).
3. **P1** — Respostas 500 incluem `str(exc)` (path/leak potencial).
4. **P1** — Demo com erro não oferece retry explícito no wizard.
5. **P1** — `reference_order_id` sem guard `pd.isna` na persistência.
6. **P2** — Labels de status em inglês na UI PT-BR.
7. **P2** — `sessionStorage` grava batch e não é lido na navegação.
8. **P2** — Dependências `zod` / `lucide-react` declaradas e não usadas.
9. **P2** — Comentário CORS em `.env.example` aponta domínio errado.
10. **P2** — Sem `.github/workflows/ci.yml`.

---

## 5. Quick wins

- Corrigir hang de ID inválido + retry de demo.
- Ordenação de severidade no relatório.
- Sanitizar 500s + logging básico.
- CI GitHub Actions (pytest + vitest + next build).
- Scripts `typecheck` / lint estável.
- Labels PT + link “último batch” no header.
- Docs: ARCHITECTURE, TECHNICAL_DECISIONS, TESTING, DEPLOYMENT, HANDOFF.
- README endurecido para entrevista.

---

## 6. Melhorias estruturais (pós-MVP / roadmap)

- `Decimal` / `Numeric` para dinheiro.
- Postgres + Alembic.
- Auth + workspace.
- Playwright smoke: home → demo → dashboard → issue → export.
- Rate limit / tamanho máximo de upload.
- Recálculo explícito de KPIs a partir de issues abertas (implementado neste pass no dashboard).

---

## 7. Plano de execução deste pass

1. Branch `chore/portfolio-quality-pass`
2. Corrigir bugs P0/P1 + testes
3. UX (empty/error/retry/nav/labels)
4. CI + scripts + env alignment
5. Docs técnicas + README + HANDOFF
6. Rodar pytest / vitest / build
7. Commit + push

---

## 8. Checklist final

- [x] Branch criada
- [x] Bugs P0/P1 corrigidos
- [x] Testes novos/atualizados
- [x] CI adicionada
- [x] Docs criadas/atualizadas
- [x] README portfolio-ready
- [x] Build/testes verdes
- [x] Commit + push

---

## 9. Olhar de recrutador

**Forte:** problema real, engine pura testável, jornada E2E, honestidade de escopo, demo viva.  
**Frágil:** float money, `/tmp`, sem CI (pré-pass), UI sem testes.  
**Narrativa recomendada:** Analytics Engineering / Ops Analytics — não “fintech platform”.

---

## 10. Addendum — Fase 2a (2026-08)

Após o merge da Fase 1 (PR #1, `a40d867`), a Fase 2a atacou os riscos estruturais de
**grain** e **integridade de KPIs financeiros** que o pass 1 deixou de fora por escopo.

### Riscos fechados nesta fase
| Risco (pré-Fase 2a) | Severidade | Resolução |
|---------------------|------------|-----------|
| `order == order_line` no modelo | Alto | `Order` (cabeçalho) + `OrderLine` (item); regras agregam por `order_id` |
| Duplicação de issues ao iterar linhas | Médio | `groupby("order_id")` em `missing_payment`/`missing_stock_out` |
| Double-counting financeiro no impacto por canal | Alto | impacto restrito a `MONEY_ISSUE_TYPES` + dedup `(issue_type, entity_id)` |
| KPIs sem decomposição (só elegível/divergência) | Médio | `compute_kpis`: missing/under/over/orphan/pending-excluded com invariante |

### Invariante central (novo, refinado em 2a.1)
`eligible_amount = reconciled_amount + missing_payment_amount + underpayment_amount`

(`overpayment_amount` e `orphan_payment_amount` são exposures payments-side, reportadas à parte — nunca subtraídas de `eligible`).

Validado no dataset dourado: `22478.5 = 21152.9 + 1179.1 + 146.5`.  
Impacto por canal sem inflação: `sum(impact) = 1325.6 == unreconciled_amount 1325.6` (overpayment excluído do impacto por canal).

### O que permanece fora de escopo (Fase 2b)
- Múltiplos pagamentos por pedido (split / parcial / excesso / refund) com modelo dedicado.
- Reconciliação de estoque com saldo de abertura + janela temporal + quantidade esperada/real.
- Versionamento de regras (`rule_id`, `versão`, `evidence`, `fingerprint`).

### Nota de verificação
CI deve rodar no SHA novo (não reusar verde do SHA anterior). Backend 47 passed; front
`tsc`/`lint`/`vitest`/`build` verdes. Merge via **merge commit** (não squash), por
convenção de histórico documentário do projeto.

---

## 11. Addendum — Fase 2a.1 (2026-08) — grain invariants

Revisão pós-merge da Fase 2a (PR #2, `ab8ce71`) identificou **4 defeitos reais de modelagem + 1 bug sutil de fórmula de overpayment**. Corrigidos em `feat/fase2a1-grain-invariants` (PR #3).

### Defeitos fechados
| # | Defeito (pré-2a.1) | Severidade | Resolução |
|---|---------------------|------------|-----------|
| 1 | 1 `Order` persistido por linha CSV (N headers → N linhas) | Alto | 1 `Order` por `(batch_id, order_id)` + N `OrderLine` |
| 2 | `uq_order_line(order_id, line_id)` quebra re-import em outro batch | Médio | constraints incluem `batch_id` (`uq_order_header`, `uq_order_line`) |
| 3 | `rule_duplicate_order` marcava qq multiline como duplicata (alta) | Alto | split 3 saídas: multiline legítimo / `duplicate_line` / `header_conflict` |
| 4 | `missing_stock_out` fazia `sku=("sku","first")`, perdendo SKUs | Médio | grain `(order_id, sku)`: 1 issue por SKU sem `out` |
| 5 | overpayment subtraído de `eligible` (semântica errada) | Médio | `overpayment`/`orphan_payment` são payments-side; `eligible = reconciled + missing + under` |

### Por que o verde da Fase 2a não pegou
O dataset dourado tem `over=0`; o invariante antigo `eligible = reconciled + missing + under + over` era trivialmente satisfeito, mascarando o bug de semântica. Os 6 testes obrigatórios de 2a.1 cobrem os grains e o caso `over≠0` explicitamente.

### Verificação
Backend 52 passed; front `tsc`/`lint`/`vitest` verdes; `next build` delegado à CI (ENOSPC local). Merge via merge commit.

