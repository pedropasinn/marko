
Sim. Eu mudaria a definição do projeto para algo mais ambicioso:

> **Marko não será um programa que “escolhe investimentos”. Será um sistema quantitativo de gestão patrimonial, pesquisa, decisão, risco, execução assistida, contabilidade e auditoria.**

E, como o capital inicial veio de um empréstimo da sua mãe, há uma ideia de finanças que eu colocaria no centro desde o primeiro dia: **Asset-Liability Management**. O Marko não deve enxergar apenas “tenho R$ 50 mil”; ele deve enxergar “tenho R$ 50 mil em ativos e uma obrigação futura de R$ 50 mil — ou o valor contratualmente devido — com determinada data e condições”. Isso muda a maneira correta de medir risco.

Eu também acrescentaria imediatamente `cvxportfolio` aos repositórios que você pediu para o Codex clonar. Ele cobre uma lacuna importante: custos de transação, restrições e otimização multi-período, e seu simulador foi desenhado para que as decisões do backtest usem apenas informação disponível até cada instante. ([GitHub][1])

Vou descrever abaixo como eu faria o projeto do zero até o estágio em que eu consideraria o sistema tecnicamente apto a acompanhar capital real.

---

# 1. A filosofia do Marko

Eu escreveria cinco regras praticamente constitucionais.

**Regra 1 — Marko não tenta adivinhar o futuro; ele administra incerteza.**

Uma previsão de retorno não é verdade. É uma distribuição com enorme erro.

Por isso:

[
\hat{\mu}
\neq
\mu
]

e

[
\hat{\Sigma}
\neq
\Sigma
]

Todo modelo do Marko precisa assumir explicitamente que suas estimativas podem estar erradas.

**Regra 2 — nenhum modelo é o Marko.**

Markowitz não é o Marko.

Black-Litterman não é o Marko.

HRP não é o Marko.

Um modelo de IA não é o Marko.

O Marko é o sistema que compara, combina, valida e eventualmente rejeita esses modelos.

**Regra 3 — modelos simples são benchmarks permanentes.**

Nunca exclua:

* 1/N;
* buy-and-hold;
* mínimo de variância;
* benchmark de caixa/renda fixa apropriado;
* benchmark de mercado;
* uma alocação estratégica simples.

Se uma arquitetura com transformers, HMMs e otimização robusta não consegue mostrar valor comparada a um benchmark trivial, ela não merece controlar dinheiro.

**Regra 4 — previsão e decisão são coisas diferentes.**

O módulo macro pode concluir:

> probabilidade maior de queda de juros.

O módulo de equity pode concluir:

> determinada empresa parece barata.

O módulo de notícias pode concluir:

> risco regulatório aumentou.

Mas nenhum deles diz:

> compre R$ 4.312,42.

Eles produzem evidências, sinais, distribuições e graus de confiança.

Quem transforma isso em carteira é outra camada.

**Regra 5 — LLM nunca é autoridade de execução.**

Claude, Codex, ChatGPT etc. podem pesquisar, questionar, explicar, testar e gerar hipóteses.

Não devem conseguir inventar uma ordem e transmiti-la diretamente.

---

# 2. Antes da carteira: representar corretamente o empréstimo

Esse é um elemento que eu não ignoraria.

Teríamos:

```text
ASSETS
R$ 50.000

LIABILITY
Empréstimo da mãe
Principal: R$ 50.000
Vencimento: ?
Juros: ?
Indexação: ?
Possibilidade de cobrança antecipada: ?
```

Isso vira uma entidade real dentro do Marko:

```text
Liability
├── creditor
├── initial_principal
├── current_balance
├── start_date
├── maturity_date
├── interest_rule
├── inflation_rule
├── scheduled_cashflows
└── early_call_conditions
```

Então, além de:

[
E[R]
]

e volatilidade, começamos a medir:

[
P(W_T < L_T)
]

onde:

* (W_T) = patrimônio futuro;
* (L_T) = obrigação futura.

Essa é a **probabilidade de shortfall**.

Podemos também otimizar:

[
ES_\alpha(L_T-W_T)
]

nos cenários ruins.

Isso é muito mais apropriado para dinheiro emprestado do que simplesmente:

> maximizar Sharpe.

O Marko pode inclusive separar economicamente:

```text
Patrimônio total
│
├── Liability-matching capital
│
│   └── capital destinado a preservar
│       capacidade de pagamento
│
└── Risk capital
    │
    └── capital com maior capacidade
        de assumir risco
```

A proporção entre eles não precisa ser decidida agora. Ela deve surgir posteriormente da obrigação, horizonte e tolerância ao risco.

---

# 3. O Investment Policy Statement

Antes de escolher qualquer ativo, eu faria o Marko exigir um documento estruturado chamado `InvestmentPolicy`.

Seria provavelmente a coisa mais importante do sistema.

Algo como:

```yaml
portfolio:
  name: personal-main

objective:
  horizon: 4_years
  primary: terminal_real_wealth
  secondary: beat_benchmark

liability:
  enabled: true

liquidity:
  emergency_withdrawal: ...
  planned_withdrawals: ...

risk:
  maximum_acceptable_drawdown: ...
  shortfall_probability_limit: ...
  cvar_limit: ...

constraints:
  leverage: false
  short_selling: false
  illiquid_assets: false

concentration:
  max_single_asset: ...
  max_single_sector: ...
  max_single_country: ...
  max_single_currency: ...

implementation:
  monthly_contribution: 2000
  cashflow_rebalancing_first: true

governance:
  automatic_execution: false
```

Isso deve ser versionado.

Se daqui a um ano sua condição mudar:

```text
IPS v1
↓
IPS v2
```

O histórico permanece.

Nunca devemos alterar retroativamente o passado.

---

# 4. O que aproveitar dos repositórios que você está clonando

Aqui eu já tenho uma visão bastante clara.

| Repositório              | Papel no Marko                                                        | Minha recomendação                                             |
| ------------------------- | --------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `skfolio`               | Portfolio research, estimadores, otimização, validação, ensembles | **Motor quantitativo principal**                           |
| `Riskfolio-Lib`         | Medidas avançadas de risco, risk budgeting, fatores, hierárquicos   | **Segundo motor / laboratório avançado**                 |
| `PyPortfolioOpt`        | Markowitz, shrinkage, BL, HRP                                         | **Benchmark independente e implementação simples**       |
| `cvxportfolio`          | custos, restrições, execução e otimização multi-período        | **Laboratório de implementação/execution optimization** |
| `vectorbt`              | backtests em massa e parameter sweeps                                 | **Research harness**                                       |
| `QuantStats`            | métricas e relatórios                                               | **Analytics**                                              |
| `OpenBB`                | abstração de provedores financeiros                                 | **Referência para Data Gateway**                          |
| `Qlib`                  | ML, experimentos, concept drift, alpha research                       | **Marko ML futuro**                                        |
| `Ghostfolio`            | portfolio tracking e UX                                               | **Referência de produto; não base arquitetural**         |
| `Wealthfolio`           | local-first, tracking, agent tools/MCP                                | **Referência muito interessante de UX/agentes**           |
| `Portfolio Performance` | ledger, performance accounting e importação                         | **Referência contábil**                                  |

O `skfolio` é hoje a biblioteca que eu colocaria mais próxima do núcleo de pesquisa. Ela é BSD-3-Clause, usa uma interface inspirada em scikit-learn e foi projetada justamente para combinar otimização, model selection, cross-validation e stress testing. ([GitHub][2])

