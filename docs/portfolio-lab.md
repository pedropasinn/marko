# Portfolio Lab

## Modelos

- `NO_ACTION`;
- equal weight;
- inverse volatility;
- minimum variance com shrinkage e projected gradient;
- risk budgeting;
- adapters opcionais skfolio e PyPortfolioOpt.

`PortfolioProblem` normaliza matriz, universo, pesos atuais e bounds. Todo `PortfolioCandidate` passa por pós-validação de finitude, soma e limites.

`ModelRun` fixa código, ambiente, dataset, IPS, universo, parâmetros, seed, solver, resultado e violações. O framework de validação inclui walk-forward, purged k-fold com embargo, turnover, perturbação, estabilidade e stress determinístico.

Os modelos internos são baselines controláveis, não promessa de superioridade econômica.
