# Experimento prospectivo de seis meses

Status: ready-for-agent

Tracker: https://github.com/pedropasinn/marko/issues/16

Pedido: simular US$ 10.000 durante seis meses, comparar modelos, avaliar decisões diariamente por agentes independentes e publicar relatórios semanais, mantendo revisão de código contínua.

## Contrato

- Capital exclusivamente virtual: US$ 10.000 por modelo, sem aportes ou saques. Resultados comparáveis, nunca somados entre modelos.
- Campanha inicial 14/09/2026 a 14/03/2027; sessão final 12/03/2027 pelo calendário NYSE. Encerramento por valor marcado, sem fingir venda realizada.
- Universo inicial fixo: SPY, EFA, IEMG, IEF, GLD, BIL. Long-only, sem empréstimo/alavancagem. Custos explícitos de 5 bps por lado, preço de abertura posterior à decisão. Impostos pessoais excluídos; distribuições brutas contabilizadas em recebíveis no ex-date, sem reinvestimento antes de verificar a data de pagamento.
- Modelos congelados: equal-weight, minimum variance, risk budgeting, HRP e CVaR; benchmarks caixa, SPY buy-and-hold e carteira 60/40 SPY/IEF buy-and-hold. Rebalanceamento mensal após última sessão do mês; avaliação/mark diário.
- Modelos skfolio por adapters; estado paper separado do ledger real. Price feed Yahoo/yfinance para pesquisa pessoal, snapshots privados, sem substituir silenciosamente provider ou dados faltantes.
- Decisões só usam snapshots observados antes de sua criação. Execução virtual apenas na próxima abertura após criação; jamais inventar decisões para dias perdidos.
- Registro hash-chained append-only, idempotência, cron externo, catch-up apenas para valuation/execução de decisões já existentes. Versões congeladas e config hash verificadas.
- Agentes de risco e metodologia avaliam separadamente. Revisor de código semanal cria propostas verificáveis; mudanças não reescrevem resultados nem são promovidas automaticamente à campanha congelada.
- Falta de credencial, quota ou dado gera estado explícito. Não confundir testes sintéticos, preflight, shadow prospectivo e lucro realizável.

## Aceitação

- Contraexemplos da auditoria viram regressões econômicas independentes.
- Teste de custos, dividendos, splits, gaps, fechamento precoce, data futura, replay duplicado, hash e mudança de código/config.
- Agendamento publicado e executado ao menos uma vez; relatório inicial real e auditoria do estado.
- Orçamento de APIs fixado em zero por decisão do usuário. IA somente pela assinatura local existente, sujeita à disponibilidade da máquina e da quota; ausência de parecer explicitamente reportada.
- Resultados e dados em repositório operacional privado; código e documentação de arquitetura no Marko.

## Limites do experimento

Seis meses medem o comportamento desse período, não comprovam capacidade de prever retorno futuro. Não haveria capital real nem lucro realizado. Resultados serão líquidos dos custos simulados e antes de impostos pessoais, infraestrutura e custos de IA, estes reportados separadamente quando conhecidos.