`Riskfolio-Lib` é excelente para servir como laboratório de risco e implementação matemática. Atualmente documenta 24 medidas convexas de risco e vários problemas diferentes de otimização, além de modelos hierárquicos e de fatores. Também é BSD-3-Clause. ([GitHub][3])

`PyPortfolioOpt` eu manteria mesmo existindo sobreposição. É relativamente simples e implementa Markowitz, shrinkage, Black-Litterman e HRP. Isso o torna muito bom como **oracle independente**: se duas implementações diferentes de mínimo de variância estiverem produzindo resultados completamente diferentes com os mesmos dados e restrições, precisamos descobrir por quê. Ele usa licença MIT. ([GitHub][4])

`cvxportfolio` entra em outra camada. Ele nos ajuda a sair de:

[
\text{target weights}
]

para:

[
\text{decisões ao longo do tempo}
]

incluindo custos, turnover e planejamento em vários períodos. ([GitHub][1])

`vectorbt` é extremamente interessante para experimentação em escala e walk-forward. Mas atenção: a edição open source atual está sob Apache 2.0 + Commons Clause e expressamente limita vender produtos ou serviços cujo objeto principal seja o próprio software. Eu o manteria no **research environment**, isolado da arquitetura comercial do Marko. ([GitHub][5])

`QuantStats` é Apache-2.0 e encaixa perfeitamente na camada de performance analytics: Sharpe, volatilidade, drawdowns, rolling statistics e relatórios. ([GitHub][6])

`Qlib` é MIT e eu deixaria para uma fase posterior. A arquitetura dele cobre processamento de dados → ML → backtest → portfolio → execução, e inclui supervised learning, adaptação a market dynamics e reinforcement learning. É uma excelente referência para o futuro `Marko Research`. ([GitHub][7])

Agora um alerta arquitetural: `OpenBB`, `Ghostfolio` e `Wealthfolio` são AGPL-3.0 atualmente. `Portfolio Performance` é EPL-1.0 e `cvxportfolio` atual é GPLv3. ([GitHub][8])

Para projeto pessoal isso é bem mais simples, mas se um dia Marko virar produto, isso importa muito. Não é aconselhamento jurídico, mas eu faria desde já:

```text
BSD / MIT / Apache
        ↓
podem ser dependências naturais do Marko

GPL / AGPL / EPL / Commons Clause
        ↓
adapters isolados / ferramentas de research /
referência arquitetural
        ↓
revisão de licença antes de distribuição comercial
```

Principalmente: **não peça para o Codex começar a copiar arquivos desses projetos para dentro do Marko.**

---

# 5. Onde eu mandaria o Codex colocar esses clones

Nem dentro de `marko/src`.

Nem como uma enorme pasta `vendor/`.

Eu faria:

```text
~/repo/
├── marko/
│
└── marko-references/
    ├── skfolio/
    ├── Riskfolio-Lib/
    ├── PyPortfolioOpt/
    ├── cvxportfolio/
    ├── vectorbt/
    ├── quantstats/
    ├── OpenBB/
    ├── qlib/
    ├── ghostfolio/
    ├── wealthfolio/
    └── portfolio-performance/
```

Dentro de Marko, teríamos apenas:

```text
docs/research/upstreams/
├── skfolio.md
├── riskfolio.md
├── pyportfolioopt.md
├── cvxportfolio.md
├── vectorbt.md
├── quantstats.md
├── openbb.md
├── qlib.md
├── ghostfolio.md
├── wealthfolio.md
└── portfolio-performance.md
```

E um:

```text
upstreams.lock.json
```

com:

```json
{
  "skfolio": {
    "commit": "...",
    "version": "...",
    "license": "BSD-3-Clause"
  }
}
```

Assim sabemos exatamente qual código o Codex estudou.

---

# 6. Arquitetura do Marko

Eu faria Ports & Adapters.

O principal motivo é muito claro aqui: queremos poder trocar absolutamente tudo.

Hoje:

```text
skfolio
```

amanhã:

```text
nosso próprio optimizer
```

Hoje:

```text
Data Provider A
```

amanhã:

```text
Data Provider B
```

O core não deve perceber.

Algo assim:

```text
marko/
│
├── apps/
│   ├── api/
│   ├── web/
│   └── worker/
│
├── marko/
│   │
│   ├── domain/
│   │   ├── instruments/
│   │   ├── portfolio/
│   │   ├── accounting/
│   │   ├── liabilities/
│   │   ├── allocation/
│   │   ├── risk/
│   │   ├── research/
│   │   ├── execution/
│   │   └── governance/
│   │
│   ├── application/
│   │   ├── commands/
│   │   ├── queries/
│   │   └── services/
│   │
│   ├── ports/
│   │   ├── market_data.py
│   │   ├── fundamentals.py
│   │   ├── macro.py
│   │   ├── news.py
│   │   ├── optimizer.py
│   │   ├── risk_model.py
│   │   ├── broker.py
│   │   ├── ledger.py
│   │   └── clock.py
│   │
│   └── adapters/
│       ├── skfolio/
│       ├── riskfolio/
│       ├── pyportfolioopt/
│       ├── market_data/
│       ├── database/
│       └── broker/
│
├── research/
│   ├── experiments/
│   ├── notebooks/
│   ├── datasets/
│   └── model_cards/
│
├── configs/
├── migrations/
├── tests/
├── docs/
└── infra/
```

Um princípio arquitetural importante:

> `Portfolio` nunca deve ser um objeto `skfolio.Portfolio`.

Teremos:

```python
MarkoPortfolio
```

e um adapter transforma isso no formato esperado pelo `skfolio`.

Isso evita dependência estrutural da biblioteca.

---

# 7. A camada de dados talvez seja mais importante que os modelos

Se os dados estiverem errados, o Marko estará errado de maneira sofisticada.

Eu separaria:

```text
RAW
↓
NORMALIZED
↓
POINT-IN-TIME
↓
FEATURES
↓
MODELS
```

E todo dado precisa carregar pelo menos quatro timestamps:

```text
effective_at
observed_at
available_at
ingested_at
```

Isso parece detalhe, mas é crucial.

Imagine:

```text
Balanço referente a:
31/12/2025

Publicado:
15/03/2026
```

O backtest de janeiro de 2026 **não pode conhecer esse balanço**.

O mesmo vale para dados macro revisados.

O PIB publicado originalmente como:

```text
+1,7%
```

pode depois ser revisado para:

```text
+1,4%
```

O Marko precisa saber:

> Qual número um investidor realmente conhecia naquele dia?

Essa é uma das diferenças entre um backtest bonito e pesquisa quantitativa séria.

---

# 8. Armazenamento

Eu faria um híbrido.

### PostgreSQL

Para estado operacional:

```text
accounts
portfolios
transactions
orders
holdings
cashflows
liabilities
model_runs
decisions
targets
risk_snapshots
users
audit_log
```

### Parquet

Para datasets grandes:

```text
prices/
fundamentals/
macro/
features/
alternative_data/
```

### DuckDB

Para pesquisar rapidamente os Parquets.

Teríamos, por exemplo:

```text
Postgres
= verdade operacional

Parquet
= verdade histórica analítica

DuckDB
= engine de pesquisa
```

Isso evita colocar bilhões de observações desnecessariamente no banco operacional.

---

# 9. Ledger — uma das partes mais importantes

Nunca calcule patrimônio simplesmente como:

