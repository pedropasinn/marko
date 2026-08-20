# Arquitetura

```text
Adapters de dados -> Observações canônicas -> Vintages/Datasets
                                                |
Adapters de custódia -> Activities -> Ledger -> Snapshots/Analytics
                                                |
IPS + Liability + Universe + Constraints -> Portfolio Lab
                                                |
Model Runs -> Committee -> Decision Packet -> Rebalance/Execution draft
                                                |
                         aprovação humana -> registro -> reconciliação
```

## Contextos

- `accounting`: dinheiro, instrumentos, contas, activities, posições, caixa e reconciliação.
- `policy`: passivos, IPS, universo e constraints.
- `data`: providers, observações temporais, qualidade e vintages.
- `research`: datasets, modelos, solvers, validação e ModelRun.
- `decision`: comitê, alternativas, `NO_ACTION`, draft, aprovação e auditoria.

## Portas

- `MarketDataProvider` retorna observações canônicas, nunca DataFrames sem schema.
- `PortfolioModel` recebe snapshot imutável e devolve candidato + diagnóstico.
- `Solver` devolve status, tolerâncias e violações além dos pesos.
- `LedgerRepository` persiste events append-only e snapshots derivados.
- `BrokerAdapter` importa confirmações; não é fonte exclusiva da verdade.

Objetos de skfolio, PyPortfolioOpt ou qualquer upstream ficam contidos nos adapters.
