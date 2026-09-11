# Auditoria dos upstreams

Atualização posterior à auditoria, 11/09/2026: os achados financeiros abaixo descrevem o snapshot anterior à correção. Foram corrigidos e protegidos por regressões; o spike 009 reexecutado agora retorna `no_action=0`, rejeita solver inviável, treino futuro e política/targets divergentes, e aceita avaliar drift fora dos bounds. O `result.json` original foi preservado como evidência histórica. A integração skfolio foi atualizada para 1.0.6; protocolo prospectivo em `config/shadow-usd-2026.toml`. A falha ponto-no-tempo reproduzida no helper do TradingAgents continua sendo limite para sua integração.

## Revisão executável — 11/09/2026

Marko auditado: `934ab2d65821c783cdcfb684c8728ed0228f2fee`, v0.3.2, igual ao HEAD remoto consultado. A arquitetura faz sentido, mas a maturidade operacional descrita em `STATUS.md` excede o que os testes demonstram para pesquisa e decisão. O projeto já serve como laboratório sintético e núcleo contábil; ainda não é um gestor pessoal validado.

Escopo: inspeção de fonte, testes, configurações e referências; atualização dos clones; simulação local. Nenhuma mudança no motor financeiro, configuração privada, dependências do produto ou deploy. Os achados abaixo permanecem abertos.

### Achados prioritários

| Prioridade | Achado e reprodução | Consequência | Local |
|---|---|---|---|
| P1 | `NO_ACTION` informa +12,5% quando o buy-and-hold rende 0%. Carteira 50/50; A sobe 100% e cai 50%, B fica parado. | O retorno usa pesos constantes diariamente; o drift usa quantidades constantes. São duas estratégias diferentes. Há rebalanceamento implícito sem custo. | `src/marko/validation.py`, `evaluate_walk_forward` |
| P1 | Com R$ 2.000 de aporte e custo de 5 bps, a proposta de compra desaparece; com custo zero ela existe. | O algoritmo tenta gastar todo o aporte antes de adicionar a taxa. Se ultrapassa o caixa, pula a compra em vez de reduzir a quantidade. No exemplo, R$ 1.999 + R$ 1 de custo caberiam. | `src/marko/decision.py`, `_cash_flow_only` |
| P1 | Um candidato com `solver_status="infeasible"` é aceito como validado. | Feasibility dos pesos não comprova sucesso do solver; também não há gate de convergência/qualidade da solução. O adapter skfolio devolve o texto genérico `upstream`. | `src/marko/portfolio_lab.py`, `check_candidate`; `research_registry.py` |
| P1 | `evaluate_walk_forward` aceita treino posterior ao teste; drift acima do limite aborta a janela seguinte. | O avaliador confia nos índices recebidos e confunde estado atual com carteira-alvo admissível. Um estado fora do limite deveria permitir avaliar correção ou sinalizar violação. | `validation.py`; `PortfolioProblem.__post_init__` |
| P1 | Um pacote aceita outra política e outros targets junto da referência de um ModelRun validado. | A referência é íntegra, mas não prova que a proposta implementa aquela política/solução. Combinação de modelos também precisaria de transformação rastreável. | `decision.py`, `CashFlowRebalancer.build_packet` |
| P2 | `InvestmentPolicy` e `ConstraintSet` existem, mas não há compilador ligando a política e os passivos ao PortfolioProblem/DecisionPacket. | A aplicação ainda depende do chamador para transportar corretamente limites, universo e objetivos. Orientação a passivos está sobretudo no domínio. | `policy.py`, `case_config.py`, `portfolio_lab.py` |
| P2 | O caso de um único ativo é aceito por PortfolioProblem, mas MinimumVariance falha com covariância escalar. | A fronteira pública do laboratório admite um problema que o solver interno não suporta. | `portfolio_lab.py`, `MinimumVariance.solve` |

Reprodução e saída: [`009-current-audit/run.py`](../../research/spikes/009-current-audit/run.py), [`result.json`](../../research/spikes/009-current-audit/result.json). Os booleanos `accepted` registram vulnerabilidades reproduzidas; não são aprovação do comportamento.

