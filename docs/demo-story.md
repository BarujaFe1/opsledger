# Demo story

## Persona

Marina, analista operacional de um e-commerce pequeno omnichannel (Shopify + Mercado Livre + WhatsApp + Instagram + loja física). Toda sexta ela fecha a semana com três planilhas exportadas manualmente.

## Dor

Na última semana:

- 5 pedidos “pagos” sem captura no gateway;
- 3 pagamentos com `order_id` inexistente;
- 4 divergências de valor (desconto/marketplace);
- 2 pedidos duplicados na exportação;
- 5 vendas sem baixa de estoque;
- 1 SKU com saldo negativo estimado;
- canais escritos como `zap`, `wpp`, `whatsapp`.

## Jornada na demo

1. Abre OpsLedger e clica **Rodar demo**.
2. Vê preview dos três arquivos e o batch concluído.
3. No dashboard, identifica valor em divergência e a próxima melhor ação (geralmente estoque crítico).
4. Filtra issues por severidade `high`/`critical`.
5. Abre uma issue, marca como `reviewing`, adiciona nota.
6. Exporta CSV para o gestor e gera o relatório markdown de fechamento.

## Mensagem de portfólio

OpsLedger mostra capacidade de modelar uma dor real, implementar regras auditáveis, expor API clara e entregar UX executiva — sem fingir ser um ERP.
