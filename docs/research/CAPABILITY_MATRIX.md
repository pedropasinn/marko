# Matriz de capacidades

`FULL` é implementação central; `PARTIAL`, cobertura limitada; `REFERENCE`, padrão útil sem adoção direta; `NONE`, ausente do foco.

| Capacidade | SK | RF | PPO | CVXP | VBT | QS | OBB | QLIB | GF | WF | PP |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Mean Variance | FULL | FULL | FULL | FULL | PARTIAL | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Black–Litterman | FULL | FULL | FULL | NONE | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Shrinkage | FULL | FULL | FULL | PARTIAL | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Risk Parity | FULL | FULL | PARTIAL | PARTIAL | NONE | NONE | NONE | PARTIAL | NONE | PARTIAL | NONE |
| HRP | FULL | FULL | FULL | NONE | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| HERC | FULL | FULL | NONE | NONE | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| NCO | FULL | PARTIAL | NONE | NONE | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| CVaR | FULL | FULL | FULL | PARTIAL | PARTIAL | FULL | NONE | PARTIAL | NONE | NONE | PARTIAL |
| CDaR | FULL | FULL | FULL | NONE | PARTIAL | PARTIAL | NONE | PARTIAL | NONE | NONE | FULL |
| DRO | FULL | PARTIAL | NONE | NONE | NONE | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Factor Models | FULL | FULL | NONE | FULL | PARTIAL | NONE | PARTIAL | FULL | NONE | NONE | PARTIAL |
| Transaction Costs | FULL | FULL | PARTIAL | FULL | FULL | NONE | NONE | FULL | PARTIAL | FULL | FULL |
| Multi-period Optimization | NONE | NONE | NONE | FULL | PARTIAL | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Walk-forward | FULL | PARTIAL | NONE | FULL | FULL | NONE | NONE | FULL | NONE | NONE | NONE |
| Purged CV | FULL | NONE | NONE | NONE | PARTIAL | NONE | NONE | PARTIAL | NONE | NONE | NONE |
| Backtesting | PARTIAL | PARTIAL | NONE | FULL | FULL | NONE | NONE | FULL | PARTIAL | PARTIAL | PARTIAL |
| Performance Analytics | FULL | FULL | PARTIAL | FULL | FULL | FULL | PARTIAL | FULL | PARTIAL | FULL | FULL |
| Accounting | NONE | NONE | NONE | PARTIAL | PARTIAL | NONE | NONE | PARTIAL | FULL | FULL | FULL |
| Data Providers | NONE | NONE | NONE | PARTIAL | FULL | PARTIAL | FULL | FULL | FULL | PARTIAL | FULL |
| Experiment Tracking | PARTIAL | NONE | NONE | PARTIAL | PARTIAL | NONE | NONE | FULL | NONE | PARTIAL | NONE |
| ML | FULL | PARTIAL | NONE | NONE | PARTIAL | NONE | NONE | FULL | NONE | NONE | NONE |
| Agent Architecture | NONE | NONE | NONE | NONE | NONE | NONE | PARTIAL | PARTIAL | NONE | FULL | NONE |
| UI/UX patrimonial | NONE | NONE | NONE | NONE | PARTIAL | FULL | PARTIAL | PARTIAL | FULL | FULL | FULL |

Siglas: SK skfolio; RF Riskfolio; PPO PyPortfolioOpt; CVXP cvxportfolio; VBT vectorbt; QS QuantStats; OBB OpenBB; GF Ghostfolio; WF Wealthfolio; PP Portfolio Performance.

## Lacunas próprias

- cadastro brasileiro de instrumentos, calendários e tributação;
- passivo familiar e calendário de devolução;
- semântica ponto-no-tempo com quatro tempos e vintage;
- IPS versionado como restrição executável;
- reconciliação broker-ledger e trilha decisória unificada;
- decisão `NO_ACTION` comparável às alternativas de negociação.
