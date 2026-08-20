# Changelog

As mudanças relevantes do Marko serão registradas aqui por versão.

## [Unreleased]

### Planejado

- persistência do domínio;
- regras fiscais brasileiras;
- shadow portfolio;
- conectores autenticados.

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