> posição atual × preço.

Precisamos de um ledger.

Um evento pode ser:

```text
DEPOSIT
WITHDRAWAL
BUY
SELL
DIVIDEND
INTEREST
FEE
TAX
SPLIT
BONUS
TRANSFER
FX_CONVERSION
```

E esses eventos são imutáveis.

O estado da carteira é derivado deles.

```text
Ledger
↓
Positions
↓
Valuation
↓
Performance
```

Se o sistema disser:

```text
Patrimônio = R$ 58.214,37
```

precisamos conseguir reconstruir exatamente por quê.

É nessa parte que eu estudaria muito `Portfolio Performance`, `Ghostfolio` e `Wealthfolio`, não necessariamente para copiar código, mas para entender problemas que projetos maduros já precisaram resolver.

`Portfolio Performance`, por exemplo, tem mais de oito mil commits e muito trabalho justamente em operações, importações, corporate actions e performance accounting. ([GitHub][9])

---

# 10. Performance corretamente calculada

O Marko precisa distinguir:

### Money-weighted return

XIRR.

Responde:

> Qual foi o retorno efetivamente experimentado pelo investidor considerando quando ele colocou dinheiro?

### Time-weighted return

TWR.

Responde:

> Como a estratégia performou independentemente dos aportes?

Com seus R$ 2 mil entrando mensalmente, essa distinção é essencial.

Teremos:

```text
Portfolio Value
Net Contributions
TWR
XIRR
CAGR
Real Return
Excess Return
```

e benchmarks.

---

# 11. O Model Zoo

Agora chegamos ao coração matemático.

Eu dividiria os modelos em famílias.

## Família A — Baselines

Obrigatórios:

```text
1/N
Buy & Hold
Minimum Variance
Market-cap
Simple Strategic Allocation
```

## Família B — Markowitz

```text
Mean Variance
Maximum Sharpe
Minimum Variance
Efficient Return
Efficient Risk
```

Mas nunca com covariance matrix crua como única opção.

---

# 12. Covariance Lab

Teríamos estimadores diferentes:

```text
Sample Covariance
EWMA
Ledoit-Wolf
OAS
Constant Correlation Shrinkage
Single Factor Shrinkage
Factor Covariance
Denoised Covariance
Regime-aware Covariance
```

O PyPortfolioOpt atualmente implementa inclusive diferentes shrinkage targets de Ledoit-Wolf, como constant variance, single factor e constant correlation. ([GitHub][10])

Essa será uma dimensão inteira do experimento.

Não:

```text
Markowitz
```

mas:

```text
Markowitz
× expected-return estimator
× covariance estimator
× regularization
× constraints
```

---

# 13. Black-Litterman

Esse será um dos componentes fundamentais.

Temos:

```text
Market Prior
+
Investor Views
+
Confidence
↓
Posterior Returns
```

As views podem vir de:

```text
fundamental
macro
factor
valuation
quantitative
```

Por exemplo, conceitualmente:

```text
View:
Asset group A expected to outperform B.

Confidence:
0.62

Evidence:
Macro model
Factor model
Valuation
```

Muito importante:

**LLM não define a confiança.**

Podemos usar LLM para extrair informação.

A confiança precisa ter fundamento quantitativo ou uma regra explícita.

---

# 14. Entropy Pooling

Também colocaria no laboratório.

Ele permite partir de uma distribuição anterior e adicionar views sobre:

```text
média
volatilidade
quantis
correlação
probabilidades condicionais
```

Isso é extraordinariamente flexível para incorporar cenários macro.

---

# 15. Risk Parity / Risk Budgeting

Queremos permanentemente calcular:

[
RC_i =
w_i
\frac{\partial \sigma_p}{\partial w_i}
]

Ou seja:

> quanto cada posição contribui para o risco total?

Tela:

```text
CAPITAL
PETR4       7%
ETF US     15%
Bonds      30%
...

RISK
PETR4      16%
ETF US     28%
Bonds       8%
...
```

Isso geralmente revela coisas que pesos nominais escondem.

---

# 16. Maximum Diversification

Outro challenger:

[
DR =
\frac{w^\top \sigma}
{\sqrt{w^\top\Sigma w}}
]

Maximizamos o diversification ratio.

Não precisa ganhar, mas deve estar no laboratório.

---

# 17. HRP / HERC / NCO

Teríamos:

```text
Hierarchical Risk Parity
Hierarchical Equal Risk Contribution
Nested Clustered Optimization
```

O interessante aqui é que conseguimos visualizar a estrutura:

```text
Equities
├── Brazil
│   ├── Banks
│   ├── Commodities
│   └── Consumer
│
└── International
    ├── US
    ├── Developed ex-US
    └── Emerging
```

Mas novamente:

> HRP não ganha automaticamente porque parece matematicamente moderno.

Ele precisa enfrentar 1/N no mesmo dataset.

---

# 18. Tail-risk models

Muito importantes para o Marko:

```text
CVaR / Expected Shortfall
CDaR
Maximum Drawdown
Semi-deviation
Lower Partial Moments
```

Eu quero conseguir perguntar:

> Nos piores 5% dos cenários simulados, qual é a perda média?

Isso é:

[
CVaR_{95%}
]

Muito mais intuitivo para capital real.

---

# 19. Distributionally Robust Optimization

Essa é uma das áreas que eu estudaria seriamente.

O modelo admite:

> não sabemos qual é a distribuição verdadeira.

Em vez de:

[
P=P_0
]

temos:

[
P\in\mathcal P
]

e buscamos algo que funcione razoavelmente em uma vizinhança de distribuições.

O `skfolio` já possui otimização Distributionally Robust CVaR, então vale estudar a implementação e exemplos com atenção. ([GitHub][2])

---

# 20. Factor models

Eu criaria um `Factor Engine`.

Categorias:

```text
Market
Size
Value
Quality
Profitability
Investment
Momentum
Low Vol
Term
Credit
Inflation
FX
Commodity
Liquidity
```

Então conseguimos decompor a carteira em:

[
R_p =
\alpha +
\beta_1F_1+
\beta_2F_2+\cdots+
\epsilon
]

Isso é muito melhor que pensar:

> tenho PETR4 + VALE3 + banco X.

Talvez economicamente tenhamos:

```text
commodity exposure
value exposure
Brazil exposure
FX exposure
cyclical exposure
```

E várias ações estejam apenas duplicando a mesma aposta.

---

# 21. Macro Engine

Aqui podemos fazer algo realmente interessante.

```text
MARKO MACRO

Inflation
Interest rates
Yield curve
Credit
Activity
Employment
FX
Commodities
Liquidity
Fiscal
Global conditions
```

Features:

```text
level
change
acceleration
surprise
relative position
z-score
trend
regime
```

E manter:

```text
Nowcast
Forecast
Consensus
Actual
Surprise
```

O importante é não converter:

```text
IPCA caiu
```

diretamente em:

```text
BUY
```

O macro engine alimenta probabilidades e cenários.

---

# 22. Regime Engine

Teremos diferentes métodos concorrentes:

```text
rule-based regimes
Markov Switching
Hidden Markov Models
clustering
change-point detection
```

Possíveis regimes conceituais:

```text
Growth ↑ / Inflation ↓
Growth ↑ / Inflation ↑
Growth ↓ / Inflation ↑
Growth ↓ / Inflation ↓
```

Mas não quero codificar os quatro quadrantes como verdade metafísica.

