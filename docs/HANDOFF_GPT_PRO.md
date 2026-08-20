# Handoff completo do Marko para GPT Pro

Use este documento junto com `CONTEXT.md`, `docs/adr/` e o código. Ele descreve o estado real do projeto em 20/08/2026. Não presuma que itens marcados como pendentes já existem.

## Pedido original

Construir um gestor quantitativo pessoal orientado a um capital inicial associado a um passivo e a aportes periódicos. Valores, datas e relações reais pertencem apenas à configuração privada. O sistema deve manter uma tese, contabilizar patrimônio e passivo, comparar modelos, medir risco, propor alocações e explicar decisões. IA produz evidências, features e hipóteses; nunca converte notícias diretamente em ordens.

O princípio do produto é:

> Tomar boas decisões mesmo quando as previsões estiverem erradas.

Não existe autorização para investir, recomendar uma carteira real ou enviar ordens.

## Estado atual

O pacote está na versão `0.3.0` em validação. Foram concluídos:

1. arqueologia de onze projetos open source;
2. kernel contábil e de política;
3. analytics essenciais;
4. separação entre configuração pública sintética e caso pessoal privado;
5. gateway brasileiro ponto-no-tempo;
6. Portfolio Lab com baselines e adapters;
7. ModelRun e Solver Registry;
8. validação temporal e stress;
9. DecisionPacket com `NO_ACTION`;
10. cash-flow rebalancing sem vendas;
11. reversões contábeis refletidas nos lotes por `as_of`;
12. valuation completo/incompleto com proveniência;
13. candidatos pós-validados obrigatórios na decisão.
14. contratos de serialização JSON canônicos e versionados;
15. portas de repositório sem dependência de driver no domínio;
16. PostgreSQL append-only para Activity, Observation, ModelRun e DecisionPacket;
17. datasets Parquet imutáveis para observações;
18. migrações com advisory lock e checksum;
19. backup verificado e restore idempotente;
20. scheduler shadow e reconciliação de referências ponto-no-tempo.
21. casos dourados de TWR com aportes, transferências, FX e corporate actions.

Validação atual:

- 92 testes locais aprovados, 2 integrações condicionais e 84% de cobertura;
- Ruff aprovado;
- MyPy estrito aprovado;
- Parquet exercitado localmente;
- PostgreSQL 16 coberto por job dedicado do CI;
- BCB/SGS e IBGE/SIDRA exercitados ao vivo;
- adapters skfolio e PyPortfolioOpt retornando candidatos factíveis;
- onze snapshots upstream limpos e oito spikes reproduzíveis preservados.

## Três verdades separadas

### Accounting Truth

Fatos efetivamente ocorridos: caixa, posições, taxas, impostos, transferências, FX, corporate actions e reconciliação.

### Research Truth

Resultados reproduzíveis de datasets, modelos, parâmetros, seeds e solvers. Um resultado de pesquisa não altera o ledger.

### Decision Truth

Alternativas apresentadas, evidências, aprovação, execução e reconciliação. Draft não equivale a ordem; aprovação não equivale a execução.

## Módulos implementados

### `money.py`

Dinheiro baseado em `Decimal`, quantizado por moeda. Operações entre moedas diferentes falham. Float só é usado em matrizes e retornos do laboratório.

### `activities.py` e `ledger.py`

Activities imutáveis e append-only:

- depósitos e retiradas;
- compras e vendas;
- dividendos, juros, taxas e impostos;
- transferências de caixa e posições;
- conversões FX com duas pernas;
- deliveries;
- splits e grupamentos;
- spinoffs;
- amortizações;
- reversões que preservam o evento original.

Caixa e posições são projeções. `sequence` resolve causalidade quando timestamps coincidem. IDs duplicados são rejeitados.

### `taxlots.py`

Lotes FIFO e custo médio. Compra incorpora taxas e impostos ao custo. Venda calcula proceeds líquidos, custo alocado e ganho realizado. Split altera quantidade sem alterar custo total. Amortização reduz base. Entradas sem base conhecida bloqueiam o cálculo.

### `snapshots.py` e `reconciliation.py`

Snapshots fixam `as_of`, último evento incluído, caixa, posições, cotações e valor de liquidação. Reconciliação compara snapshot e extrato no mesmo instante e relata diferenças de caixa e quantidade.

### `analytics.py`

Implementações próprias de:

- TWR;
- XIRR;
- drawdown máximo, pico, vale e recuperação;
- atribuição de taxas, impostos e rendimentos.

