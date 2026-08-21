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

PostgreSQL append-only <-> codecs versionados <-> portas do domínio
Parquet imutável <------ datasets de pesquisa
Scheduler shadow ------> corte PIT ------> reconciliação de referências

Marko Console (React/TS/PWA) -> Read API FastAPI -> portas de leitura
                                      |                  |
                                demo sintético   PostgreSQL append-only
```

## Contextos

- `accounting`: dinheiro, instrumentos, contas, activities, posições, caixa e reconciliação.
- `policy`: passivos, IPS, universo e constraints.
- `data`: providers, observações temporais, qualidade e vintages.
- `research`: datasets, modelos, solvers, validação e ModelRun.
- `decision`: comitê, alternativas, `NO_ACTION`, draft, aprovação e auditoria.
- `persistence`: codecs, portas, PostgreSQL, Parquet, migrações, backup e restore validado.
- `shadow`: `ShadowRunRequest`, agenda determinística, `knowledge_cutoff`, diário append-only, reconciliação PIT e benchmarks operacionais.
- `read_api`: DTOs explícitos e consultas limitadas sobre Accounting, Research e Decision Truth; nenhuma rota de escrita.
- `apps/console`: superfície React/TypeScript/PWA somente leitura, com modos HTTP e sintético explicitamente distintos.

## Portas

- `MarketDataProvider` retorna observações canônicas, nunca DataFrames sem schema.
- `PortfolioModel` recebe snapshot imutável e devolve candidato + diagnóstico.
- `Solver` devolve status, tolerâncias e violações além dos pesos.
- portas próprias persistem Activity, Observation, ModelRun, `ShadowRunRequest` e DecisionPacket append-only.
- `ReadStore` expõe apenas consultas; a API não reutiliza portas de escrita.
- `BrokerAdapter` importa confirmações; não é fonte exclusiva da verdade.

Objetos de skfolio, PyPortfolioOpt ou qualquer upstream ficam contidos nos adapters.

## Superfície pública

O [Console](https://marko-console.vercel.app) e a [Read API](https://marko-api.vercel.app/api/v1/status) são deploys sintéticos. O Neon associado contém exclusivamente dados sintéticos em `gru1`, com Neon Auth habilitada, mas dados reais continuam proibidos até a autenticação ser efetivamente aplicada no caminho completo e existir IPS privado.

O Console já suporta login e obtém o JWT oficial do Neon Auth sem persistir a credencial. A Read API valida tokens EdDSA pelo JWKS do Neon, exige `sub`/expiração, aplica allowlist e falha fechada. O modo privado só deve ser habilitado após as duas identidades serem cadastradas fora do Git.

A direção visual do Console usa como referência os padrões de produto estudados no Ghostfolio e no Untitled UI — hierarquia clara, disclosure progressivo e estados honestos — sem copiar código, componentes ou identidade visual.
