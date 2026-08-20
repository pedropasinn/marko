# PyPortfolioOpt

## Ficha

- Origem: `https://github.com/PyPortfolio/PyPortfolioOpt.git`; `main`; `a6638d2e06dae6f444fd022cfd4b3c528902a85b`; versão `1.6.0`.
- Linguagem/dependências: Python; NumPy, pandas, SciPy e CVXPY.
- Licença: MIT; permissiva para dependência, modificação e distribuição com aviso.
- Arquitetura/APIs: módulos pequenos `expected_returns`, `risk_models`, `objective_functions`, `efficient_frontier`, `black_litterman`, `hierarchical_portfolio` e `discrete_allocation`.
- Testes: pytest com casos unitários e resultados esperados.

## Cobertura

Expected returns históricos/EMA/CAPM, sample covariance, semicovariance, exponential covariance e shrinkage Ledoit-Wolf; efficient frontier, minimum volatility, max Sharpe, efficient risk/return, Black–Litterman, HRP, EfficientCVaR/CDaR/Semivariance e alocação discreta.

Não cobre ledger, ingestão, walk-forward, experiment registry ou execução multi-período. A superfície simples permite alinhar retornos, covariância, bounds e solver com o Marko e o skfolio.

## Avaliação

- Fortes: legibilidade, popularidade e independência suficiente para detectar regressões.
- Fracos: validação temporal e rastreabilidade precisam ser externas.
- Duplicações: grande parte dos baselines do skfolio.
- Único no conjunto: oracle compacto e alocação discreta acessível.
- Classificação: **B — WRAP BEHIND ADAPTER** para validação; nunca única fonte de verdade.