O teste de integração existente `tests/test_end_to_end.py` verifica as referências e a presença das alternativas, mas não exige que uma compra economicamente viável seja proposta. O teste do walk-forward confere a fórmula implementada, sem confrontá-la com uma evolução independente de caixa e posições. Isso explica por que a suíte passa junto com os contraexemplos.

### O que foi efetivamente verificado

- Backend: 156 testes aprovados, 3 ignorados. Os três dependem de `MARKO_TEST_POSTGRES_DSN`; não foram exercitados contra banco nesta auditoria. O adapter opcional também foi testado diretamente com a fonte atual do skfolio.
- Console: 8 testes aprovados, TypeScript e build aprovados; aviso de bundle acima de 500 kB. Não houve auditoria visual completa ou revisão de acessibilidade.
- API pública: `/api/v1/status` respondeu `mode=postgres`, `synthetic=true`. Console respondeu HTTP 200. Isso confirma disponibilidade, não prontidão privada.
- `marko status`: `ready=false`, nove campos ausentes. Não foi necessário ler segredos.
- Uma primeira execução de pytest ficou presa no sandbox antigo. Foi encerrada; a execução fora dele terminou em 6,13 s. Não classificada como defeito do produto.
- Não foram repetidos testes de restore, segurança de deploy, migração de banco ou histórico econômico real.

### Simulação realizada

252 retornos diários sintéticos, seed 42, três ativos abstratos. A volatilidade e a média são parâmetros artificiais; os nomes não representam produtos financeiros. Limite de 80% por ativo.

| Modelo executado com a fonte atual do skfolio | A | B | C |
|---|---:|---:|---:|
| Mínima variância pelo adapter existente do Marko | 80,00% | 11,98% | 8,02% |
| Risk budgeting upstream | 63,63% | 20,92% | 15,45% |
| HRP upstream | 80,00% | 15,00% | 5,00% |
| CVaR upstream | 80,00% | 11,45% | 8,55% |

A mínima variância virou um ModelRun e depois um DecisionPacket com `NO_ACTION` e `cash_flow_only`, partindo de R$ 50.000 fictícios e aporte de R$ 2.000. Sem custo, propôs comprar R$ 2.000 de A. Com 5 bps, deixou todo o aporte em caixa, reproduzindo o defeito acima. Não houve aprovação ou execução de ordem.

Comando usado, a partir da raiz do Marko:

```bash
PYTHONPATH=/home/pedro/repo/marko-references/skfolio/src:/home/pedro/repo/marko/src \
  research/.venv-quant/bin/python research/spikes/009-current-audit/run.py
```

A fonte executada é skfolio `029ae0b`, que declara 1.0.6. A distribuição instalada no ambiente continua 0.20.2: o teste usa `PYTHONPATH`, sem substituir o ambiente. O JSON registra ambos. SciPy 1.18.0, scikit-learn 1.9.0, CVXPY 1.9.2 e CLARABEL 0.11.1 estavam presentes. Este smoke de compatibilidade não equivale a resolver, empacotar e certificar o novo conjunto de dependências.

### Atualização das referências

Os onze clones estavam limpos. Foram consultados no GitHub e avançados somente por fast-forward quando havia atualização. TradingAgents foi clonado separadamente. Todos terminaram alinhados ao tracking branch; versões abaixo são as declaradas pela fonte, não necessariamente uma release imutável.