Eles são um modelo entre vários.

O regime pode influenciar:

```text
expected returns
covariance
risk budgets
stress scenarios
confidence
```

---

# 23. Fundamental Engine

Para ações individuais:

```text
Income Statement
Balance Sheet
Cash Flow
Margins
ROIC
ROE
Debt
Interest coverage
Working capital
Capex
FCF
Dividends
Share dilution
```

Depois:

```text
valuation
quality
growth
financial strength
earnings revisions
capital allocation
```

Teríamos históricos.

Não:

```text
P/L atual = 8
```

mas:

```text
P/L atual
vs
histórico da empresa
vs
setor
vs
mercado
vs
taxas
vs
crescimento
```

---

# 24. Valuation Engine

Diversos modelos:

```text
DCF
Dividend Discount
Residual Income
Multiples
Reverse DCF
Scenario valuation
```

Mas os resultados entram como distribuições.

Não:

```text
Fair value = R$ 31,74
```

e sim:

```text
P10: R$ ...
P50: R$ ...
P90: R$ ...
```

Sob premissas explícitas.

---

# 25. News Engine

Aqui entra bastante IA.

Pipeline:

```text
Source
↓
Document ingestion
↓
Deduplication
↓
Entity extraction
↓
Event extraction
↓
Classification
↓
Impact candidates
↓
Evidence store
```

LLM poderia identificar:

```text
Company
Country
Sector
Event
Novelty
Direction
Time horizon
Confidence
```

Mas o Marko registra também:

```text
source
published_at
retrieved_at
exact evidence
model
prompt version
```

Nada de:

> “A IA acha que a Petrobras vai subir.”

---

# 26. Research Evidence Store

Cada hipótese deveria ser rastreável.

```text
Hypothesis H-00421

Claim:
Factor X should improve risk-adjusted return.

Evidence:
Paper A
Paper B
Experiment 82
Experiment 97

Contradictory evidence:
Experiment 91

Status:
CHALLENGER
```

Esse sistema evita que a pesquisa vire uma coleção de ideias esquecidas.

---

# 27. Model Cards

Cada modelo ganha uma ficha.

```text
MODEL CARD

Name:
Black-Litterman v2

Theory:
...

Inputs:
...

Outputs:
...

Assumptions:
...

Failure modes:
...

Hyperparameters:
...

Data requirements:
...

Benchmarks:
...

Backtests:
...

Stress tests:
...

Known weaknesses:
...

Approved usage:
...

Version:
...
```

Isso será extremamente valioso com agentes trabalhando no projeto.

---

# 28. Experiment Registry

Cada experimento:

```text
experiment_id
git_commit
dataset_hash
universe_version
start_date
end_date
training_window
validation_method
parameters
cost_model
result
artifacts
created_at
```

Assim:

> reproduza o experimento 341

realmente significa alguma coisa.

---

# 29. Backtest Engine

Essa parte tem que ser quase paranoica.

O backtester precisa impedir:

### Look-ahead bias

Nenhuma informação futura.

### Survivorship bias

Não podemos testar usando apenas empresas que sobreviveram até hoje.

### Restatement bias

Fundamentals revisados não podem aparecer no passado.

### Universe leakage

Uma empresa que só entrou no índice posteriormente não pode aparecer antes.

### Corporate actions

Splits, dividendos etc.

### Currency

Retorno em BRL ≠ retorno em USD.

### Costs

Spread, corretagem quando aplicável, impostos, FX etc.

### Cash return

Dinheiro parado também rende ou custa.

### Slippage

Preço teórico ≠ execução.

---

# 30. Walk-forward

Em vez de:

```text
2010 ────────────────── 2025
         backtest
```

teríamos:

```text
TRAIN ── TEST
      TRAIN ── TEST
            TRAIN ── TEST
                  TRAIN ── TEST
```

Ou expanding window.

Isso deve ser padrão.

---

# 31. Purged Cross Validation

Para ML e sinais com horizontes sobrepostos:

```text
train
gap
test
embargo
```

Reduz leakage temporal.

O `skfolio` já enfatiza integração com ferramentas de cross-validation/model selection, uma das razões de eu colocá-lo no centro do laboratório. ([GitHub][2])

---

# 32. Não cair no problema de testar 10.000 estratégias

Esse é outro perigo.

Se testarmos:

```text
10.000 estratégias
```

e pegarmos a melhor, é praticamente garantido que encontraremos alguma coisa maravilhosa por sorte.

Precisamos de ferramentas como:

```text
Deflated Sharpe Ratio
Probability of Backtest Overfitting
multiple-testing corrections
bootstrap confidence intervals
parameter stability
```

E, principalmente:

> registrar todos os experimentos, inclusive os ruins.

Nada de survivorship bias de pesquisa.

---

# 33. Stress testing

Além de backtest histórico:

```text
Historical stress
Synthetic stress
Factor shocks
Correlation shocks
Liquidity shocks
```

Exemplos conceituais:

```text
Equities -30%
BRL -20%
Interest rates +300 bps
Credit spreads +400 bps
Commodity -35%
```

E combinações.

Outra extremamente importante:

```text
correlations → 1
```

porque é justamente quando diversificação frequentemente falha.

---

# 34. Monte Carlo

Não apenas GBM ingênuo.

Teríamos diferentes geradores:

```text
Gaussian
Student-t
Historical bootstrap
Block bootstrap
Regime bootstrap
Factor simulation
Posterior predictive
```

O resultado que quero mostrar é:

```text
Terminal Wealth Distribution

P05
P25
P50
P75
P95

Probability of loss
Probability of real loss
Probability of liability shortfall
Expected shortfall
```

---

# 35. Model Committee

Essa é talvez minha parte favorita.

Suponha:

```text
Minimum Variance        → 12% equity
Risk Parity             → 25%
Black-Litterman         → 37%
HRP                     → 22%
DRO-CVaR                → 18%
Maximum Diversification → 31%
```

O Marko mostra:

```text
MODEL DISAGREEMENT
```

e não apenas média.

Alta discordância é informação.

Poderíamos ter:

[
D_t =
Dispersion(w_{1,t},...,w_{n,t})
]

e usar isso como medida de **model uncertainty**.

---

# 36. Champion / Challenger

Nunca substituiríamos um modelo diretamente.

Teríamos:

```text
PRODUCTION
Champion

SHADOW
Challenger A
Challenger B
Challenger C
```

Um challenger pode superar o champion durante muito tempo e mesmo assim não entrar em produção até passar pelo processo de aprovação.

Isso é prática muito melhor de model risk.

---

# 37. Ensemble

Posteriormente:

[
w =
\sum_m \alpha_m w_m
]

Mas os (\alpha_m) não seriam escolhidos simplesmente pelo maior Sharpe histórico.

Podemos avaliar:

```text
out-of-sample performance
stability
drawdown
tail risk
turnover
parameter sensitivity
regime robustness
model complexity
```

Eu inclusive criaria um:

```text
Complexity Penalty
```

Modelos extraordinariamente complexos precisam entregar evidência extraordinariamente melhor.

---

# 38. Portfolio Decision Engine

Pipeline final:

```text
CURRENT PORTFOLIO
+
NEW CASH
+
LIABILITY
+
IPS
+
MARKET STATE
+
MODEL VIEWS
+
RISK ESTIMATES
+
MODEL COMMITTEE
           ↓
      TARGET PORTFOLIO
           ↓
      IMPLEMENTATION
           ↓
      TRADE PROPOSAL
```

