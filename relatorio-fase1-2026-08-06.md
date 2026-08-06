# Relatório — Fase 1 (P0): Hardening de Segurança e Demo Pública Stateless

**Data:** 2026-08-06
**Branch:** `chore/portfolio-quality-pass`
**Status:** ✅ Implementado, verificado, versionado em 5 commits e enviado em PR para `main`

---

## O que foi feito nesta resposta

Retomei a Fase 1 do plano aprovado. O código-fonte dos P0s já estava escrito; faltava
**escrever os testes de segurança, validar tudo, corrigir dois bugs da validação e fechar os
quatro gates de confirmação** solicitados na aprovação.

### 1. Suíte de testes de segurança (`apps/api/tests/test_security.py`) — NOVO
**40 testes no total do backend passam** (24 desta suíte + 16 existentes, sem regressão no
modo local). Cobre os controles P0:

- **Erros seguros (sem vazamento):** `safe_error` nunca inclui stack/SQL/caminhos; inclui
  `request_id` quando fornecido; `new_request_id` gera hex de 32 chars.
- **Escape de HTML:** `<img onerror=...>` vira `&lt;img ...&gt;`; aspas e `&` escapados.
- **Defesa contra injeção de fórmula em CSV:** células que começam com `= + - @ \t \r \n`
  ganham prefixo `'`; texto normal e `None` não são alterados.
- **Mascaramento de PII (allowlist):** `mask_pii` → `***` (e `""` para vazio/None/NaN);
  `mask_pii_row` mascara **apenas** `customer_name` e `customer_document_optional`.
- **CORS:** `allow_credentials=False` confirmado inspecionando o middleware registrado.
- **Demo pública read-only:** `GET /api/mode` → `{"public_demo": true}`; `POST /api/imports`
  → 403 `upload_disabled`; `PATCH /api/issues/{id}` → 403 `mutation_disabled`.
- **PII fora do preview:** `POST /api/demo/run` retorna `customer_name: "***"` e nenhum nome
  real do CSV vaza no corpo da resposta.
- **Escape de HTML no relatório (injeção):** `?format=html` injeta `<script>` no markdown e
  confirma que a saída contém `&lt;script&gt;` e NÃO `<script>`.
- **Erro 500 seguro:** handler global retorna `internal_error` + `request_id` e NÃO vaza
  `RuntimeError`/`SELECT`/caminhos.
- **Reconstrução stateless determinística:** `run_demo_stateless()` idêntico entre chamadas
  e após limpar o cache (simulação de cold start serverless).

### 2. Testes de fechamento dos gates de confirmação (adicionados a `test_security.py`)
- **Gate 2 — `test_mask_pii_row_only_masks_allowlist_fields`:** confirma que o mascaramento é
  uma allowlist explícita; campos de texto livre (`description`, `recommended_action`, `notes`,
  `transaction_reference`, `entity_id`, `title`, `severity`) **não** são mascarados, preservando
  a fidelidade de relatórios/exportações.
- **Gate 3 — `test_demo_stateless_cache_is_immutable`:** exatamente o snippet solicitado —
  `first["issues"][0].status = "resolved"` não corrompe o dataset cacheado; `second` e novas
  chamadas continuam com `status == "open"`.
- **Gate 4 — `test_local_export_csv_sanitizes_all_fields`:** injeta gatilhos de fórmula em
  **todos** os campos do CSV (id, entity_id, title, description, recommended_action, amount,
  note) e confirma que cada um recebe o prefixo `'` (sanitização aplicada a TODAS as exportações,
  locais e públicas).

### 3. Correção de bug — objetos sintéticos da demo (`import_service.py`)
Os objetos `ImportBatch`/`ReconciliationIssue` sintéticos (demo pública) não tinham
`created_at`/`updated_at` → falha de validação Pydantic (`ImportBatchOut`/`IssueOut`).
Adicionada constante `DEMO_CLOSED_AT` (fechamento de jun/2026, tz-aware UTC) e aplicada aos
objetos sintéticos. Mantém a saída determinística.

