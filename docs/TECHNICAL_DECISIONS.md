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

### ADR-005 — Dinheiro como float (temporário)
**Decisão:** `float` / SQLAlchemy `Float` no MVP.  
**Por quê:** velocidade de entrega.  
**Trade-off:** impreciso para finanças reais — roadmap explícito para `Decimal`/`Numeric`.

### ADR-006 — Sem auth no MVP
**Decisão:** endpoints públicos.  
**Por quê:** demo de portfólio sem fricção.  
**Trade-off:** superfície aberta a abuso; rate-limit/auth são pré-requisito de produto pago.

## O que deliberadamente NÃO fizemos

- ERP / WMS / emissão fiscal / conciliação bancária completa.
- Multi-idioma completo (UI PT-BR + README bilingue).
- Realtime / websockets.
- Marketplace de templates.
