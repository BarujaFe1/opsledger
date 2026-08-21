# Regras de reconciliação

Todas as regras vivem em `apps/api/app/reconciliation/engine.py` e são cobertas por testes em `apps/api/tests/`.

**Inventário canônico:** a engine tem **8 funções de regra** capazes de emitir **até 11 issue types**. O demo golden atual exercita **9 issue types** (os não exercitados são `duplicate_line` e `header_conflict`).

| # | Função | Issue types |
|---|--------|-------------|
| 1 | `rule_missing_payment` | `missing_payment` |
| 2 | `rule_orphan_payment` | `orphan_payment` |
| 3 | `rule_amount_mismatch` | `amount_mismatch` |
| 4 | `rule_duplicate_order` | `duplicate_line`, `header_conflict` |
| 5 | `rule_missing_stock_out` | `missing_stock_out` |
| 6 | `rule_negative_stock` | `negative_stock` |
| 7 | `rule_channel_standardization` | `channel_standardization` |
| 8 | `rule_refund_anomalies` | `refund_without_payment`, `over_refund`, `chargeback` |

## 1. `missing_payment`

**Motivação:** pedido marcado como pago/enviado sem dinheiro correspondente gera risco de receita fantasma.

**Lógica:** status do pedido ∈ {`paid`, `shipped`} e não existe pagamento com status `paid` para o mesmo `order_id`.

**Severidade:** high  
**Impacto:** `net_amount` do pedido  
**Exemplo:** `ORD-0005` paid, sem `PAY-*`  
**Ação:** verificar gateway, marketplace ou status do pedido.

## 2. `orphan_payment`

**Motivação:** dinheiro sem pedido dificulta baixa e auditoria.

**Lógica:** pagamento `paid` cujo `order_id` não existe em orders.

**Severidade:** high  
**Impacto:** valor do pagamento  
**Exemplo:** `PAY-ORPH-1` → `ORD-9991`  
**Ação:** verificar ID de pedido, importação ou duplicidade de canal.

## 3. `amount_mismatch`

**Motivação:** descontos, frete, taxas e reembolsos quebram o fechamento.

**Lógica:** |net do pedido − soma de pagamentos aprovados| > R$ 0,05.

**Severidade:** high se diferença ≥ R$ 20; medium caso contrário  
**Impacto:** diferença absoluta  
**Exemplo:** pedido R$ 100, pagamento R$ 75  
**Ação:** revisar desconto, frete, taxa ou reembolso.

## 4. `duplicate_order` → `header_conflict` / `duplicate_line`

**Motivação:** exportações duplicadas inflacionam GMV e estoque; porém um pedido legítimo pode ter múltiplos SKUs (multiline) e NÃO é duplicata.

**Lógica (`rule_duplicate_order`):** mesmo `order_id` aparece em mais de uma linha. Três saídas:
- **multiline legítimo** — header consistente (cliente/canal/status/data) + SKUs distintos → válido, **sem issue**.
- **`duplicate_line`** — linha idêntica repetida (mesmo SKU/quantidade/valor) → **high**.
- **`header_conflict`** — atributos de cabeçalho conflitantes entre linhas do mesmo `order_id` → **high**.

**Severidade:** high (para `duplicate_line`/`header_conflict`); multiline legítimo não gera issue  
**Exemplo:** `ORD-0012` com dois SKUs diferentes = multiline legítimo (sem issue); `ORD-X` com duas linhas idênticas = `duplicate_line`  
**Ação:** verificar duplicidade de exportação / integridade do cabeçalho.

## 5. `missing_stock_out`

**Motivação:** venda sem baixa distorce disponibilidade.

**Lógica:** pedido `paid`/`shipped` sem movimento `out` com `reference_order_id` + SKU.

**Severidade:** medium  
**Exemplo:** `ORD-0015` shipped sem `MOV-OUT`  
**Ação:** revisar baixa de estoque.

## 6. `negative_stock`

**Motivação:** saldo impossível indica erro de cadastro ou baixa duplicada.

