# Changelog

As mudanças relevantes do Marko serão registradas aqui por versão.

## [Unreleased]

## [0.3.0] — 2026-08-20

### Adicionado

- portas de repositório e codecs JSON canônicos/versionados;
- PostgreSQL append-only para Activity, Observation, ModelRun e DecisionPacket;
- migrações transacionais com advisory lock e checksum;
- Parquet imutável para datasets de observações;
- backup, verificação e restore idempotente;
- scheduler shadow e reconciliação de evidências ponto-no-tempo;
- casos dourados de TWR com aportes, transferências, FX e corporate actions;
- comandos de persistência e shadow no CLI;
- job de integração PostgreSQL 16/Parquet.

### Segurança

- UPDATE e DELETE são bloqueados por triggers;
- conflito de identidade é detectado por hash;
- backup adulterado e schema desconhecido falham explicitamente;
- capital real e broker write adapter permanecem bloqueados.

## [0.2.1] — 2026-08-20

### Alterado

- configuração pública substituída por exemplo sintético; caso real passa por `MARKO_CASE_PATH` ou arquivo local ignorado;
- reversões validadas contra o payload original e refletidas nos lotes fiscais por `as_of`;
- matriz de campos por `ActivityKind` impede valores monetários sem efeito;
- moedas desconhecidas são rejeitadas;
- valuation informa completude, preços/FX ausentes, stale quotes e evidências;
- SIDRA preserva dimensões concorrentes e vintages usam hash do payload bruto;
- candidatos pós-validados são tipos próprios e únicos aceitos pela decisão;
- walk-forward usa pesos após drift e rejeita `step <= 0`;
- caixa virou entrada explícita do rebalanceador;
- juros do passivo usam `InterestTerms` estruturado;
- CI foi dividido em quality gate, adapters opcionais e provider smoke.

## [0.2.0] — 2026-08-20

### Adicionado

- transferências, FX, splits, grupamentos, spinoffs, amortizações e reversões;
- lotes FIFO e custo médio;
- snapshots e reconciliação;
- TWR, XIRR, drawdown e atribuição de caixa;
- configuração validável de Liability, IPS e Universe;
- providers BCB/SGS e IBGE/SIDRA;
- contratos para Tesouro Direto, ANBIMA e B3;
- baselines e adapters de otimização;
- ModelRun e Solver Registry;
- walk-forward, purge, embargo, custos, estabilidade e stress;
- DecisionPacket e cash-flow rebalancing;
- CLI `marko`.

### Validação

- 55 testes e 85% de cobertura;
- dois golden cases XIRR do Portfolio Performance;
- adapters skfolio e PyPortfolioOpt factíveis;
- consultas reais BCB e SIDRA.

## [0.1.0] — 2026-08-20

### Adicionado

- Money decimal e moeda explícita;
- Instrument Master, contas, activities e ledger append-only;
- Liability, IPS, Universe e Constraint Set;
- quatro coordenadas temporais e Data Vintage;
- auditoria de onze upstreams;
- oito spikes quantitativos reproduzíveis;
- doze ADRs iniciais.
