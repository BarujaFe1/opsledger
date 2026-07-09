# Handoff de portfólio — OpsLedger

## Título curto

OpsLedger — reconciliação operacional para e-commerces pequenos

## Descrição curta

Aplicação full-stack que cruza pedidos, pagamentos e estoque, detecta divergências com regras testáveis e orienta o fechamento operacional.

## Descrição média

OpsLedger transforma planilhas bagunçadas de operação em um batch reconciliado: valida CSVs, executa sete regras de qualidade/financeiro/estoque, exibe KPIs executivos, permite investigar e atualizar issues, exportar CSV e gerar relatório de fechamento. Demo local com dados sintéticos realistas, sem dependências externas obrigatórias.

## Descrição longa

Pequenos e-commerces costumam fechar a semana com três exportações manuais — pedidos, pagamentos e movimentações de estoque — que não conversam entre si. O resultado são pagamentos órfãos, pedidos “pagos” sem captura, divergências de valor, duplicidades e baixas de estoque faltantes.

OpsLedger é um MVP de portfólio que ataca exatamente essa dor. O usuário roda uma demo sintética ou importa CSVs; o backend (FastAPI + Pandas + SQLAlchemy/SQLite) valida schema, cria um `ImportBatch` e executa uma engine de reconciliação com regras rastreáveis. O frontend (Next.js + Tailwind + Recharts + TanStack Table) entrega landing, wizard, dashboard, issues register, detalhe com timeline de status, exportação e relatório.

O projeto evidencia raciocínio de produto, modelagem de dados, qualidade de dados aplicada, API bem definida, testes automatizados e documentação pronta para entrevista — sem inflar o escopo para um ERP.

## Bullets de impacto

- 7 regras de reconciliação cobertas por testes unitários
- Demo com ~150 pedidos e 15–30 divergências intencionais
- Dashboard com valor conciliado vs. em divergência e próxima melhor ação
- Fluxo completo: import → issues → status → export CSV → relatório
- Documentação técnica + handoff de portfólio incluídos

## Stack resumida

Next.js · TypeScript · Tailwind · Recharts · TanStack Table · FastAPI · Python 3.12 · Pandas · Pydantic · SQLAlchemy · SQLite · pytest · Vitest · Docker

## Problema resolvido

Falta de uma ferramenta leve para cruzar planilhas operacionais e transformar divergências em ações priorizadas por impacto financeiro.

## Competências provadas

- Dados aplicados a operação real
- Python/Pandas e modelagem SQL
- APIs FastAPI com schemas claros
- Produto/UX executiva
- Qualidade de dados e automação de análise
- Testes e documentação de handoff

## Como apresentar em entrevista

1. Conte a dor da Marina (analista) em 30s.
2. Mostre a home → Rodar demo → dashboard (KPIs + próxima ação).
3. Abra uma issue crítica/high e explique a regra por trás.
4. Altere status + mostre export/relatório.
5. Abra o código da engine e um teste — destaque rastreabilidade.
6. Fale limitações honestas e o que faria em v1.1 (auth, Postgres, regras por tenant).

## Limitações honestas

- Sem autenticação ou multiempresa
- SQLite single-user
- Estoque é simulação de saldo do batch, não WMS
- Sem integrações reais de marketplace/gateway

## Próximos passos

- Auth + workspaces
- PostgreSQL + Alembic
- Regras configuráveis
- Matching fuzzy entre canais
- Alertas para críticas
- Comparativo entre batches

## Sugestão de post para LinkedIn

Acabei de publicar o OpsLedger, um MVP de reconciliação operacional para pequenos e-commerces.

A ideia: em vez de mais um dashboard bonito, uma ferramenta que importa pedidos, pagamentos e estoque, cruza com regras claras e mostra o que revisar — com impacto financeiro e próxima ação.

Stack: Next.js + FastAPI + Pandas + SQLite, com demo local, testes da engine e documentação de portfólio.

Se você já sofreu com planilhas que “quase batem” no fechamento da semana, esse projeto é sobre transformar esse caos em decisão.

#dados #operacoes #python #fastapi #nextjs #portfolio
