# Análise dos projetos de referência

Data da inspeção: 20/08/2026.

## Decisão

O Marko não deve ser um fork de nenhum dos projetos. A combinação mais sólida para o v0.1 é:

- `skfolio` como motor principal de construção e validação de portfólios;
- `PyPortfolioOpt` como benchmark independente e referência didática;
- `Riskfolio-Lib` como bancada de pesquisa avançada, fora do caminho crítico;
- um ledger e um planejador de aportes próprios, inspirados nos contratos do Wealthfolio e na contabilidade do Portfolio Performance;
- adaptadores próprios para dados, com OpenBB apenas como integração opcional;
- `vectorbt` apenas na bancada experimental e sob revisão de licença;
- métricas próprias pequenas, validadas contra QuantStats, em vez de torná-lo fonte de verdade;
- agente separado do otimizador: ele explica, compara cenários e prepara planos; não executa ordens.

## Estado dos clones

| Projeto | Commit inspecionado | Versão | Licença | Papel recomendado |
| --- | --- | --- | --- | --- |
| skfolio | `07dd64b3640fc4350d3d092837a978a87e9e4b34` | 0.20.2 | BSD-3-Clause | dependência principal |
| Riskfolio-Lib | `632a9e48fbaf2b9f8e83864a492332364b6ed32c` | 7.3.0 | BSD-3-Clause | adaptador de pesquisa |
| PyPortfolioOpt | `a6638d2e06dae6f444fd022cfd4b3c528902a85b` | 1.6.0 | MIT | benchmark/oráculo |
| vectorbt | `34b6d5935e3ea3eccd549e2592bc0f455b8045f5` | 1.1.0 | Apache-2.0 + Commons Clause | bancada opcional |
| QuantStats | `fbd10daed0227aa0d10da6513f1b15e7e98d7fae` | 0.0.78 | Apache-2.0 | validação e relatórios experimentais |
| OpenBB | `3e071fcc2cd9f891cac6040ae60296dba76dab46` | core 1.6.13 | AGPL-3.0 | integração isolada e opcional |
| Ghostfolio | `7a2ba0d8d665c2bd58a4ca04fb44a66e190bad0c` | 3.56.0 | AGPL-3.0 | referência de produto |
| Wealthfolio | `ac95f786f83c37009dc8d623bca7244bd76c4a24` | 3.7.0 | AGPL-3.0 | principal referência de produto e agente |
| Portfolio Performance | `90b27560fc0804878386911227cac6d01b7a28fa` | 0.87.1-SNAPSHOT | EPL-1.0 | referência contábil |

Os sete clones novos são rasos. Wealthfolio e Portfolio Performance já estavam presentes, completos e alinhados aos respectivos branches remotos no momento da inspeção.

As versões encontradas corrigem duas informações do levantamento inicial: Riskfolio-Lib já está em 7.3.0 e vectorbt em 1.1.0.

## O que aproveitar

### skfolio

É o melhor núcleo para o v0.1 porque modela otimização como estimadores compatíveis com scikit-learn. Isso permite tratar estimadores de momentos, priors, alocadores e validação temporal como componentes substituíveis, sem criar uma API paralela no Marko.

Aproveitar diretamente:

- `EqualWeighted`, `InverseVolatility`, `MeanRisk`, `RiskBudgeting` e `MaximumDiversification`;
- HRP, HERC e NCO;
- CVaR, CDaR, maximum drawdown e DRO-CVaR;
- Black–Litterman, Entropy Pooling e modelos fatoriais;
- Ledoit–Wolf, OAS, denoising, detoning, Gerber e covariância ajustada por regime;
- custos, peso anterior, regularização, turnover, cardinalidade e restrições por grupo;
- `WalkForward` com purge explícito e `CombinatorialPurgedCV`;
- `StackingOptimization`, que treina o combinador com previsões fora da amostra;
- cadeia de fallback e registro de falha do otimizador.

Não expor objetos do skfolio diretamente na API pública. O Marko precisa de um contrato próprio de `ModelSpec`, `ModelRun` e `TargetPortfolio`, para permitir troca de biblioteca e preservar resultados históricos.

### PyPortfolioOpt

É pequeno, legível e cobre as referências canônicas: fronteira eficiente, Black–Litterman, HRP, CVaR, CDaR, semivariância, regularização L2, custos de transação e alocação discreta.

Usar como:

- oráculo independente nos testes de minimum variance, BL, HRP e fronteira;
- baseline didático para conferir convenções de retornos, anualização e covariância;
- referência para transformar pesos contínuos em quantidades negociáveis.

