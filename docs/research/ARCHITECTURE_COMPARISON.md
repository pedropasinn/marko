# Comparação arquitetural

## Fronteiras observadas

| Contexto Marko | Melhor referência | Padrão aproveitado | O que permanece próprio |
|---|---|---|---|
| Accounting Truth | Portfolio Performance, Wealthfolio | eventos, snapshots, dinheiro exato, reconciliação | semântica brasileira e passivo |
| Data Truth | OpenBB, Qlib | provider registry, schema padrão, dataset/feature pipeline | quatro tempos, vintage e qualidade |
| Research Truth | skfolio, vectorbt, Qlib | estimator, temporal CV, recorder e artefatos | ModelRun canônico e gates |
| Decision Truth | Wealthfolio, cvxportfolio | draft/approve/record; política/custo/constraint | IPS, liability e DecisionPacket |
| Presentation | Ghostfolio, Wealthfolio | visão de holdings, drift, importação e saúde | explicações e discordância entre modelos |

## Arquitetura adotada

```text
providers -> canonical observations -> point-in-time datasets
                                         |
immutable activities -> ledger -> snapshots -> analytics
                                         |
IPS + liability + universe + constraints -> portfolio adapters
                                         |
model runs -> committee -> decision packet incl. NO_ACTION
                                         |
simulate -> draft -> human approval -> record -> reconcile
```

O núcleo é hexagonal: domínio puro no centro; storage, providers, solvers e bibliotecas são portas substituíveis. Accounting, Research e Decision são verdades distintas, ligadas por identificadores e versões, nunca por mutação implícita.

## Classificação transversal

| Capacidade | Classe | Motivo |
|---|---|---|
| modelos skfolio | B | dependência permissiva, mas domínio deve ficar estável |
| baselines PyPortfolioOpt | B | oracle independente e pequeno |
| métricas financeiras | C | controle de convenções e testes dourados |
| ledger/política/passivo | C | coração específico do produto |
| protocolos OpenBB/Qlib | D | boas fronteiras, plataformas grandes/copyleft |
| agentes e UX patrimonial | D | reaproveitar decisões, não código AGPL |
| vectorbt/Riskfolio/cvxportfolio | E | ambientes e finalidade de pesquisa |
| sinal LLM direto para ordem | F | ausência de evidência, controle e responsabilidade |