**Lógica:** simula saldo por SKU em ordem cronológica (`in`/`return` somam, `out` subtrai, `adjustment` usa sinal).

**Severidade:** critical  
**Exemplo:** `SKU-MEI-09` após saídas excessivas  
**Ação:** revisar cadastro, contagem física ou baixa duplicada.

## 7. `channel_standardization`

**Motivação:** dimensão de canal suja quebra análises por origem.

**Lógica:** aliases (`whatsapp`/`zap`/`wpp` → WhatsApp, etc.) ou múltiplas grafias do mesmo canal.

**Severidade:** low  
**Exemplo:** `whatsapp` e `zap` no mesmo batch  
**Ação:** padronizar dimensão de canal.

## 8. `rule_refund_anomalies` → `refund_without_payment` / `over_refund` / `chargeback`

**Motivação:** reembolsos e chargebacks são reversões posteriores de caixa. Reembolsos "bem explicados" (com pagamento correspondente) e chargebacks regulares ficam **silenciosos** — apenas líquidam os KPIs via realização de caixa. Só as anomalias abaixo viram issue.

**Lógica (`rule_refund_anomalies`):** considera apenas pagamentos **liquidados** por par `(kind, status)` — `payment/paid`, `refund/refunded`, `chargeback/charged_back` — sobre pedidos **cumpridos** (`paid`/`shipped`). Por pedido soma `paid_gross` (pagamentos normais liquidados), `refund_sum` (reembolsos + chargebacks liquidados) e `chargeback_sum`; pedidos sem reversão não entram na análise. Três saídas:

### `refund_without_payment`

- **Condição:** existe reembolso/chargeback liquidado, mas **nenhum** pagamento liquidado para o pedido (`paid_gross <= 0`). O dinheiro foi devolvido sem nunca ter sido recebido.
- **Severidade:** high
- **Semântica do valor:** `amount_impact = refund_sum` (magnitude total devolvida).
- **Ação recomendada:** verificar estorno, gateway ou pedido cancelado indevidamente.

### `over_refund`

- **Condição:** o total reembolsado/chargeback **excede** o total recebido (`refund_sum > paid_gross > 0`).
- **Severidade:** high
- **Semântica do valor:** `amount_impact = refund_sum − paid_gross` (apenas o excesso).
- **Ação recomendada:** revisar política de reembolso e possível fraude.

### `chargeback`

- **Condição:** existe chargeback liquidado sobre o pedido. Enquadramento: **exposição financeira em disputa**, não perda final automática — o valor reduz o caixa realizado (`net_cash`) enquanto a disputa não é resolvida.
- **Severidade:** medium
- **Semântica do valor:** `amount_impact = chargeback_sum` (valor associado à disputa).
- **Ação recomendada:** acionar disputa de chargeback junto à operadora.

## Duas dimensões financeiras (preservar)

As regras acima alimentam **duas dimensões independentes** em `compute_kpis` — reembolso nunca marca retroativamente um pedido pago como subpagado.

### PAYMENT MATCHING (cobertura do pedido)

> **Invariante:** `eligible = reconciled + missing + under`

Pergunta: *o valor original do pedido foi coberto por pagamentos normais válidos?* Base = pedidos cumpridos (`paid`/`shipped`). Só `missing_payment`, `orphan_payment` e `amount_mismatch` decompõem esta dimensão (`MONEY_ISSUE_TYPES`). Overpayment e orphan são exposições do lado dos pagamentos, reportados separadamente — nunca subtraídos do eligible.

### CASH REALIZATION (caixa realizado)

> **Invariante:** `net_cash = gross_paid − refunds − active_chargebacks`

Reembolsos e chargebacks liquidados são reversões posteriores de caixa: reduzem `net_cash_amount`, não o `reconciled` nem inflam o `under`. `net_cash` pode ficar negativo (ex.: `refund_without_payment` / `over_refund`) — essa é a verdade honesta de caixa. `active_chargeback_amount` é exposição corrente em disputa, não perda realizada.
