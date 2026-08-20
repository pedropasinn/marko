# ADR 016 — Candidato pós-validado na decisão

## Decisão

`PortfolioCandidate` valida estrutura e finitude. A pós-validação contra `PortfolioProblem` produz `ValidatedPortfolioCandidate`. `DecisionPacket` aceita ModelRuns somente por referências que carregam esse tipo validado.

## Consequências

Chamadas diretas a `model.solve()` permanecem pesquisa bruta e não entram no caminho de decisão. Ordem de ativos, dimensões, soma, bounds e finitude são verificadas antes do draft.