Não há ganho em manter skfolio e PyPortfolioOpt como dois motores equivalentes em produção. Isso duplicaria semântica, configuração e tratamento de falhas.

### Riskfolio-Lib

Tem a maior superfície de otimização avançada: múltiplas medidas de risco, risk parity, fatores, uncertainty sets, OWA, higher moments, grafos, clusters e restrições combinatórias.

Usar para experimentos que ainda não estejam cobertos adequadamente pelo skfolio e para validação cruzada de soluções. Não usar como núcleo inicial porque:

- a classe central `Portfolio` concentra mais de 6.700 linhas e muitos modos de operação;
- o pacote compila uma extensão C++/pybind11;
- a instalação traz uma pilha científica larga e depende do próprio vectorbt;
- sua API dificulta transformar cada execução em um artefato pequeno e auditável.

### vectorbt

A versão 1.1.0 possui simulação vetorizada, callbacks event-driven, splitters rolling/expanding, logs de ordens, trades e posições, além de kernels Rust opcionais.

É adequado para varrer configurações e validar a mecânica de rebalances. Não deve ser dependência do serviço principal: a pilha é pesada, sua licença inclui Commons Clause e a abstração é orientada a backtests de sinais/ordens, não ao ledger de um gestor pessoal.

Antes de qualquer uso comercial ou serviço hospedado, revisar a Commons Clause. O repositório não deve ser tratado como open source permissivo.

### QuantStats

Oferece uma boa lista de métricas e tearsheets, mas mistura cálculo, pandas, gráficos, HTML e download via yfinance.

Usar para comparar resultados de Sharpe, Sortino, CVaR, drawdown, Calmar e rolling metrics durante o desenvolvimento. No domínio do Marko, implementar somente as métricas adotadas, com convenções explícitas para frequência, taxa livre de risco, NaNs e retornos aritméticos/logarítmicos.

### OpenBB

O desenho `modelo padronizado -> fetcher do provedor -> transformação -> resultado anotado` é excelente para a porta de dados do Marko. O registry por entry points e a separação `transform_query / extract_data / transform_data` também valem ser reproduzidos como conceito.

Não usar OpenBB como núcleo da ingestão:

- o repositório inteiro é AGPL-3.0;
- a plataforma é grande para o conjunto inicial de dados;
- não há provedor nativo de BCB, Selic, SIDRA, ANBIMA ou B3 no clone inspecionado;
- credenciais, limites e termos das fontes continuam sendo responsabilidade do Marko.

Para o Brasil, criar adaptadores próprios para as fontes oficiais e manter OpenBB atrás de uma porta opcional ou de um processo separado.

### Wealthfolio

É a referência de produto mais útil do conjunto atual. Já contém vários requisitos que o texto propunha como novos:

- targets por taxonomia e escopo;
- bandas absolutas e híbridas de desvio;
- modos `cash_flow_only`, `sell_to_rebalance` e `hybrid`;
- objetivo de chegar ao alvo exato ou apenas à banda mais próxima;
- lote inteiro, valor mínimo de operação, trava de categoria e teto de turnover;
- planejador que prioriza redução de drift por real investido;
- distinção rigorosa entre caixa rastreado e caixa disponível para aporte;
- ledger de atividades, holdings, snapshots, FX, classificação, health checks e reconciliação;
- núcleo de domínio separado de SQLite, Tauri, servidor e frontend;
- ferramentas de agente classificadas como leitura, sugestão, rascunho e escrita;
- scopes explícitos, commit separado, autenticação por token e auditoria com argumentos sanitizados;
- avaliações do agente por sequência de ferramentas, limites de saída e eventos de streaming.

O Marko deve adotar esses contratos conceituais, especialmente o fluxo `ler -> simular -> gerar rascunho -> aprovação humana -> registrar`, sem copiar código AGPL enquanto a licença do Marko não estiver decidida.

### Portfolio Performance

É a melhor fonte para os detalhes difíceis do ledger:

- dinheiro e quantidades sem `float` binário;
- valor bruto separado de taxas e impostos;
- moeda do ativo, moeda da transação e taxa de câmbio registrada;
- compras, vendas, transferências e entregas como eventos distintos;
- snapshots por data e por escopo;
- FIFO e custo médio;
- TWR, IRR, drawdown, volatilidade e atribuição;
- `Trail` para explicar de onde veio cada número;
- filtros do mesmo ledger por conta, carteira, ativo ou classificação.

Essas invariantes valem mais para o Marko que qualquer algoritmo sofisticado. Usar como especificação de comportamento e conjunto de casos-limite, não como dependência Java.

