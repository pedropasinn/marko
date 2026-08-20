# Roadmap canônico

## 0.1 — Accounting e Policy kernel

Estado: implementado.

Dinheiro exato, Instrument Master, contas, activities, ledger, snapshots básicos, Liability, IPS, Universe, Constraints, quatro tempos e invariantes.

Gate: casos contábeis determinísticos, duplicatas rejeitadas, moeda incompatível rejeitada e shortfall calculável.

## 0.2 — Analytics e reconciliação

Estado: implementado no corte inicial; corporate actions complexas e regras fiscais brasileiras ainda exigem casos dourados.

TWR, XIRR, drawdown, volatilidade, contribuições, FX, corporate actions, tax lots e importação/reconciliação.

## 0.3 — Data Gateway

Estado: BCB/SGS e IBGE/SIDRA operacionais; contratos de Tesouro, ANBIMA e B3 aguardam endpoint/credenciais atuais.

Providers brasileiros, proveniência, qualidade, calendário, point-in-time, revisão e Data Vintage.

## 0.4 — Baseline Portfolio Lab

Estado: implementado com motores internos e adapters opcionais.

`NO_ACTION`, 1/N, inverse volatility, minimum variance, risk budgeting e adapters skfolio/PyPortfolioOpt.

## 0.5 — Validation Framework

Estado: implementado no corte inicial.

Walk-forward, purge/embargo, custos, benchmarks, estabilidade, stress, sensibilidade e registry de experimentos/solvers.

## 0.6 — Advanced Portfolio Lab

Black–Litterman, HRP/HERC/NCO, CVaR/CDaR, maximum diversification, DRO e ensemble. Nenhum modelo avança sem superar os gates de 0.5.

## 0.7 — Decision e Implementation

Estado: `NO_ACTION` e cash-flow rebalancing implementados como draft; vendas, imposto e execução permanecem futuros.

Model committee, DecisionPacket, cash-flow rebalancing, impostos, turnover, lotes inteiros, draft/approve/record e explicações.

## 0.8 — Macro, fundamentos e research agents

Evidências viram features/views com confiança; nunca ordens diretas.

## 0.9 — Shadow operation

Carteira virtual paralela, CDI/1-N/carteira real como benchmarks e reconciliação diária.

## Gate para capital real

Accounting reconciliado, dados PIT, testes anti-look-ahead, robustez, limites de risco, execução simulada, auditoria, shadow por período suficiente, revisão humana e definição formal do empréstimo. Tempo curto de shadow valida operação, não retorno esperado.
