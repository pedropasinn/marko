# Decision Engine

`DecisionPacket` exige `NO_ACTION` e aceita somente referências a ModelRuns com `ValidatedPortfolioCandidate`. O caixa é uma entrada explícita, não um instrumento com ID convencional. O modo `cash_flow_only` ordena déficits contra o alvo, respeita pesos máximos, lotes inteiros, negociação mínima, aporte disponível e custo estimado.

O resultado é draft: trades validados, pesos projetados que somam um, caixa não alocado, turnover, feasibility e razões. Não altera ledger nem envia ordens.

Vendas e otimização tributária ficam fora deste corte; o caso prioritário usa aportes mensais para reduzir drift sem realizar posições.
