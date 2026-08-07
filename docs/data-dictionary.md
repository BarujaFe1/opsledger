# Dicionário de dados

## Tabelas (SQLite / SQLAlchemy)

### `import_batches`
| Campo | Tipo | Descrição |
|-------|------|-----------|
| id | int PK | Identificador do batch |
| created_at | datetime | Criação |
| source_name | string | `demo` ou `upload` |
| status | string | pending / processing / completed / failed |
| total_orders | int | Contagem |
| total_payments | int | Contagem |
| total_stock_movements | int | Contagem |
| total_issues | int | Contagem de issues |
| total_amount | Decimal / Numeric(18,2) | Soma net dos pedidos |
| reconciled_amount | Decimal / Numeric(18,2) | Estimativa conciliada (snapshot do run) |
| unreconciled_amount | Decimal / Numeric(18,2) | Impacto financeiro no run |

### `orders`
Campos alinhados ao CSV de pedidos + `batch_id`, `id` interno.

### `payments`
Campos alinhados ao CSV de pagamentos + `batch_id`, `id` interno.

### `stock_movements`
Campos alinhados ao CSV de estoque + `batch_id`, `id` interno.

### `reconciliation_issues`
Issue gerada pela engine: tipo, severidade, entidade, título, descrição, ação, impacto, status, timestamps, nota.

### `issue_status_history`
Auditoria de mudanças de status (`previous_status`, `new_status`, `note`, `changed_at`).

## Formatos CSV

Datas: ISO 8601 ou `YYYY-MM-DD` (parseadas como UTC).  
Decimais: ponto (ex.: `99.90`).  
Encoding: UTF-8.

### `orders.csv` (obrigatórias)

`order_id, order_date, customer_name, channel, sku, product_name, quantity, unit_price, gross_amount, discount_amount, net_amount, status`

Opcional: `customer_document_optional`  
Status: `created | paid | canceled | shipped | returned`

### `payments.csv` (obrigatórias)

`payment_id, order_id, paid_at, amount, method, status`

Opcional: `transaction_reference`  
Method: `pix | credit_card | debit_card | cash | transfer | marketplace`  
Status: `paid | pending | refunded | failed`

### `stock_movements.csv` (obrigatórias)

`movement_id, sku, movement_type, quantity, movement_date`

Opcionais: `reference_order_id, notes`  
Movement type: `in | out | adjustment | return`