### 4. Correção de bug — frontend (`issues/[issueId]/page.tsx`)
Build do Next.js quebrou: `getMode` era usado mas não importado. Adicionado ao import de
`@/lib/api`. Build voltou a passar.

### 5. Correção de bug — imutabilidade do cache (Gate 3, `import_service.py`)
`run_demo_stateless()` agora retorna `copy.deepcopy(payload)`. Antes, o payload cacheado era
entregue por referência, permitindo que um caller mutasse o dataset compartilhado read-only.
Agora cada chamada recebe uma cópia defensiva; o cache é a única fonte de verdade imutável.

### 6. Verificação
- Backend: `pytest` → **40 passed** (24 da suíte de segurança/demo + 16 existentes, sem
  regressão no modo local).
- Frontend: `npm run build` → **compilado com sucesso** (Next.js 15.5.20, 5 rotas).

---

## Status dos Gates de Confirmação (solicitados na aprovação)

| Gate | O que verificar | Estado |
|------|----------------|--------|
| 1 — Vercel smoke test pós-push | Teste real de cold start serverless, cross-instância/concorrente | ⏳ PENDENTE (gate de publicação, roda após o push) |
| 2 — PII allowlist em campos de texto livre | `notes`, `description`, `transaction_reference` etc. NÃO mascarados | ✅ FECHADO (teste + docstring na allowlist) |
| 3 — Cache não mutável por referência | `second["issues"][0]["status"] == "open"` após mutar `first` | ✅ FECHADO (`copy.deepcopy` + teste) |
| 4 — Sanitização CSV em TODAS as exportações locais | Título, mensagem, evidência, recomendação, IDs, notas | ✅ FECHADO (teste cobre todos os campos) |

---

## Status dos entregáveis da Fase 1

| P0 | Arquivo | Estado |
|----|---------|--------|
| Infra de segurança + erros seguros | `core/security.py` (novo), `core/config.py`, `main.py` | ✅ |
| HTML escape + defesa CSV injection | `core/security.py`, `api/routes.py` | ✅ |
| CORS `allow_credentials=False` | `main.py` | ✅ |
| Demo pública stateless + PATCH 403 | `services/import_service.py`, `api/routes.py` | ✅ |
| Frontend read-only na demo pública | `lib/api.ts`, `issues/[issueId]/page.tsx`, `wizard/WizardClient.tsx` | ✅ |
| Testes de segurança e demo | `tests/test_security.py` | ✅ |

---

## Estrutura de commits (5 commits separados, conforme aprovado)

1. `feat(demo): make public showcase stateless and read-only`
   — `core/config.py` (public_demo_mode, demo_dataset_version) + `services/import_service.py` (engine stateless)
2. `feat(security): add safe errors and output sanitization`
   — `core/security.py` (novo), `main.py` (CORS off, request-id, 500 seguro), `api/routes.py` (safe errors, escape, sanitize, mask, 403)
3. `test(security): cover public demo and injection protections`
   — `tests/test_security.py` (novo, 24 testes)
4. `fix(web): enforce public demo restrictions in the interface`
   — `lib/api.ts`, `wizard/WizardClient.tsx`, `issues/[issueId]/page.tsx`
5. `docs: record phase 1 hardening results`
   — `relatorio-fase1-2026-08-06.md` (novo)

Push: `git push -u origin chore/portfolio-quality-pass` + PR aberta para `main`.

## Próximos passos
- **Gate 1:** rodar smoke test real no Vercel após o deploy da PR (cold start, cross-instância, concorrente, multi-região).
- **Fase 2 (recomendada):** correção de reconciliação de domínio — grão pedido vs item, Decimal/Numeric ponta a ponta, pagamentos divididos, exposição sem dupla contagem, saldo de estoque de abertura, consumo parcial/excesso, fingerprint/versionamento de regras.

---

*Arquivo de trabalho gerado automaticamente a cada resposta, conforme instruído. Pode ser apagado.*