Dois casos Excel de XIRR do Portfolio Performance foram convertidos em golden tests.

### `liabilities.py`, `policy.py` e `case_config.py`

Representam Liability, fluxos, funding ratio, shortfall, IPS, Universe e Constraint Set. `PersonalCase` converte uma configuração completa em Liability, IPS e Universe.

O arquivo `config/personal-case.example.toml` contém somente valores sintéticos. O caso real deve ser fornecido por `MARKO_CASE_PATH` ou arquivo local ignorado. Os fatos do pedido original não são versionados em configuração pública.

Campos desconhecidos permanecem vazios. O CLI retorna `ready: false` até que sejam preenchidos.

### `temporal.py` e `data_gateway.py`

Toda observação possui:

- `effective_at`;
- `observed_at`;
- `available_at`;
- `ingested_at`;
- fonte;
- unidade;
- dimensões;
- vintage;
- flags de qualidade.

Providers:

- BCB/SGS operacional;
- IBGE/SIDRA operacional;
- Tesouro Direto com endpoint JSON injetável;
- ANBIMA e B3 com endpoint, schema e token injetáveis;
- calendário de dias úteis;
- store idempotente com consultas `as_known_at` e revisão mais recente.

As respostas BCB/SIDRA consultadas não expõem o instante histórico de publicação. O adapter usa a ingestão como disponibilidade conservadora e marca `availability_conservative`.

O endpoint JSON legado do Tesouro Direto respondeu HTTP 410. Não foi inventado um substituto. ANBIMA/B3 ainda precisam de credenciais e contratos atuais.

### `portfolio_lab.py`

Contrato próprio `PortfolioProblem -> PortfolioCandidate` com:

- `NO_ACTION`;
- equal weight;
- inverse volatility;
- minimum variance com shrinkage e projected gradient;
- risk budgeting;
- adapter skfolio;
- adapter PyPortfolioOpt;
- pós-validação de pesos, soma, finitude e bounds.

Objetos upstream não atravessam a fronteira do domínio.

### `research_registry.py`

`ModelRun` fixa:

- código;
- ambiente;
- fingerprint do dataset;
- IPS e versão;
- Universe e versão;
- parâmetros;
- seed;
- solver, versão e tolerâncias;
- candidato e violações.

Registries são idempotentes e detectam conflitos de identidade.

### `validation.py`

Inclui:

- walk-forward;
- purge;
- purged k-fold com embargo;
- retorno bruto e líquido de custo;
- turnover;
- sensibilidade por perturbação;
- estabilidade de pesos;
- choques por ativo;
- stress de correlações.

Validação precede modelos avançados.

### `decision.py`

`DecisionPacket` exige a alternativa `NO_ACTION`. O modo `cash_flow_only`:

- usa apenas o aporte;
- não vende;
- prioriza maiores déficits contra o alvo;
- respeita peso máximo;
- respeita lotes inteiros e negociação mínima;
- estima custos;
- verifica liquidez mínima e turnover;
- preserva drafts inviáveis com razões explícitas.

O resultado não altera ledger nem envia ordens.

### `persistence/`

Contém:

- portas para Activity, Observation, ModelRun e DecisionPacket;
- codecs explícitos `schema@version` com JSON canônico e SHA-256;
- `PostgresStore` com append idempotente, conflito por hash e leitura verificada;
- migrações SQL numeradas, transacionais, serializadas e protegidas por checksum;
- `ParquetObservationStore` para datasets imutáveis de pesquisa;
- backup atômico, verificação de hash e restore idempotente.

PostgreSQL é a fonte operacional. Parquet não sobrescreve Accounting ou Decision Truth.

### `shadow.py`

Agenda ciclos mensais de modo determinístico, preservando timezone, instante agendado e `knowledge_cutoff`. A reconciliação exige ModelRuns exatos e rejeita evidência que ainda não estava disponível quando o DecisionPacket foi criado.

O módulo não aprova nem executa operações.

## Upstreams estudados

Os clones ficam fora do produto, em `/home/pedro/repo/marko-references`. O snapshot exato está em `upstreams.lock.json`.

