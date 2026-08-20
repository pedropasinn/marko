# Accounting 0.2.1

Activities imutáveis representam caixa, trades, transferências, FX, entregas, splits/grupamentos, spinoffs, amortizações e reversões. Cada tipo possui uma matriz explícita de campos aceitos. Reversões referenciam o original e precisam reproduzir seu payload; o ledger deriva o efeito inverso.

| Tipo | Obrigatórios | Opcionais com efeito |
|---|---|---|
| deposit | gross | nenhum |
| withdrawal | gross | fee, tax |
| buy/sell | gross, instrument, quantity | fee, tax |
| dividend | gross, instrument | fee, tax |
| interest | gross | instrument, fee, tax |
| fee/tax | gross | nenhum |
| delivery in | instrument, quantity | cost basis |
| delivery out | instrument, quantity | nenhum |
| cash transfer | gross, conta e activity relacionadas | fee, tax |
| position transfer | instrument, quantity, conta e activity relacionadas | cost basis na entrada |
| FX conversion | gross, counter amount, ratio | fee, tax na moeda de saída |
| split | instrument, ratio | nenhum |
| spinoff | instrument, quantity, instrumento de origem | cost basis |
| amortization | gross, instrument | fee, tax |

Campos fora da linha correspondente são rejeitados. `cost_basis` ausente em entrada de posição é aceito como fato incompleto, mas bloqueia qualquer relatório fiscal que dependa dele.

O ledger deriva caixa e posições e valida pares de transferência. Lotes fiscais suportam FIFO e custo médio, `as_of` e reversões sem perder proveniência. Entradas sem base conhecida bloqueiam cálculo realizado.

Snapshots fixam `as_of` e último evento. `ValuationResult` distingue valor completo de parcial, lista preços e FX ausentes, cotações vencidas e IDs das evidências. `net_liquidation_value` lança erro quando a valuation não está completa.

Analytics próprios cobrem TWR, XIRR, drawdown máximo e atribuição separada de taxas, impostos, renda, devolução de principal e ajustes.

Os dois casos Excel de `IRRTest.java` do Portfolio Performance foram reproduzidos como golden tests, inclusive o fluxo irregular de oito datas.