Mas entre target e trade haverá outra otimização.

---

# 39. Rebalancing não é simplesmente “voltar para os pesos”

Suponha:

```text
Target     Actual

A  20%      18%
B  20%      21%
C  20%      21%
D  20%      19%
E  20%      21%
```

E entram R$ 2.000.

O Marko primeiro tenta corrigir com o aporte.

Isso é `cash-flow rebalancing`.

Só depois considera vendas.

---

# 40. Execution Optimizer

Formalmente podemos ter algo como:

[
\min_x
\underbrace{
(w(x)-w^*)'\Sigma(w(x)-w^*)
}*{desvio\ do\ target}
+
\lambda_C C(x)
+
\lambda_T T(x)
+
\lambda*{TO}Turnover(x)
]

onde:

* (x) = trades;
* (C(x)) = custos;
* (T(x)) = impacto tributário parametrizado segundo as regras vigentes;
* turnover = movimentação;
* (w^*) = carteira alvo.

É aqui que estudar `cvxportfolio` será extremamente útil. Ele já trabalha explicitamente com custos, constraints e decisões multi-período. ([GitHub][1])

---

# 41. O Marko não deveria dizer BUY/SELL o tempo todo

Eu usaria estados como:

```text
HOLD
CONTRIBUTE
REBALANCE
REDUCE
REVIEW
EXIT
```

E toda recomendação deveria explicar:

```text
Current
Target
Deviation
Reason
Risk impact
Expected implementation cost
Model agreement
Confidence
Trigger
```

---

# 42. Thesis Ledger

Cada investimento mantém uma tese.

```text
ASSET THESIS

Asset:
...

Portfolio role:
...

Why owned:
...

Expected drivers:
...

Risks:
...

Valuation:
...

Factor exposures:
...

Macro sensitivities:
...

Models supporting:
...

Models opposing:
...

Entry thesis:
...

Invalidation conditions:
...

Maximum exposure:
...

Last review:
...
```

A venda pode ocorrer porque:

```text
tese quebrou
valuation mudou
risk budget mudou
correlation mudou
better alternative
portfolio constraint
liability requirement
```

Não simplesmente:

> caiu 15%.

---

# 43. Agentic Marko

Eu teria vários agentes especializados.

```text
MARKO ORCHESTRATOR
│
├── Data Steward
├── Fundamental Analyst
├── Macro Analyst
├── News Analyst
├── Quant Researcher
├── Portfolio Committee
├── Risk Officer
├── Model Auditor
├── Accountant
└── Explainer
```

### Data Steward

Pergunta:

> Os dados estão completos e atualizados?

### Fundamental Analyst

> O que mudou na empresa?

### Macro Analyst

> O que mudou nas distribuições macro?

### Quant Researcher

> Há evidência estatística?

### Portfolio Committee

> O que os modelos recomendam?

### Risk Officer

> Estamos violando alguma restrição?

### Model Auditor

> Existe leakage, overfitting ou mudança metodológica?

### Accountant

> O ledger bate com o patrimônio real?

### Explainer

> Traduza tudo isso para uma decisão compreensível.

---

# 44. Permissões dos agentes

Muito importante:

```text
Research Agent
READ   ✓
WRITE research ✓
TRADE  ✗

Portfolio Agent
READ   ✓
WRITE proposals ✓
TRADE  ✗

Risk Agent
READ   ✓
VETO proposal ✓
TRADE  ✗

Execution Service
READ proposal ✓
CREATE order draft ✓
SEND automatically ✗
```

Na primeira versão com capital real, eu manteria execução manual.

E, se a conta de investimentos estiver legalmente sob responsabilidade de um adulto, a aprovação/executação deve permanecer com o titular/responsável da conta e dentro das regras da corretora; o Marko não deve servir para contornar exigências de idade ou autorização.

---

# 45. Audit Log completo

Tudo gera log imutável.

```text
2026-08-20 08:01
Market data updated

08:03
Risk model recomputed

08:05
Black-Litterman view changed

08:06
Portfolio target changed
18.2% → 17.4%

08:07
Risk Officer approved

08:08
Rebalance proposal generated

09:16
Proposal manually accepted
```

Se daqui a dois anos perguntarmos:

> Por que compramos isso?

teremos a resposta.

---

# 46. Interface do Marko

Eu imagino algo com 10 áreas principais.

## Command Center

```text
Portfolio value
Today's change
Since inception
TWR
XIRR

Risk
Expected shortfall
Drawdown
Volatility

Allocation drift
New cash
Pending reviews
Data alerts

MARKO STATUS
NO ACTION REQUIRED
```

A última informação é importante.

O sistema precisa ser confortável em dizer:

> **Não faça nada.**

---

# 47. Portfolio

Visualizações:

```text
asset
asset class
sector
country
currency
factor
risk contribution
liquidity
```

E:

```text
Target vs Actual
```

---

# 48. Risk Cockpit

Quero aqui:

```text
Volatility
Expected Shortfall
VaR
CDaR
Max Drawdown
Beta
Tracking Error
Concentration
Correlation
Liquidity
FX risk
Rate sensitivity
```

E:

```text
Risk Contribution by Asset
Risk Contribution by Factor
```

---

# 49. Model Lab

Imagine:

```text
MODEL                   RETURN   RISK   DD    TO    STATUS

1/N
MinVar
BL
RiskParity
HRP
HERC
NCO
CVaR
DRO
...
```

Clicar abre:

```text
in-sample
out-of-sample
walk-forward
stress
parameter sensitivity
weights
model card
```

---

# 50. Disagreement Screen

Essa eu faria especialmente para o Marko:

```text
MODEL CONSENSUS

Asset X

MinVar     3%
BL         9%
HRP        5%
DRO        4%
RP         6%

Consensus: 5.4%
Dispersion: LOW
```

versus:

```text
Asset Y

2%
18%
0%
11%
3%

Dispersion: VERY HIGH
```

O segundo merece investigação.

---

# 51. Rebalance Screen

Nada de botão enorme:

> BUY NOW.

Tela:

```text
Current portfolio
Target portfolio

New contribution:
R$ ...

Suggested allocation of contribution:
...

Trades avoided:
...

Estimated costs:
...

Risk before:
...

Risk after:
...

Reason:
...

Models:
...

Approve proposal
Reject
Defer
```

---

# 52. Macro Cockpit

```text
Growth
Inflation
Rates
Credit
FX
Commodities
Liquidity
Fiscal
Global
```

Com:

```text
Current
Trend
Consensus
Marko estimate
Surprise
Regime
```

---

# 53. Research

Papers, hipóteses e experimentos:

```text
NEW PAPER
↓
Research Agent
↓
Model candidate
↓
Experiment
↓
Challenger
↓
Validation
↓
Rejected / Accepted
```

Nada vai diretamente:

```text
paper → production
```

---

# 54. Data Health

Eu quero uma tela que normalmente seria ignorada por projetos desse tipo:

```text
DATA HEALTH

Prices             ✓
FX                 ✓
Corporate actions  ✓
Macro              ✓
Fundamentals       ✓
News               ✓

Stale series: 0
Missing records: 0
Anomalies: 2
```

Se dados estiverem ruins:

```text
PORTFOLIO DECISION
FROZEN
```

Essa é a atitude certa.

---

# 55. A estratégia de desenvolvimento

Eu não construiria tudo ao mesmo tempo.

Teríamos estágios.

### Marko 0 — Archaeology

