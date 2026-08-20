# skfolio

## Ficha

- Origem: `https://github.com/skfolio/skfolio.git`; `main`; `07dd64b3640fc4350d3d092837a978a87e9e4b34`; tag `v0.20.2`.
- Linguagem/dependências: Python; NumPy, pandas, SciPy, scikit-learn, CVXPY e solvers.
- Licença: BSD-3-Clause. Adequada a uso pessoal, dependência, modificação e produto, preservando avisos.
- Arquitetura: estimadores compatíveis com scikit-learn, `fit`/`predict`, composição por pipelines e seleção temporal.
- APIs/tipos: `Portfolio`, `Population`, estimadores de `prior`, `moments`, `optimization`, `model_selection` e `pre_selection`.
- Testes/validação: pytest, exemplos e comparação de estimadores; `WalkForward`, `CombinatorialPurgedCV` e predição fora da amostra.

## Cobertura

Implementa Equal Weight, inverse volatility, mean-risk regularizado, minimum variance, efficient frontier, maximum diversification, risk budgeting, Black–Litterman, Entropy Pooling, modelos fatoriais, shrinkage/Ledoit-Wolf, denoise/detone, HRP, HERC, NCO, CVaR, CDaR e DRO-CVaR. Custos de transação, penalidade/limite de turnover, bounds, grupos e L1/L2 entram na otimização. `StackingOptimization` combina previsões fora da amostra e registra falhas de estimadores.

Não é ledger, data gateway nem simulador de execução. Stress testing existe sobretudo pela geração/avaliação de populações, não como motor completo de cenários econômicos.

## Avaliação

- Fortes: superfície coerente, validação temporal nativa, muitos modelos sob a mesma convenção, composição e diagnósticos.
- Fracos: defaults e abstrações podem esconder convenções; CVXPY/solvers tornam reprodutibilidade parte do contrato.
- Duplicações: mean-variance/BL/HRP com PyPortfolioOpt; risco avançado com Riskfolio.
- Único: combinação de portfolio optimization com protocolo scikit-learn, CPCV e stacking.
- Classificação: **B — WRAP BEHIND ADAPTER** como motor principal. Objetos da biblioteca nunca atravessam o domínio.
