# vectorbt

## Ficha

- Origem: `https://github.com/polakowo/vectorbt.git`; `master`; `34b6d5935e3ea3eccd549e2592bc0f455b8045f5`; tag `v1.1.0`.
- Linguagens/dependências: Python e Rust opcional; NumPy, pandas, Numba e ecossistema de plots/dados.
- Licença: Apache-2.0 acrescida de Commons Clause. Pesquisa pessoal é o uso inicial; dependência comercial requer revisão específica.
- Arquitetura/APIs: arrays tipados, accessors pandas, indicators, signals, portfolio simulation, splitters e records.
- Testes: pytest, benchmarks e grande matriz de configurações.

## Cobertura

Executa simulações vetorizadas e event-driven, parameter broadcasting/sweeps, sinais, indicadores, rolling/expanding/walk-forward, portfólios multiativos, ordens, custos e analytics. A engine Rust recente é opcional. Não oferece accounting patrimonial canônico nem registro experimental completo.

## Avaliação

- Fortes: velocidade exploratória, composição vetorial e sweeps massivos.
- Fracos: superfície ampla, risco de overfitting e licença não trivial.
- Duplicações: backtest e métricas com Qlib/cvxportfolio/QuantStats.
- Único: escala de experimentação interativa.
- Classificação: **E — RESEARCH TOOL ONLY**; resultados só entram no Marko via artefato versionado.
