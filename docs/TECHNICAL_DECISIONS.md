# Technical Decisions — OpsLedger

## ADRs leves

### ADR-001 — Engine em Pandas puro
**Decisão:** regras de reconciliação como funções puras sobre DataFrames.  
**Por quê:** testabilidade unitária sem banco; portabilidade futura para jobs de warehouse.  
**Trade-off:** não há SQL incremental; batch inteiro em memória (ok para MVP ~centenas de linhas).

### ADR-002 — SQLite no MVP / `/tmp` no Vercel
**Decisão:** zero setup para demo de portfólio; Vercel usa filesystem efêmero.  
**Por quê:** one-click demo pública sem Postgres obrigatório.  
**Trade-off:** dados não sobrevivem cold start; nunca vender como multi-user prod.

### ADR-003 — Same-origin `/api` no Vercel
**Decisão:** prefixar FastAPI com `/api` e rewrite no `vercel.json`.  
**Por quê:** CORS simples, URL única para portfólio (`opsledger-app.vercel.app`).  
**Trade-off:** local ainda usa `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000`.

### ADR-004 — KPIs financeiros a partir de issues abertas
**Decisão (quality pass):** dashboard recalcula conciliado/divergência só com issues `open`/`reviewing` dos tipos financeiros.  
**Por quê:** resolver uma issue deve refletir no fechamento; snapshot do import sozinho mentia o estado operacional.  
**Trade-off:** valores no `ImportBatch` continuam sendo o snapshot do processamento (auditoria do run).

### ADR-005 — Dinheiro como Decimal / Numeric
**Decisão:** `decimal.Decimal` no domínio + `Numeric(18, 2)` no SQLAlchemy; serialização JSON ainda como `number` quantizado (centavos) para o cliente Next.js.  
**Por quê:** evitar armadilhas IEEE (`0.1 + 0.2`) em regras e totais de fechamento — credibilidade em entrevistas de analytics/finanças.  
**Trade-off:** JSON continua float na borda HTTP (UI); a fonte de verdade interna é Decimal quantizado half-up.

### ADR-006 — Sem auth no MVP
**Decisão:** endpoints públicos.  
**Por quê:** demo de portfólio sem fricção.  
**Trade-off:** superfície aberta a abuso; rate-limit/auth são pré-requisito de produto pago.

### ADR-007 — Grain: Order (cabeçalho) + OrderLine (item)
**Decisão (Fase 2a → refinada em 2a.1):** `Order` é cabeçalho (identidade/dimensão). A persistência grava **exatamente um `Order` por `(batch_id, order_id)`** e N `OrderLine` por pedido (`line_id = "{order_id}-L{seq}"`). `UniqueConstraint("batch_id","order_id")` em `Order` e `UniqueConstraint("batch_id","order_id","line_id")` em `OrderLine` — o `batch_id` evita colisão quando o mesmo pedido é reimportado em outro batch. A reconciliação financeira agrega por `order_id`.  
**Por que o refinamento:** a Fase 2a gravava um `Order` por linha do CSV (N cabeçalhos → N linhas), o que não correspondia ao modelo conceitual de "1 Order → N Lines". O review pós-merge identificou isso.  
**Detecção de duplicata → 3 saídas** (`rule_duplicate_order`): (1) **multiline legítimo** — header consistente + SKUs distintos → válido (sem issue); (2) **`duplicate_line`** — linha idêntica repetida → alta; (3) **`header_conflict`** — atributos de cabeçalho conflitantes (cliente/canal/status/data) → alta. O antigo `duplicate_order` único foi removido.  
**`missing_stock_out`** agora opera no grain `(order_id, sku)`: uma issue por SKU sem movimento `out` vinculado.  
**Trade-off:** a persistência grava N `OrderLine` por pedido; o engine agrega de volta ao grain de pedido antes de emitir issues e KPIs. `OrderLine.order_id` é link lógico (não FK) para preservar a detecção de `duplicate_line`/`header_conflict`.

### ADR-008 — Decomposição de KPIs financeiros sem double-counting
**Decisão (Fase 2a → refinada em 2a.1):** `compute_kpis(orders, payments, issues)` expõe `eligible / reconciled / unreconciled / missing_payment / underpayment / overpayment / orphan_payment / pending_excluded`. Invariante de fechamento: `eligible = reconciled + missing + under`. **`overpayment` e `orphan_payment` são exposures payments-side** (dinheiro recebido em excesso de / sem um pedido) e são reportados à parte, **nunca subtraídos de `eligible`**. Um pedido de R$100 com pagamento de R$110 está 100% coberto (matched=100); só há R$10 de excesso de caixa. Under/over vêm de `amount_mismatch` abertos comparados ao somatório de pagamentos aprovados por pedido.  
**Impacto por canal** no dashboard: restrito a `MONEY_ISSUE_TYPES` e **dedupado por (issue_type, entity_id)**; para `amount_mismatch` conta apenas a parcela **under** (a sobrepagamento é payments-side e fica de fora), então `sum(impact por canal) == unreconciled_amount` (sem inflação). Issues de estoque/duplicata não entram no impacto financeiro por canal.  
**Por que:** a implementação anterior somava o `amount_impact` de TODAS as issues abertas por canal (incluindo `missing_stock_out`, `duplicate_order`), inflacionando 2–3×; e tratava overpayment como redução do valor conciliado, o que é semanticamente errado (o pedido está pago).  
**Trade-off:** o impacto por canal deixa de refletir overpayment/estoque/duplicata — por design; elas continuam nos contadores `issues_by_type` e nos campos `overpayment_amount`/`orphan_payment_amount`.

## O que deliberadamente NÃO fizemos

- ERP / WMS / emissão fiscal / conciliação bancária completa.
- Multi-idioma completo (UI PT-BR + README bilingue).
- Realtime / websockets.
- Marketplace de templates.