| Projeto | Antes → agora | Commit auditado | Observação |
|---|---|---|---|
| skfolio | 0.20.2 → 1.0.6 | `029ae0b` | Alterações importantes de API e módulos fatoriais/atribuição |
| Wealthfolio | 3.7.0 → 3.9.0 | `2a2d13c97` | Evolução de caixa, reconciliação, ativos e produto |
| Ghostfolio | 3.56.0 → 3.69.0 | `bef1c0d` | Novos endpoints MCP e evolução de API/atividades |
| Portfolio Performance | 0.87.1-SNAPSHOT → mesma versão declarada | `0975616970` | Código atualizado apesar da versão igual |
| TradingAgents | novo clone | `be952b8` | Commit menciona v0.4.2; pyproject ainda declara 0.4.0 |
| Riskfolio-Lib | 7.3.0, sem novo HEAD | `632a9e4` | Laboratório/oráculo |
| PyPortfolioOpt | 1.6.0, sem novo HEAD | `a6638d2` | HRP ainda acessa API privada removida do SciPy |
| cvxportfolio | versão dinâmica, sem novo HEAD | `351c782` | Ambiente separado, GPL |
| vectorbt | 1.1.0, sem novo HEAD | `34b6d59` | Commons Clause permanece |
| QuantStats | 0.0.81, sem novo HEAD | `fbd10da` | Candidato a relatório/métricas por dependência |
| OpenBB | core 1.6.13, sem novo HEAD | `3e071fc` | Conectores externos; AGPL |
| Qlib | versão dinâmica, sem novo HEAD | `79633dd` | PIT/rolling/ML; MIT |

O lock registra o snapshot atual e preserva o anterior em `historical_snapshots`. Os spikes 001–008 e suas fichas originais continuam evidência do snapshot de agosto; não foram reexecutados nem renomeados para aparentar atualização.

### Onde o reaproveitamento está aquém do plano

O plano escolheu skfolio como motor principal, mas `portfolio_lab.py` contém projected gradient próprio e risk budgeting iterativo próprio, além de apenas dois adapters de mínima variância. HRP, Black–Litterman e CVaR aparecem nos spikes, não no fluxo normal. `validation.py` reimplementa splits e avaliação. QuantStats foi classificado para reimplementação de métricas mesmo sendo permissivo.

O ADR 002 exige domínio independente de upstreams. Isso é compatível com chamar bibliotecas inteiras atrás de adapters; não exige reimplementar seus algoritmos. Decimal, ledger, passivos, política, cortes temporais e aprovação continuam responsabilidades adequadas do Marko.

O cadastro de `ModelRun` também merece complemento: solver, seed e hash de dados são fornecidos pelo chamador. O fingerprint de ambiente cobre poucos pacotes e não fixa automaticamente SciPy/CVXPY/BLAS. É um registro útil, mas ainda não uma cápsula suficiente para reproduzir qualquer execução.

### TradingAgents: utilidade e limites