Nenhuma carteira.

Objetivo:

> estudar os repositórios existentes.

Deliverables:

```text
UPSTREAM_AUDIT.md
LICENSE_MATRIX.md
CAPABILITY_MATRIX.md
ARCHITECTURE_COMPARISON.md
REUSE_PLAN.md
```

---

# 56. Marko 0.1 — Financial Core

Primeiras entidades:

```text
Money
Currency
Instrument
Account
Transaction
Portfolio
Position
Liability
Benchmark
```

Sem IA.

Sem optimizer.

---

# 57. Marko 0.2 — Ledger

Importação manual de transações.

Precisamos provar:

```text
ledger
↓
holdings
↓
valuation
```

100% reproduzível.

---

# 58. Marko 0.3 — Market Data

```text
prices
dividends
splits
FX
rates
```

Com provenance e timestamps.

---

# 59. Marko 0.4 — Analytics

```text
TWR
XIRR
CAGR
vol
drawdown
Sharpe
Sortino
CVaR
CDaR
```

Validar contra QuantStats e implementações independentes.

---

# 60. Marko 0.5 — Baseline Portfolio Lab

Somente:

```text
1/N
Minimum Variance
Markowitz
Maximum Sharpe
```

Com diferentes covariâncias.

---

# 61. Marko 0.6 — Advanced Portfolio Lab

Adicionar:

```text
Black-Litterman
Risk Parity
Maximum Diversification
HRP
HERC
NCO
CVaR
CDaR
DRO
```

Aqui entram fortemente skfolio e Riskfolio.

---

# 62. Marko 0.7 — Validation Framework

Nada avança sem:

```text
walk-forward
bootstrap
stress tests
parameter sensitivity
transaction costs
multiple benchmarks
```

---

# 63. Marko 0.8 — Implementation Engine

Agora:

```text
Target Portfolio
↓
Trade Optimizer
```

Aportes mensais.

Turnover.

Custos.

Restrições.

Liabilities.

---

# 64. Marko 0.9 — Fundamentals + Macro

Só depois acrescentaria:

```text
fundamental features
factor models
macro features
regimes
```

---

# 65. Marko 0.10 — Black-Litterman Views

Agora o pipeline começa a ficar poderoso:

```text
Macro
Fundamentals
Factors
Valuation
↓
Views
↓
Confidence
↓
Black-Litterman
```

---

# 66. Marko 0.11 — Research Agents

LLMs começam a trabalhar.

Mas ainda em:

```text
READ
RESEARCH
PROPOSE
```

não:

```text
TRADE
```

---

# 67. Marko 0.12 — ML Research

Agora começamos a estudar Qlib.

Não antes.

Features:

```text
factor signals
macro
fundamentals
market
```

Modelos:

```text
linear regularized
tree models
boosting
neural models
```

Antes de qualquer coisa sofisticada.

Se linear ganhar de transformer:

> usamos linear.

---

# 68. Marko 0.13 — Regime Learning

```text
Markov Switching
HMM
Change Point
Adaptive covariance
```

Challengers apenas.

---

# 69. Marko 0.14 — Model Ensemble

O `Model Committee` passa a combinar modelos aprovados.

---

# 70. Marko 0.15 — Full Dashboard

Agora UI completa.

Até aqui os motores devem funcionar sem frontend.

---

# 71. Marko 0.16 — Shadow Portfolio

Esse é o primeiro grande teste operacional.

Criamos:

```text
SHADOW CAPITAL
R$ 50.000 virtuais
```

e simulamos exatamente:

```text
data arrives
models run
proposal generated
manual decision
portfolio updated
monthly contribution
```

Tudo como se fosse real.

O objetivo principal não é provar retorno.

É provar:

```text
dados corretos
ledger correto
ordens corretas
rebalancing correto
custos corretos
sem leakage
sem falhas operacionais
```

---

# 72. Marko 0.17 — Parallel portfolios

Rodamos simultaneamente:

```text
Marko Champion
1/N
Simple allocation
Risk-free benchmark
Market benchmark
Challengers
```

Todos exatamente com os mesmos fluxos de caixa.

---

# 73. Marko 0.18 — Red Team

Agora tentamos quebrar o próprio sistema.

Testes:

```text
Preço ausente
Preço errado ×100
Split não registrado
Dividend duplicated
FX stale
Banco offline
Model NaN
Optimizer infeasible
Negative cash
Duplicate transaction
Timezone mismatch
Macro revision
API timeout
Corrupted file
```

Marko precisa falhar com segurança.

---

# 74. Marko 0.19 — Investment Committee Review

Antes de capital real:

```text
Investment Policy
Model Cards
Backtesting methodology
Stress tests
Risk limits
Data provenance
Operational procedures
Failure handling
Liability analysis
```

Tudo revisado.

Para dinheiro real — especialmente dinheiro emprestado — eu também colocaria uma revisão humana externa como etapa sensata: um profissional habilitado pode questionar premissas que nós mesmos deixamos passar.

---

# 75. Marko 1.0 — Production Candidate

Aqui existe algo importantíssimo:

**Marko 1.0 provavelmente não usará todos os modelos que construímos.**

Talvez o laboratório tenha:

```text
35 modelos
```

e produção tenha:

```text
4 ou 5
```

Isso seria perfeitamente saudável.

Algo extremamente sofisticado pode ficar:

```text
RESEARCH ONLY
```

---

# 76. O gate para capital real

Eu criaria uma checklist formal.

### G1 — Accounting

```text
0 divergências de ledger
```

### G2 — Data

```text
point-in-time semantics validated
corporate actions validated
provenance complete
```

### G3 — Backtesting

```text
no known leakage
costs included
benchmarks included
walk-forward enabled
```

### G4 — Robustness

O resultado não desaparece quando alteramos levemente:

```text
window
start date
rebalance date
covariance estimator
cost assumptions
```

### G5 — Risk

```text
stress tests passed
IPS limits enforced
liability shortfall measured
```

### G6 — Execution

```text
cash-flow rebalancing tested
order generation tested
rounding tested
failed optimizer handled
```

### G7 — Audit

Toda decisão é reproduzível.

### G8 — Shadow operation

Sistema operou sem incidentes materiais.

### G9 — Human review

Premissas e limites aprovados.

### G10 — Legal/account ownership

A execução real está de acordo com as regras aplicáveis à conta e ao titular/responsável.

Só então:

```text
LIVE_CANDIDATE = TRUE
```

---

# 77. Eu ainda não colocaria todo o capital imediatamente

Mesmo depois de Marko passar nesses gates, eu distinguiria:

```text
software production-ready
```

de:

```text
investment strategy proven
```

São coisas completamente diferentes.

O sistema pode estar tecnicamente perfeito e a estratégia ser ruim.

A transição para capital real deveria começar com uma exposição deliberadamente pequena, determinada em conjunto com o responsável legal/titular da conta e compatível com a obrigação de devolver o empréstimo, enquanto o restante permanece em instrumentos adequados à preservação do capital e liquidez.

Eu não definiria hoje um percentual específico antes de termos o IPS e os termos do empréstimo.

---

# 78. Depois disso: Marko 2

Aí sim eu começaria a ficar realmente experimental.

```text
Bayesian model averaging
Dynamic Black-Litterman
Entropy Pooling
Dynamic risk budgets
Online learning
Concept drift
Bayesian covariance
Regime-specific priors
Distributionally robust optimization
Multi-period optimization
Scenario-conditioned allocation
```

