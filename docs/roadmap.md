# Roadmap canônico

Versões descrevem entregas do software. Gates descrevem capacidades e permanecem estáveis mesmo quando várias delas avançam na mesma release.

## Versões

### v0.2.1 — Integrity Hardening

Estado: concluída em 20/08/2026.

Fronteira público/privado, reversões e lotes, activity matrix, valuation completo, proveniência bruta, validação de candidatos, drift walk-forward, caixa explícito, termos de juros estruturados, CLI e CI em camadas.

### v0.3.0 — Persistence and Shadow Readiness

Estado: concluída em 20/08/2026.

Portas de repositório, contratos de serialização versionados, PostgreSQL operacional, Parquet de pesquisa, migrações, round trips, idempotência, backup/restore, scheduler shadow e reconciliação.

### v0.3.1 — Operational Integrity

Estado: concluída em 20/08/2026.

Persistência de `ShadowRunRequest`, ciclos completos e `knowledge_cutoff`, diário operacional shadow append-only, benchmarks e falhas explícitas, referências compactas de `ModelRun`, backup privado AES-256-GCM, hardening de restore/codecs/Parquet, Read API somente leitura, Marko Console React/TypeScript/PWA e deploy público exclusivamente sintético.

### v0.3.2 — Packaging Integrity

Estado: concluída em 20/08/2026.

Source distribution minimalista, sem dependências ou builds do Console, com inspeção automática de tamanho, arquivos de ambiente, artefatos de deploy e áreas privadas no CI.

### v0.4.0 — Personal IPS and Shadow Operation

Estado: aguardando informações e acessos do proprietário.

Autenticação efetiva, Liability/IPS/Universe reais em configuração privada, credenciais atuais de ANBIMA/B3 e operação shadow prolongada sem capital real. O provider do Tesouro Direto já usa o CKAN oficial; os benchmarks CDI/1/N e o diário existem no núcleo, mas ainda precisam de operação com o caso privado.

## Gates de capacidade

| Gate | Capacidade | Estado |
|---|---|---|
| G1 | Accounting | endurecimento v0.2.1 concluído |
| G2 | Analytics | corte inicial implementado |
| G3 | Data | BCB/SGS, SIDRA e contrato CKAN do Tesouro; ANBIMA/B3 bloqueados por credenciais |
| G4 | Baselines | implementado |
| G5 | Validation | endurecimento v0.2.1 concluído |
| G6 | Advanced Models | não iniciado |
| G7 | Decision | draft por aporte e candidato validado |
| G8 | Research Agents | não iniciado |
| G9 | Shadow | integridade operacional concluída; histórico real aguarda autenticação e IPS privado |

## Gate para capital real

Accounting reconciliado, dados PIT completos, testes anti-look-ahead, limites de risco, execução simulada, auditoria, shadow por período suficiente, revisão humana e definição formal do empréstimo. Tempo curto de shadow valida operação, não retorno esperado.
