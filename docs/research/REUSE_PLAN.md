# Plano de reaproveitamento

## Adotar por dependência

- `skfolio`: modelos de alocação, estimadores e validação temporal.
- `PyPortfolioOpt`: implementação independente de baselines e Black–Litterman.

## Usar como oráculo

- `Riskfolio-Lib`: risk budgeting, medidas de cauda e restrições avançadas.
- `cvxportfolio`: política multi-período, custos, turnover e restrições.
- `QuantStats`: conferência de métricas.
- `Portfolio Performance`: transações, TWR, IRR, drawdown e custo fiscal.

## Reproduzir o padrão, não o código

- `OpenBB`: modelo padronizado, fetcher e registry de provedores.
- `Qlib`: dataset ponto-no-tempo, experiment/recorder e rolling tasks.
- `Wealthfolio`: cenários de rebalanceamento, drift e permissões read/draft/write.
- `Ghostfolio`: importação, regras e navegação patrimonial.

## Isolar

- `vectorbt`: ambiente de pesquisa separado por restrição de licença e superfície ampla.
- todo copyleft: nunca importado pelo núcleo sem decisão jurídica explícita.
