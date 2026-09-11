# Plano de reaproveitamento

## Proposta após auditoria de 11/09/2026

Estado: primeiro incremento implementado em 11/09/2026. Integridade econômica corrigida, skfolio 1.0.6 incorporado por adapters de mínima variância, risk budgeting, HRP e CVaR; campanha prospectiva com equal-weight e três benchmarks. Não há integração de TradingAgents na autoridade de negociação. Evidência histórica das falhas em [`UPSTREAM_AUDIT.md`](UPSTREAM_AUDIT.md); regressões atuais em `tests/test_validation.py`, `test_decision.py`, `test_portfolio_lab.py` e `test_experiment_*.py`.

A campanha aprovada é 14/09/2026–14/03/2027, US$ 10.000 por modelo, ETFs em USD, sem aportes/alavancagem. Orçamento de APIs: zero. Revisores independentes de IA usam somente a assinatura Codex local quando disponível; regras determinísticas são rotuladas separadamente. TradingAgents permanece pesquisa futura: uma contribuição de LLM teria de vencer uma ablação prospectiva e preservar dados ponto-no-tempo, custos e versões congeladas.

O Marko deve possuir o significado financeiro e a autoridade dos dados/decisões. Bibliotecas podem possuir a implementação matemática, os relatórios e ferramentas de pesquisa. O ADR 002 permite esse desenho: independência do domínio não implica independência de implementação.

### Mapa concreto de aproveitamento

Os caminhos de fonte abaixo são relativos ao respectivo clone em `/home/pedro/repo/marko-references`.

| Referência | Componente aproveitável | Forma proposta | Verificação para aceitar |
|---|---|---|---|
| skfolio | `src/skfolio/optimization/convex/{_mean_risk,_risk_budgeting}.py`, `optimization/cluster`, `prior`, `model_selection/_walk_forward.py` | Motor principal por adapters: covariância/shrinkage, mínima variância, risk budgeting, HRP/HERC, CVaR; depois BL. Consumir splits upstream, preservando semântica de carteira/custos no contrato. | Mesma matriz, bounds, frequência, covariância e solver; status real, objetivo e feasibility. Falhas não podem virar candidatos válidos. |
| PyPortfolioOpt | `pypfopt/{risk_models,black_litterman,discrete_allocation}.py` | Oráculo independente; testar alocação discreta como candidato à tradução peso→quantidade. | Comparar restrições e objetivo, não só pesos. Não usar `HRPOpt` com SciPy 1.18 enquanto persistir `_LINKAGE_METHODS`. Alocação discreta não modela automaticamente posições existentes e tributação. |
| Riskfolio-Lib | `riskfolio/src/Portfolio.py`: `rp_optimization`, `wc_optimization`; `RiskFunctions.py` | Ambiente de pesquisa com entradas/saídas canônicas; oráculo de contribuições de risco e cauda. | Matriz e convenções alinhadas; limites, convergência e dependências transitivas verificados. |
| QuantStats | `quantstats/stats.py`, `reports.py::html` | Dependência opcional de relatório/métricas, evitando reimplementar catálogo inteiro. | Receber série de retornos pronta; fixar frequência, taxa livre de risco, convenção de CVaR, dividendos/custos e cash flows. Relatório não busca cotação implicitamente. |
| cvxportfolio | `cvxportfolio/{simulator,costs,policies}.py`: MarketSimulator, TransactionCost, MultiPeriodOptimization | Executável de laboratório para comparar evolução de patrimônio e políticas com custos; JSON/Parquet na fronteira. | Mesmo calendário e instante de execução, custos proporcionais/impacto, holdings e caixa. GPL e conflito CVXPY exigem avaliação antes de incorporação ao produto. |
| vectorbt | `vectorbt/portfolio/base.py::from_orders/from_signals`, splitters e records | Bancada opcional para varrer cenários, com budget de hipóteses e holdout. | Taxas/slippage explícitos; resultados confrontados com um simulador de referência. Commons Clause impede presumir adoção comercial livre. |
| OpenBB | `openbb_platform/core/openbb_core/provider/abstract/fetcher.py`, providers e standard models | Avaliar usar conectores existentes através de serviço/adapter, se houver fonte útil, em vez de reconstruir cada fornecedor internacional. | Transporte `transform_query→extract→transform_data`; acrescentar quatro tempos, vintage e qualidade do Marko. Licença e termos de cada fonte antes da integração. |
| Qlib | `qlib/data/data.py::LocalPITProvider`, `workflow/task/gen.py::RollingGen`, `workflow/recorder.py::MLflowRecorder` | Laboratório separado quando houver pesquisa preditiva de features/alpha. É MIT: o adiamento se deve à complexidade e ao encaixe, não a proibição genérica. | PIT de publicação/revisão, rolling sem vazamento, custos e artefatos versionados. Não criar uma segunda autoridade contábil. |
| Wealthfolio | `crates/core/src/portfolio/allocation_targets/{optimizer,drift_service,rebalance_service}.rs` e fixtures de caixa | Casos de referência para cash-flow-only, cenários de venda, bandas, lotes e custos. Considerar aplicativo acompanhante por exportação antes de duplicar toda a UX patrimonial. | Fixtures com caixa insuficiente para taxas, mínimo de negociação, quantidades inteiras e drift. AGPL: estudo não autoriza incorporar código sem cumprir condições. |
| Ghostfolio | `apps/api/src/app/endpoints/mcp`, importação, regras e serviços de portfolio | Referência/aplicação acompanhante para importação e consulta; MCP novo merece análise específica de permissões. | Verificar o calculador realmente usado: stubs de TWR/MWR/ROI ainda lançam `Method not implemented`; isso não significa que todo o app carece de performance. |
| Portfolio Performance | `name.abuchen.portfolio/src/.../math/IRR.java`, `snapshot/PerformanceIndex.java`, `snapshot/trail`; fixtures JUnit | Oráculo contábil de fluxos, FX, corporate actions e arredondamento. Reaproveitar especificações econômicas e comparar resultados por exportação. | Casos dourados executados nos dois sistemas; explicar diferenças de timing/cash flow. EPL permanece no escopo da revisão de incorporação. |
| TradingAgents | `graph/setup.py`, `agents/schemas.py`, `graph/checkpointer.py`, `agents/utils/memory.py` | Serviço de pesquisa que produz evidências e hipóteses; grafo/módulos reutilizados conforme licença e compatibilidade. | Disponibilidade comprovada de documentos, nenhum estado futuro na memória, saída com referências, budget LLM e ablação sem LLM/analista único/debate. Não aceitar sizing textual como limite executável. |

