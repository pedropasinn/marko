# Decision Engine

`DecisionPacket` exige `NO_ACTION` e preserva política, ModelRuns e evidências. O modo `cash_flow_only` ordena déficits contra o alvo, respeita pesos máximos, lotes inteiros, negociação mínima, caixa disponível e custo estimado.

O resultado é draft: trades, pesos projetados, caixa não alocado, turnover, feasibility e razões. Não altera ledger nem envia ordens.

Vendas e otimização tributária ficam fora deste corte; o caso prioritário usa aportes mensais para reduzir drift sem realizar posições.
