# Accounting 0.2

Activities imutáveis representam caixa, trades, transferências, FX, entregas, splits/grupamentos, spinoffs, amortizações e reversões. `sequence` resolve causalidade quando vários fatos compartilham timestamps.

O ledger deriva caixa e posições. Snapshots fixam `as_of` e último evento; reconciliação compara snapshot e extrato no mesmo instante. Lotes fiscais suportam FIFO e custo médio, preservando custo total em splits. Entradas sem base conhecida bloqueiam cálculo realizado.

Analytics próprios cobrem TWR, XIRR, drawdown máximo e atribuição de taxas, impostos e rendimentos. Convenções são explícitas e permanecem independentes do QuantStats.

Os dois casos Excel de `IRRTest.java` do Portfolio Performance foram reproduzidos como golden tests, inclusive o fluxo irregular de oito datas.