### Ghostfolio

É útil para estudar a experiência de contas, atividades, ativos, benchmarks, snapshots em fila, regras de concentração e painéis. O modelo Prisma mostra um ledger razoavelmente simples para uma aplicação web multiusuário.

Não usar como referência matemática principal. No commit inspecionado, as classes TWR e MWR existem na factory, mas seus métodos centrais ainda lançam `Method not implemented`. A implementação mais madura está no cálculo próprio de ROAI/ROI e em muitos testes de casos de transação.

Como o código é AGPL, limitar o uso a decisões de produto e testes comportamentais até existir uma decisão explícita sobre a licença do Marko.

## Arquitetura derivada

```text
fontes oficiais / provedores
          |
          v
    dados normalizados  ---->  ledger imutável
          |                       |
          v                       v
 estimadores point-in-time   snapshots contábeis
          |                       |
          +----------+------------+
                     v
              comitê de modelos
                     |
                     v
          carteira-alvo versionada
                     |
                     v
       planejador de aporte/rebalance
                     |
                     v
          rascunho para aprovação
```

Contratos mínimos:

- `MarketDataProvider`: busca dados e devolve modelos normalizados com fonte, instante observado, instante disponível e qualidade;
- `Allocator`: recebe um snapshot imutável e devolve pesos, diagnósticos e status;
- `ValidationProtocol`: define janelas, purge, latência, custos e calendário antes de executar modelos;
- `ModelRun`: guarda versão do código, parâmetros, universo, fingerprint dos dados, pesos e métricas;
- `CommitteeDecision`: guarda consenso, dispersão, ranking de estabilidade e discordâncias, sem esconder os modelos individuais;
- `ExecutionPlanner`: converte alvo, carteira atual, caixa, lote, imposto e custo em um plano, priorizando aporte sem venda;
- `Thesis`: registra papel, hipótese, sinais favoráveis/contrários, sensibilidades, limites e data de revisão;
- `DecisionRecord`: liga tese, execução proposta, aprovação humana e eventos posteriores.

## Corte do v0.1

### Entram

- ledger de contas, instrumentos, atividades, caixa, taxas, impostos e FX;
- snapshots determinísticos e reconciliação;
- ingestão inicial por CSV e adaptadores mínimos de preços/índices;
- 1/N, inverse volatility, minimum variance, risk budgeting, HRP, CVaR e Black–Litterman;
- walk-forward com purge e custos;
- CDI e 1/N como benchmarks obrigatórios;
- comparação lado a lado dos modelos e dispersão dos pesos;
- aporte mensal com modo padrão sem vendas;
- plano em rascunho, nunca execução automática;
- tese por posição e trilha de explicação por número;
- shadow portfolio separado da carteira real.

### Não entram

- notícias ou LLM gerando ordens;
- Qlib, reinforcement learning ou previsão de alpha;
- DRO, HERC, NCO e stacking na primeira entrega operacional;
- integração com corretora;
- OpenBB como dependência obrigatória;
- vectorbt no serviço online;
- dezenas de métricas sem uso decisório;
- escolha automática do “modelo vencedor” pelo maior retorno histórico.

## Regras de validação

- toda série precisa registrar `observed_at` e `available_at`; backtest usa apenas o que estava disponível na decisão;
- splits, dividendos, câmbio, calendário, taxas e impostos precisam de casos de teste próprios;
- cada modelo deve aceitar o mesmo universo, restrições e custos ou declarar a incompatibilidade;
- comparar resultados contra PyPortfolioOpt/Riskfolio-Lib onde houver formulação equivalente;
- falha numérica gera resultado explícito e fallback registrado, nunca pesos silenciosamente reaproveitados;
- métricas devem declarar periodicidade, benchmark, taxa livre de risco e tratamento de dados faltantes;
- um aporte não pode produzir venda no modo `cash_flow_only`;
- todo plano deve reconciliar caixa, quantidades, custos e valor final;
- o agente não recebe uma ferramenta de execução: somente leitura, cenário, explicação e criação de rascunho;
- a aprovação humana deve ser um evento persistido e auditável.

## Principal implicação

O diferencial do Marko não será possuir mais um otimizador. Será preservar a cadeia inteira entre dado observado, hipótese, modelo, discordância, alvo, aporte, aprovação e resultado realizado. Os projetos quantitativos resolvem bem a matemática; Wealthfolio e Portfolio Performance mostram que o trabalho mais difícil está na contabilidade, nos limites operacionais e na explicabilidade.