| Projeto | Decisão |
|---|---|
| skfolio | motor principal atrás de adapter |
| PyPortfolioOpt | oráculo independente e adapter secundário |
| Riskfolio-Lib | laboratório/oráculo de risco avançado |
| cvxportfolio | referência de custos e otimização multi-período; GPL isolada |
| vectorbt | ferramenta de pesquisa; Commons Clause |
| QuantStats | oráculo de métricas |
| OpenBB | referência para provider registry; AGPL |
| Qlib | referência futura para ML/experiment workflow |
| Ghostfolio | referência de produto; AGPL |
| Wealthfolio | referência de ledger, drift e permissões de agente; AGPL |
| Portfolio Performance | principal referência contábil e de performance; EPL |

Achados relevantes:

- skfolio combina portfolio optimization, validação temporal, CPCV e stacking sob uma API coerente;
- Riskfolio tem catálogo mais amplo de medidas de risco, Kelly, grafos e uncertainty sets;
- cvxportfolio é a melhor referência para target -> trades mediante custo, turnover e risco;
- Wealthfolio inspirou `read -> simulate -> draft -> approve -> record`;
- Portfolio Performance inspirou dinheiro exato, eventos, snapshots, reconciliação e golden cases;
- PyPortfolioOpt 1.6.0 usa um símbolo privado removido no SciPy 1.18 em seu HRP;
- o spike minimum variance encontrou pesos próximos entre skfolio e Riskfolio e maior diferença no PyPortfolioOpt, embora o valor de risco fosse semelhante.

Nenhum código AGPL/GPL/EPL/Commons Clause foi incorporado ao núcleo.

## Spikes

`research/spikes/` contém:

1. skfolio minimum variance;
2. Riskfolio minimum variance;
3. PyPortfolioOpt minimum variance;
4. Black–Litterman;
5. HRP;
6. CVaR;
7. cvxportfolio com custos;
8. QuantStats.

Todos registram versão Python, pacote, commit, hash do dataset, seed, configuração, solver, duração e resultado.

## Comandos

```bash
uv sync --group dev
uv run pytest --cov=marko --cov-report=term-missing
uv run ruff check .
uv run mypy
uv run marko status
uv run marko fetch-bcb 1178 --start 2026-08-18 --end 2026-08-19 --unit "% a.a."
uv run marko fetch-sidra IPCA --table 1737 --variable 2266 --period "last 1"
uv sync --group dev --extra persistence
MARKO_DATABASE_URL=postgresql://... uv run marko db-migrate
MARKO_DATABASE_URL=postgresql://... uv run marko backup var/private/backup.json
uv run marko backup-verify var/private/backup.json
uv run marko shadow-due --day 20 --after 2026-07-20T13:00:00+00:00 --until 2026-08-20T13:00:00+00:00
```

## Informações ainda necessárias do proprietário

Não inventar respostas. Solicitar:

1. data de origem do empréstimo;
2. vencimento;
3. juros ou indexação;
4. possibilidade de cobrança antecipada;
5. liquidez mínima;
6. drawdown máximo tolerável;
7. residência fiscal;
8. corretoras disponíveis;
9. instrumentos disponíveis.

Somente depois disso gerar IPS real. Mesmo com o IPS completo, capital real continua bloqueado até shadow operation e revisão humana.

## Próxima sequência recomendada

1. validar PostgreSQL 16 no CI e fechar a v0.3.0;
2. obter os nove dados pessoais em configuração privada e gerar IPS/Liability;
3. adicionar casos dourados de TWR multimoeda;
4. implementar regras fiscais brasileiras por instrumento/prazo;
5. configurar endpoints/credenciais de Tesouro, ANBIMA e B3;
6. definir benchmarks, periodicidade e duração mínima da operação shadow;
7. operar shadow portfolio com CDI, 1/N e carteira real como benchmarks;
8. só então avançar para Black–Litterman, HRP/HERC/NCO, CVaR/CDaR e ensemble dentro do produto.

## Regras para qualquer continuação

- nunca tratar backtest como evidência suficiente;
- nunca permitir que pesquisa altere accounting;
- nunca omitir `NO_ACTION`;
- nunca aceitar status do solver sem pós-validar constraints;
- nunca usar dado revisado como se estivesse disponível no passado;
- nunca transformar saída de LLM diretamente em ordem;
- nunca preencher informações financeiras pessoais por suposição;
- nunca persistir valuation parcial como patrimônio total;
- nunca encaminhar `PortfolioCandidate` bruto à decisão;
- nunca incorporar código de licença incompatível sem revisão jurídica e ADR.
- nunca reescrever um fato persistido para corrigir o histórico;
- nunca restaurar backup ou dataset sem verificar schema e hash;
- nunca executar ciclo shadow com evidência posterior ao DecisionPacket.