Fonte auditada: [commit be952b8](https://github.com/TauricResearch/TradingAgents/tree/be952b8eccb49720509af544c6675233bc1f10d0). Componentes aproveitáveis: `graph/setup.py`, `graph/analyst_execution.py`, `agents/schemas.py`, `agents/managers/portfolio_manager.py`, `graph/checkpointer.py`, `agents/utils/memory.py` e testes `test_*lookahead.py`/`test_memory_pointintime.py`.

O grafo coordena analistas, debate bull/bear, trader e debate de risco; `propagate(ticker, date)` retorna estado e rating. Há schemas tipados, checkpoint, extração determinística de rating e memória com data de resolução. O Portfolio Manager ainda decide por LLM sobre relatórios; não é um solver de limites patrimoniais. Sizing e horizonte permanecem majoritariamente texto. O caminho inspecionado salva relatório/memória e retorna rating; não demonstra o simulador completo descrito no paper.

A versão atual corrige vazamentos de FRED, notícias, dados sociais, perfil empresarial e memória. Os testes dessas correções foram lidos, não executados integralmente. A leitura do README isoladamente daria uma imagem desatualizada de alguns desses pontos.

Mesmo assim, `_filter_reports_by_date` em `dataflows/alpha_vantage_fundamentals.py` usa `fiscalDateEnding <= curr_date`. Um trimestre encerrado em 31/03 e divulgado em 01/05 passa numa análise de 01/04. O spike extrai e executa essa função real com payload sintético, sem inicializar o grafo. Em Yahoo, `filter_financials_by_date` também usa a data da coluna do balanço. Encerramento fiscal não prova publicação; faltam vintage e disponibilidade verificável para essa evidência. O filtro por dia tampouco fornece o corte intradiário do Marko.

O [paper, v7 de 03/06/2025](https://arxiv.org/pdf/2412.20138), descreve backtest de janeiro a março de 2024. A tabela principal apresenta AAPL, GOOGL e AMZN, com Sharpe de até 8,21. Os autores reconhecem a janela curta e o custo de 11 chamadas LLM e mais de 20 chamadas de ferramentas por previsão. Minha avaliação: é evidência exploratória de um workflow, insuficiente para estabelecer retorno futuro, estabilidade entre regimes ou adequação ao caso brasileiro. O controle declarado de dados não demonstra ausência de conhecimento futuro nos pesos do LLM. O experimento de 2025 não pode ser equiparado ao HEAD de 2026 nem às correções posteriores. Não reproduzi os retornos publicados.

Proposta: TradingAgents como produtor externo de evidências/hipóteses para o Portfolio Lab, com fonte, disponibilidade, modelo/prompt, custo e incerteza registrados. Uma hipótese pode alimentar uma view Black–Litterman depois de calibração. Ratings não se convertem diretamente em ordens. O Marko aplica política, risco, restrições e aprovação; o debate não substitui esses gates.

A licença principal do TradingAgents é Apache-2.0, mas a instalação completa inclui Backtrader. A avaliação de licença deve incluir a árvore transitiva antes de embutir a distribuição. Não se presume que a licença do repositório cubra todas as dependências.

### Próximo incremento recomendado

1. Corrigir retorno/drift, orçamento com custos, status do solver, validação dos splits e ligação política–modelo–targets; acrescentar casos econômicos independentes às verificações.
2. Promover adapters skfolio para risk budgeting, HRP e CVaR; fixar nova versão e resolver lock em ambiente separado. Migrar APIs removidas somente onde usadas.
3. Usar QuantStats para relatório de retornos já validados e PyPortfolioOpt/Riskfolio como comparação numérica; nenhum deles corrige um backtest incorreto a montante.
4. Completar um ciclo shadow com dados versionados, benchmarks e custos. Dados públicos de pesquisa não exigem capital real nem credenciais privadas ANBIMA/B3; a política e a qualidade temporal precisam estar explícitas.
5. Só então medir o valor incremental das evidências do TradingAgents: baseline sem LLM, analista único, debate completo; mesmos dados/cortes/custos, várias execuções e holdout prospectivo.

Detalhamento por repositório e critérios de aceitação: [`REUSE_PLAN.md`](REUSE_PLAN.md).

## Classificação original — snapshot de 20/08/2026

Snapshot reproduzível: [`upstreams.lock.json`](../../upstreams.lock.json), em `historical_snapshots`. Os clones ficam em `/home/pedro/repo/marko-references`; nenhum deles é dependência implícita do produto.

| Projeto | Papel no Marko | Decisão |
|---|---|---|
| skfolio | construção e validação de portfólios | adapter quantitativo principal |
| Riskfolio-Lib | modelos e restrições avançados | laboratório e oráculo |
| PyPortfolioOpt | baselines legíveis e independentes | oráculo e adapter secundário |
| cvxportfolio | política multi-período, custos e execução | referência de arquitetura e oráculo |
| vectorbt | bancada de backtests em escala | pesquisa isolada |
| QuantStats | métricas e relatórios | oráculo; métricas essenciais próprias |
| OpenBB | contrato de provedores | referência; conectores brasileiros próprios |
| Qlib | registro experimental, rolling e ML | referência futura, não dependência do MVP |
| Ghostfolio | UX de patrimônio e importação | referência visual e de fluxos |
| Wealthfolio | ledger, drift, cenários e permissões de agente | principal referência de produto |
| Portfolio Performance | contabilidade, performance e explicabilidade | principal oráculo contábil |

## Conclusões vinculantes

1. O domínio financeiro do Marko não importa tipos de bibliotecas quantitativas.
2. Entradas e saídas externas atravessam adapters com esquemas versionados.
3. Valores monetários usam decimal exato; matrizes e retornos usam ponto flutuante somente no laboratório.
4. Toda decisão preserva dados, código, ambiente, solver, política, universo e diagnóstico.
5. Licenças copyleft ou restritivas não autorizam incorporação de código.
6. Modelos só avançam depois de contabilidade, dados temporais e validação.

As evidências específicas estão em [`upstreams/`](upstreams/).
