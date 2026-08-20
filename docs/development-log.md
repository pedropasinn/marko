# Diário de desenvolvimento

## 20/08/2026 — Fundação e arqueologia

- definição do Marko como gestor quantitativo pessoal orientado a passivos;
- separação entre Accounting, Research e Decision Truth;
- clones fixados de onze upstreams;
- auditorias, matrizes de capacidade/licença e registro de riscos;
- oito spikes com dataset comum;
- descoberta da incompatibilidade HRP do PyPortfolioOpt 1.6.0 com SciPy 1.18;
- validação cruzada de minimum variance.

## 20/08/2026 — Marko 0.1

- núcleo `Decimal` e multimoeda;
- Instrument Master e contas;
- activities e ledger append-only;
- passivos, funding ratio e shortfall;
- IPS, Universe, Constraints e quatro tempos;
- 24 testes iniciais.

## 20/08/2026 — Marko 0.2

- transferências, FX e corporate actions;
- FIFO, custo médio e amortização de base;
- snapshots, reconciliação e analytics;
- configuração pessoal sem defaults inventados;
- BCB/SGS e SIDRA testados ao vivo;
- baselines internos e adapters upstream;
- ModelRun, validação temporal e stress;
- `NO_ACTION` e rebalanceamento pelo aporte;
- 55 testes, 85% de cobertura e fluxo integrado.

## 20/08/2026 — Marko 0.2.1 Integrity Hardening

- persistência suspensa até o fechamento dos invariantes;
- separação entre exemplo público e configuração financeira privada;
- correção de reversões em lotes e validação estrita do payload original;
- activity matrix e rejeição de moedas não cadastradas;
- valuation completo/incompleto com proveniência de preço e FX;
- correção da identidade multidimensional SIDRA e hash bruto de vintage;
- candidato pós-validado obrigatório no caminho de decisão;
- correções de walk-forward, stress de correlação e caixa explícito;
- termos de juros estruturados sem conversão para `float`;
- CI em quality gate, integração opcional e provider smoke.
- 75 testes do quality gate, 1 integração opcional, 86% de cobertura, Ruff e MyPy strict aprovados.

## Como este diário evolui

Cada versão deve registrar decisões, resultados negativos, incompatibilidades e dívidas técnicas. O changelog descreve o que mudou; este diário explica por que a direção mudou.
