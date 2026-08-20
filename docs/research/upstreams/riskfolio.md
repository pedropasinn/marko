# Riskfolio-Lib

## Ficha

- Origem: `https://github.com/dcajasn/Riskfolio-Lib.git`; `master`; `632a9e48fbaf2b9f8e83864a492332364b6ed32c`; versão `7.3.0`.
- Linguagens/dependências: Python e extensão C++/pybind; NumPy, pandas, SciPy, CVXPY, scikit-learn, NetworkX, statsmodels, arch, clarabel e vectorbt.
- Licença: BSD-3-Clause; permissiva, com preservação de avisos.
- Arquitetura/APIs: classes centrais `Portfolio` e `HCPortfolio`; módulos `RiskFunctions`, `ParamsEstimation`, `ConstraintsFunctions`, `AuxFunctions` e visualizações.
- Testes: pytest e exemplos extensos; forte cobertura funcional, porém API central grande e acoplada.

## Cobertura

Suporta numerosas medidas de risco convexas, downside e drawdown, contribuições de risco por ativo/fator, risk parity, Kelly aproximado/exato, modelos fatoriais, uncertainty sets, robust optimization, cardinalidade, clusters, grafos/network portfolios e famílias hierárquicas. A formulação é feita em CVXPY com escolha de solver.

Em relação ao skfolio, oferece maior catálogo de medidas, abordagens de rede, Kelly e restrições especializadas. O skfolio tem composição, seleção de modelo, validação temporal e stacking mais coerentes. Nenhum dos dois resolve accounting ou ingestão ponto-no-tempo.

## Avaliação

- Fortes: amplitude matemática, risk contribution e laboratório de restrições.
- Fracos: `Portfolio` concentra milhares de linhas; muitas dependências e defaults; adapter mais caro.
- Duplicações: mean-risk, CVaR/CDaR, risk parity e hierárquicos com skfolio.
- Único: catálogo de risco, Kelly, uncertainty sets e grafos.
- Classificação: **E — RESEARCH TOOL ONLY** e oráculo. Promover uma função a adapter somente após spike e teste cruzado.
