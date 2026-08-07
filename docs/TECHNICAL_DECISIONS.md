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
**Decisão (Fase 2a):** `Order` é cabeçalho (identidade/dimensão: order_id, order_date, customer, channel, status). O dinheiro e o item vivem em `OrderLine` (sku, quantity, unit_price, gross/discount/net) com `order_id` indexado (link lógico, não FK, pois order_id é intencionalmente não-único para detectar duplicatas). A reconciliação financeira agrega por `order_id` (`groupby("order_id").agg(net_amount="sum")`).  
**Por quê:** `order ≠ order_line`. O modelo anterior colocava sku/quantidade/valor no cabeçalho, o que (1) impossibilitava pedidos multi-item e (2) fazia regras que iteravam linhas emitirem issues duplicadas por pedido.  
**Trade-off:** a persistência grava N `OrderLine` por pedido; o engine agrega de volta ao grain de pedido antes de emitir issues e KPIs. `OrderLine.order_id` não é FK para preservar a detecção de `duplicate_order`.

### ADR-008 — Decomposição de KPIs financeiros sem double-counting
**Decisão (Fase 2a):** `compute_kpis(orders, payments, issues)` expõe `eligible / reconciled / unreconciled / missing_payment / underpayment / overpayment / orphan_payment / pending_excluded`. Invariante: `eligible = reconciled + missing + under + over`. Under/over vêm de `amount_mismatch` abertos comparados ao somatório de pagamentos aprovados por pedido. O impacto por canal no dashboard é restrito a `MONEY_ISSUE_TYPES` (`missing_payment`, `orphan_payment`, `amount_mismatch`) e **dedupado por (issue_type, entity_id)**; issues de estoque/duplicata não entram no impacto financeiro por canal. `orphan_payment` é payments-side (dinheiro sem pedido) e é reportado à parte, nunca subtraído de `eligible`.  
**Por quê:** a implementação anterior somava o `amount_impact` de TODAS as issues abertas por canal (incluindo `missing_stock_out`, `duplicate_order`), inflacionando o impacto financeiro 2–3× acima de `unreconciled_amount`. Recrutador de finanças notaria a inconsistência soma-de-impactos ≠ fechamento.  
**Trade-off:** o impacto por canal deixa de refletir issues não-financeiras (estoque/duplicata) — por design; elas continuam nos contadores `issues_by_type`.

## O que deliberadamente NÃO fizemos

- ERP / WMS / emissão fiscal / conciliação bancária completa.
- Multi-idioma completo (UI PT-BR + README bilingue).
- Realtime / websockets.
- Marketplace de templates.
