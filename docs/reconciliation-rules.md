# Regras de reconciliação

Todas as regras vivem em `apps/api/app/reconciliation/engine.py` e são cobertas por testes em `apps/api/tests/`.

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
