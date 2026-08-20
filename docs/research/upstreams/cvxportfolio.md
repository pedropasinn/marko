# cvxportfolio

## Ficha

- Origem: `https://github.com/cvxgrp/cvxportfolio.git`; `master`; `351c782b9b8b395c1a5f886b77e0d55f1bc9396e`; versão dinâmica.
- Linguagem/dependências: Python; pandas, NumPy, Matplotlib, CVXPY `<1.7` e SCS.
- Licença: GPL-3.0. Uso pessoal e modificação são possíveis sob a licença; redistribuição derivada exige GPL. Não incorporar ao produto nesta fase.
- Arquitetura: estimadores recursivos, policies, forecasts, costs, risks, constraints, market data, simulator e result.
- APIs: `SinglePeriodOptimization`, `MultiPeriodOptimization`, `MarketSimulator`, `TransactionCost`, `HoldingCost`, `FullCovariance`, `FactorModelCovariance` e constraints.
- Testes: alvo declarado de cobertura muito alta, pytest e lint rigoroso.

## Cobertura

Policies incluem Hold, AllCash, pesos fixos, rebalanceamento periódico/adaptativo e otimização de um ou vários períodos. Constraints cobrem long-only, leverage, cash mínimo, turnover, participation rate, no-trade, bounds e exposição fatoriais. O simulador modela trades, custos, holdings e resultados; forecasts históricos alimentam retornos e riscos.

É a melhor referência para transformar carteira-alvo em trades mediante tracking error, custo, holding cost, turnover e risco. Imposto brasileiro e tax lots continuam próprios.

## Avaliação

- Fortes: separação explícita entre política, forecast, custo, constraint e simulação.
- Fracos: GPL, conflito de versão de CVXPY e foco em convenções próprias de mercado.
- Duplicações: otimização convexa e risco com skfolio/Riskfolio.
- Único: política multi-período e execução simulada integradas.
- Classificação: **D — ARCHITECTURAL REFERENCE ONLY**, com spike isolado como oráculo.