Separar processos não dispensa análise de licença. A proposta mantém a fronteira conservadora do ADR 008; eventual incorporação de copyleft ou promoção de categoria pede decisão documentada. A licença raiz de TradingAgents também não substitui a análise de suas dependências.

### Entregas na ordem de dependência

1. **Integridade econômica.** Uma carteira `NO_ACTION` precisa coincidir com evolução independente de quantidades e preços, sem rebalanceamentos escondidos. Custos entram no orçamento; não convergência bloqueia candidato. Validador temporal rejeita treino futuro e define tratamento de janelas sobrepostas. Drift fora dos bounds não impede avaliar a correção. Targets preservam política/universo/transformação a partir dos ModelRuns.
2. **Motor upstream.** Fixar skfolio 1.0.6 em ambiente de migração; usar adapters para modelos já exercitados no spike 009. `EWMu/EWCovariance.alpha`, `WalkForward.expend_train`, `FactorModel`, `ReturnDistribution.cholesky` e `UncertaintySet` mudaram no 1.0: inventariar uso antes de migrar. O adapter mínimo existente passou no smoke da nova fonte; os modelos internos só permanecem se tiverem papel explícito de baseline didático/oráculo.
3. **Pesquisa comparável.** Escolher protocolo de retornos, custos, impostos quando aplicáveis, rebalancing e benchmarks antes de comparar motores. Registrar lock de pacotes/solver, matriz/covariância, calendário, seed e fingerprints verificáveis. Reusar QuantStats para apresentação depois da validação.
4. **Um ciclo shadow utilizável.** Entrada versionada → política/constraints → retornos/PIT → candidatos → simulação de aporte/custos → DecisionPacket → revisão → reconciliação. Implementar um comando para esse fluxo, hoje composto manualmente por Python. Dados sintéticos ou públicos de pesquisa bastam para a próxima entrega; a falta de ANBIMA/B3 não bloqueia esse laboratório.
5. **LLM como hipótese testável.** Adaptar TradingAgents para ler snapshots, não obter silenciosamente dados atuais. Registrar tempo de publicação e vintage dos fundamentos. Só converter evidências em views quantitativas quando confiança/horizonte estiverem calibrados. Comparar ganho líquido de custos e instabilidade contra baseline simples em holdout prospectivo.

### O que permanece específico do Marko

Ledger/Decimal, identities e reversões, IPS e passivos, elegibilidade de instrumentos, tradução das restrições, semântica temporal, tributação aplicável, trilha de decisão e aprovação humana. Essas partes devem chamar os motores e validar suas saídas. Não há benefício em substituir um ledger auditável por memória textual de agente.

## Plano original — 20/08/2026

## Adotar por dependência

- `skfolio`: modelos de alocação, estimadores e validação temporal.
- `PyPortfolioOpt`: implementação independente de baselines e Black–Litterman.

## Usar como oráculo

- `Riskfolio-Lib`: risk budgeting, medidas de cauda e restrições avançadas.
- `cvxportfolio`: política multi-período, custos, turnover e restrições.
- `QuantStats`: conferência de métricas.
- `Portfolio Performance`: transações, TWR, IRR, drawdown e custo fiscal.

## Reproduzir o padrão, não o código

- `OpenBB`: modelo padronizado, fetcher e registry de provedores.
- `Qlib`: dataset ponto-no-tempo, experiment/recorder e rolling tasks.
- `Wealthfolio`: cenários de rebalanceamento, drift e permissões read/draft/write.
- `Ghostfolio`: importação, regras e navegação patrimonial.

## Isolar

- `vectorbt`: ambiente de pesquisa separado por restrição de licença e superfície ampla.
- todo copyleft: nunca importado pelo núcleo sem decisão jurídica explícita.