---

# 79. E Marko 3

A fronteira mais experimental:

```text
Deep learning
representation learning
transformers for financial time series
graph models
alternative data
RL
agent-based portfolio research
```

Mas tudo como challenger.

Nunca porque:

> é IA, portanto deve ser melhor.

---

# 80. O que eu pediria ao Codex AGORA

Neste momento eu não mandaria o Codex começar a construir o Marko.

Mandaria ele fazer uma **arqueologia comparativa brutalmente detalhada dos repositórios**.

E acrescentaria `cvxportfolio` à lista.

Este é o prompt que eu usaria:

Quero que você faça uma auditoria técnica profunda dos repositórios open source que estamos clonando como referências para o projeto **Marko**, um sistema quantitativo pessoal de gestão de investimentos, pesquisa, risco, portfolio construction, backtesting, contabilidade e monitoramento.

NÃO copie código desses projetos para dentro do Marko neste momento.

NÃO tente integrar tudo.

NÃO faça grandes refactors.

O objetivo desta etapa é entender exatamente o que cada projeto já resolveu, quais conceitos e arquiteturas podemos aproveitar, quais bibliotecas podem ser dependências do Marko e quais projetos devem permanecer apenas como referências.

## Repositórios a analisar

* skfolio/skfolio
* dcajasn/Riskfolio-Lib
* PyPortfolio/PyPortfolioOpt
* cvxgrp/cvxportfolio
* polakowo/vectorbt
* ranaroussi/quantstats
* OpenBB-finance/OpenBB
* microsoft/qlib
* ghostfolio/ghostfolio
* wealthfolio/wealthfolio
* portfolio-performance/portfolio

Caso algum ainda não tenha sido clonado, clone-o em uma área de referências separada do código do Marko.

Não coloque esses repositórios dentro de `marko/src`, não faça vendor e não copie seus arquivos.

Preferência de estrutura:

```text
marko-references/
├── skfolio/
├── Riskfolio-Lib/
├── PyPortfolioOpt/
├── cvxportfolio/
├── vectorbt/
├── quantstats/
├── OpenBB/
├── qlib/
├── ghostfolio/
├── wealthfolio/
└── portfolio-performance/
```

## Para cada repositório, registre

1. URL upstream.
2. Branch analisada.
3. Commit SHA exato.
4. Tag/release, quando aplicável.
5. Linguagens.
6. Dependências principais.
7. Licença.
8. Consequências aparentes da licença para:

   * projeto pessoal;
   * uso como dependência;
   * modificação;
   * redistribuição;
   * eventual produto comercial.
9. Estrutura arquitetural.
10. Módulos mais importantes.
11. APIs públicas.
12. Modelos matemáticos implementados.
13. Estruturas de dados principais.
14. Padrões de teste.
15. Estratégia de validação.
16. Backtesting.
17. Performance analytics.
18. Data ingestion.
19. Portfolio accounting.
20. Risk management.
21. Optimization.
22. Experiment tracking.
23. Agent/AI support.
24. UI/UX relevante.
25. Pontos fortes.
26. Pontos fracos.
27. Funcionalidades duplicadas por outros repositórios.
28. Funcionalidades únicas.
29. Componentes que poderíamos utilizar diretamente como dependência.
30. Componentes dos quais devemos apenas copiar o conceito arquitetural, NÃO o código.

## Atenção especial: skfolio

Analise profundamente:

* optimization;
* expected returns / priors;
* covariance estimators;
* shrinkage;
* Black-Litterman;
* risk budgeting;
* hierarchical optimization;
* HRP;
* HERC;
* NCO;
* CVaR;
* CDaR;
* Distributionally Robust CVaR;
* Maximum Diversification;
* model selection;
* cross-validation;
* walk-forward;
* ensemble/stacking;
* transaction costs;
* turnover constraints;
* regularization;
* stress testing.

Quero entender se skfolio pode funcionar como o principal motor quantitativo de portfolio construction do Marko através de um adapter.

## Atenção especial: Riskfolio-Lib

Analise:

* Portfolio;
* HCPortfolio;
* RiskFunctions;
* ParamsEstimation;
* factor models;
* risk measures;
* risk contribution;
* risk parity;
* hierarchical portfolios;
* graph/network approaches;
* CVaR/CDaR;
* Kelly formulations;
* uncertainty sets;
* robust optimization;
* constraints;
* solvers CVXPY.

Compare diretamente com skfolio.

Identifique funcionalidades que Riskfolio possui e skfolio não possui, e vice-versa.

## Atenção especial: PyPortfolioOpt

Use principalmente como implementação independente e benchmark.

Analise:

* expected_returns;
* risk_models;
* covariance shrinkage;
* efficient_frontier;
* objective_functions;
* Black-Litterman;
* HRP.

Quero saber quais partes são suficientemente simples para servir como "oracle" de validação cruzada dos nossos resultados.

Por exemplo:

```text
Marko MinVariance
vs
skfolio MinVariance
vs
PyPortfolioOpt MinVariance
```

com o mesmo dataset e as mesmas constraints.

## Atenção especial: cvxportfolio

Analise profundamente:

* simulator;
* policies;
* forecasts;
* transaction costs;
* holding costs;
* constraints;
* risk models;
* Single Period Optimization;
* Multi Period Optimization;
* execution simulation.

Quero entender como utilizar suas ideias para a camada:

```text
TARGET PORTFOLIO
↓
TRADE OPTIMIZATION
↓
IMPLEMENTATION
```

e para uma função objetivo conceitualmente semelhante a:

```text
tracking error to target
+ transaction cost
+ tax impact
+ turnover
+ risk penalties
```

Não incorpore código GPL ao Marko nesta etapa.

## Atenção especial: vectorbt

Analise como research/backtest harness.

Principalmente:

* large parameter sweeps;
* portfolio simulation;
* walk-forward;
* indicators;
* signals;
* performance;
* parallel/vectorized execution;
* experiment patterns.

Como a licença atual contém Commons Clause, não faça dele dependência estrutural obrigatória do Marko.

Trate-o inicialmente como ferramenta do ambiente de research.

## Atenção especial: QuantStats

Mapeie:

* stats;
* reports;
* plots;
* drawdown;
* rolling metrics;
* Sharpe;
* Sortino;
* CVaR;
* performance reports.

Precisamos descobrir quais métricas podem ser utilizadas diretamente e quais deveremos implementar no `marko.analytics` para termos controle e testes independentes.

## Atenção especial: OpenBB

Não copie o sistema.

Estude principalmente:

```text
Provider
Query
Standardized data model
Adapter
API
Data source abstraction
```

Queremos utilizar suas decisões arquiteturais como referência para desenhar:

```text
Marko Data Gateway
```

capaz de trocar provedores sem alterar o domínio.

Considere também as implicações da AGPL.

## Atenção especial: Qlib

Trate como referência para fases futuras.

Analise:

* dataset architecture;
* feature pipelines;
* experiment/workflow management;
* ML models;
* model registry;
* online/offline workflow;
* alpha research;
* backtesting;
* portfolio;
* execution;
* concept drift;
* automated research/RD-Agent.

Não tente incorporar Qlib ao MVP.

Precisamos saber o que vale reaproveitar quando chegarmos ao `Marko ML`.

## Atenção especial: Ghostfolio

Trate principalmente como referência de produto.

Analise:

* accounts;
* transactions;
* holdings;
* portfolio performance;
* import workflows;
* data providers;
* database model;
* portfolio dashboard;
* allocation UX;
* performance UX.

