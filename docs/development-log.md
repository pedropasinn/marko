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

## 20/08/2026 — Marko 0.3.0 Persistence and Shadow Readiness

- envelopes JSON canônicos e versionados para as quatro verdades persistidas;
- portas próprias e adapter PostgreSQL append-only;
- migrações empacotadas com advisory lock e checksum;
- datasets de observações em Parquet imutável e endereçado por conteúdo;
- backup atômico, verificação de integridade e restore idempotente;
- scheduler mensal shadow com timezone e corte de conhecimento;
- reconciliação de ModelRuns, candidatos e evidências ponto-no-tempo;
- casos dourados de TWR com fluxos, transferências, FX e corporate actions;
- CLI operacional e job de integração PostgreSQL 16/Parquet.
- 92 testes locais aprovados, 2 integrações condicionais e 84% de cobertura.

## 20/08/2026 — Marko 0.3.1 Operational Integrity

- `ShadowRunRequest` virou verdade persistida e o `knowledge_cutoff` passou a acompanhar todo o ciclo;
- DecisionPacket, ModelRun, fingerprint de dataset, snapshot, vintages e observações passaram a ser reconciliados no mesmo corte PIT;
- diário shadow append-only com transições e cadeia de hashes;
- relatório sintético de TWR, drawdown e drift contra CDI e 1/N, sem inventar séries ausentes;
- backup privado v4 AES-256-GCM, restore com pré-validação semântica e aplicação atômica no PostgreSQL;
- endurecimento de codecs e validação integral de artefatos Parquet;
- provider do Tesouro Direto migrado para descoberta pelo CKAN oficial do Tesouro Transparente;
- Read API FastAPI e Marko Console React/TypeScript/PWA somente leitura;
- Console e API publicados como demonstração sintética, com Neon exclusivamente sintético em `gru1` e Neon Auth habilitada;
- `DecisionPacket@3` compacto e ciclos shadow completos persistidos de forma append-only;
- CI ampliado com frontend e smoke do wheel, preservando os gates anteriores.
- validação local: 156 testes aprovados, 3 integrações condicionais ignoradas e 82,77% de cobertura; frontend com 8 testes, typecheck, build PWA e auditoria sem vulnerabilidades.

A publicação tornou a fronteira de segurança mais explícita: Neon Auth habilitada não basta. Dados reais permanecem proibidos até autenticação efetiva e IPS privado.

## 20/08/2026 — Marko 0.3.2 Packaging Integrity

- o sdist foi reduzido ao pacote Python, testes e documentos essenciais;
- dependências, builds e configuração local do Console ficaram fora do artefato Python;
- o CI passou a rejeitar source distributions anormais ou contendo caminhos de ambiente, deploy e dados privados.

## Como este diário evolui

Cada versão deve registrar decisões, resultados negativos, incompatibilidades e dívidas técnicas. O changelog descreve o que mudou; este diário explica por que a direção mudou.
