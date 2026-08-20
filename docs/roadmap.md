# Roadmap canônico

Versões descrevem entregas do software. Gates descrevem capacidades e permanecem estáveis mesmo quando várias delas avançam na mesma release.

## Versões

### v0.2.1 — Integrity Hardening

Estado: concluída em 20/08/2026.

Fronteira público/privado, reversões e lotes, activity matrix, valuation completo, proveniência bruta, validação de candidatos, drift walk-forward, caixa explícito, termos de juros estruturados, CLI e CI em camadas.

### v0.3.0 — Persistence and Shadow Readiness

Estado: em desenvolvimento.

Portas de repositório, contratos de serialização versionados, PostgreSQL operacional, Parquet de pesquisa, migrações, round trips, idempotência, backup/restore, scheduler shadow e reconciliação.

## Gates de capacidade

| Gate | Capacidade | Estado |
|---|---|---|
| G1 | Accounting | endurecimento v0.2.1 concluído |
| G2 | Analytics | corte inicial implementado |
| G3 | Data | BCB/SGS e SIDRA operacionais; demais pendentes |
| G4 | Baselines | implementado |
| G5 | Validation | endurecimento v0.2.1 concluído |
| G6 | Advanced Models | não iniciado |
| G7 | Decision | draft por aporte e candidato validado |
| G8 | Research Agents | não iniciado |
| G9 | Shadow | scheduler e reconciliação PIT em validação; operação ainda não iniciada |

## Gate para capital real

Accounting reconciliado, dados PIT completos, testes anti-look-ahead, limites de risco, execução simulada, auditoria, shadow por período suficiente, revisão humana e definição formal do empréstimo. Tempo curto de shadow valida operação, não retorno esperado.