Não copie código AGPL para Marko.

## Atenção especial: Wealthfolio

Analise:

* local-first architecture;
* portfolio/accounting;
* storage;
* Rust/TypeScript boundary;
* addon architecture;
* agent tools;
* MCP implementation;
* permission model;
* portfolio UX;
* import flows.

A existência de `wealthfolio-agent-tools` e `wealthfolio-mcp` é especialmente relevante para o futuro `Marko Agent`.

Entenda como eles separam ferramentas, permissões, storage e interface de agente.

Não copie código AGPL.

## Atenção especial: Portfolio Performance

Trate como referência muito madura de portfolio accounting.

Analise:

* transaction model;
* securities;
* accounts;
* dividends;
* fees;
* corporate actions;
* performance calculation;
* TWR;
* IRR/XIRR;
* benchmarks;
* tax lots quando aplicável;
* imports;
* PDF import architecture;
* portfolio reconciliation.

Não precisamos copiar a implementação Java.

Queremos entender os invariantes contábeis e os edge cases que muitos projetos simples ignoram.

# Comparação cruzada

Crie uma matriz:

```text
CAPABILITY                 SK   RF   PPO   CVXP   VBT   QS   QLIB ...

Mean Variance
Black-Litterman
Shrinkage
Risk Parity
HRP
HERC
NCO
CVaR
CDaR
DRO
Factor Models
Transaction Costs
Multi-period Optimization
Walk-forward
Purged CV
Backtesting
Performance Analytics
Accounting
Data Providers
ML
Agent Architecture
...
```

Use:

```text
FULL
PARTIAL
NONE
REFERENCE
```

# Spikes

Depois da auditoria, crie pequenos experimentos isolados em:

```text
research/spikes/
```

Nunca no domínio principal.

Por exemplo:

```text
001-skfolio-minvar/
002-riskfolio-minvar/
003-pypfopt-minvar/
004-black-litterman/
005-hrp/
006-cvar/
007-cvxportfolio-costs/
008-quantstats/
```

Todos devem usar, quando possível, o mesmo pequeno dataset reproduzível.

Queremos testar:

1. instalação;
2. API;
3. resultado;
4. velocidade;
5. estabilidade;
6. dependencies;
7. facilidade de adapter;
8. diferenças numéricas.

# Cross-validation numérica

Para modelos equivalentes, compare implementações diferentes.

Por exemplo:

```text
Minimum Variance

skfolio
Riskfolio
PyPortfolioOpt
```

Normalize:

* retornos;
* covariância;
* bounds;
* solver;
* frequência;
* annualization.

Depois compare os pesos.

Não conclua imediatamente que uma biblioteca está errada.

Investigue diferenças de:

* conventions;
* annualization;
* solver;
* defaults;
* covariance;
* risk-free rate;
* normalization;
* constraints.

# Reprodutibilidade

Todo spike precisa registrar:

```text
Python version
package versions
commit SHA
dataset hash
configuration
random seed
solver
runtime
```

# Deliverables

Crie:

```text
docs/research/upstreams/
├── skfolio.md
├── riskfolio.md
├── pyportfolioopt.md
├── cvxportfolio.md
├── vectorbt.md
├── quantstats.md
├── openbb.md
├── qlib.md
├── ghostfolio.md
├── wealthfolio.md
└── portfolio-performance.md
```

E na raiz de pesquisa:

```text
UPSTREAM_AUDIT.md
CAPABILITY_MATRIX.md
LICENSE_MATRIX.md
REUSE_PLAN.md
ARCHITECTURE_COMPARISON.md
UPSTREAM_RISK_REGISTER.md
```

Além disso, crie:

```text
upstreams.lock.json
```

com commit SHA, branch/tag e licença de cada upstream analisado.

# Classificação final

Para cada funcionalidade estudada, classifique como:

```text
A — USE AS DEPENDENCY
B — WRAP BEHIND ADAPTER
C — REIMPLEMENT WITH TESTS
D — ARCHITECTURAL REFERENCE ONLY
E — RESEARCH TOOL ONLY
F — DO NOT USE
```

Explique o motivo.

# Regra arquitetural importante

O domínio do Marko NÃO deve depender diretamente das classes de skfolio, Riskfolio, Qlib, OpenBB etc.

Exemplo:

```text
Marko OptimizerPort
       ↓
SkfolioOptimizerAdapter
```

e não:

```text
MarkoPortfolio extends SkfolioPortfolio
```

Queremos ser capazes de remover qualquer biblioteca externa sem destruir o domínio.

# Não faça nesta etapa

* Não implemente o Marko inteiro.
* Não copie grandes blocos de código.
* Não escolha uma carteira real.
* Não crie ordens.
* Não conecte corretora.
* Não implemente trading automático.
* Não otimize para retorno de backtest.
* Não introduza ML sem necessidade.
* Não coloque todos os upstreams como dependências do projeto.

Esta etapa termina quando conseguirmos responder com segurança:

> "O que já existe, o que devemos reutilizar, o que devemos encapsular, o que devemos reimplementar e o que devemos apenas estudar?"

Ao final, apresente também uma proposta de quais **5 a 10 componentes concretos** deveriam ser implementados primeiro no Marko e quais upstreams servirão como referência ou dependência para cada um.

Essa seria exatamente a próxima coisa que eu faria. Em particular, eu gostaria de ver o relatório desse agente antes de deixá-lo escrever a arquitetura principal, porque há uma boa chance de economizarmos meses de trabalho ao descobrir onde `skfolio`, `Riskfolio` e `cvxportfolio` já resolveram corretamente problemas que não precisamos resolver de novo.

E a ideia central que eu manteria durante todo o projeto seria esta:

[
\boxed{
\text{Marko}
\neq
\text{modelo de previsão}
}
]

mas:

[
\boxed
======

\text{Data}
+
\text{Evidence}
+
\text{Models}
+
\text{Uncertainty}
+
\text{Risk}
+
\text{Portfolio}
+
\text{Implementation}
+
\text{Accounting}
+
\text{Governance}
}
]

O componente mais valioso no final talvez nem seja aquele que responde “o que comprar”, mas aquele capaz de responder, a qualquer momento, **o que possuímos, por que possuímos, quais riscos estamos assumindo, quais modelos sustentam a decisão, em que condições a decisão deixa de ser válida e o que aconteceria conosco se estivermos errados**. Isso é o que eu tentaria transformar no núcleo intelectual do Marko.

[1]: https://github.com/cvxgrp/cvxportfolio?utm_source=chatgpt.com
[2]: https://github.com/skfolio/skfolio?utm_source=chatgpt.com
[3]: https://github.com/dcajasn/Riskfolio-Lib?utm_source=chatgpt.com
[4]: https://github.com/PyPortfolio/PyPortfolioOpt?utm_source=chatgpt.com
[5]: https://github.com/polakowo/vectorbt/blob/master/README.md?utm_source=chatgpt.com
[6]: https://github.com/ranaroussi/quantstats?utm_source=chatgpt.com
[7]: https://github.com/microsoft/qlib?utm_source=chatgpt.com
[8]: https://github.com/OpenBB-finance/OpenBB?utm_source=chatgpt.com
[9]: https://github.com/portfolio-performance/portfolio?utm_source=chatgpt.com
[10]: https://github.com/robertmartin8/PyPortfolioOpt?utm_source=chatgpt.com
