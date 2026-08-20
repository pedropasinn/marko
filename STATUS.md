# Estado do Marko

Atualizado em 20/08/2026. Versão atual: `0.3.0`.

## Em uma frase

O Marko já persiste fatos contábeis, dados ponto-no-tempo, pesquisa e decisões em contratos auditáveis e prepara ciclos shadow; ainda não recomenda nem executa capital real.

## Gates

| Gate | Estado | Evidência |
|---|---|---|
| Arqueologia open source | concluído | 11 auditorias, lockfile e 8 spikes |
| Accounting kernel | concluído | reversões derivadas, activity matrix e lotes `as_of` |
| Analytics e reconciliação | concluído no corte atual | valuation falha fechado e atribuição separa principal |
| Configuração pessoal | aguardando dados | `uv run marko status` lista nove campos |
| Data Gateway | parcial operacional | BCB/SGS e SIDRA ao vivo; demais aguardam acesso |
| Baseline Portfolio Lab | concluído | cinco baselines e adapters opcionais testáveis no CI |
| Validation Framework | concluído no corte atual | candidato validado, drift, step e PSD explícitos |
| Decision Engine | concluído no corte atual | caixa explícito e ModelRun validado |
| Persistência | concluída | PostgreSQL 16 validado no CI; Parquet, codecs, migrações e backup implementados |
| Shadow portfolio | readiness concluída | scheduler mensal e reconciliação PIT validados; operação depende de IPS |
| Capital real | bloqueado | depende de todos os gates e revisão humana |

## Agora

1. receber os dados ainda ausentes do caso pessoal em configuração privada;
2. configurar Tesouro Direto, ANBIMA e B3;
3. definir benchmarks e duração mínima da operação shadow;
4. iniciar ciclos shadow sem capital real;
5. manter capital real bloqueado até revisão humana e histórico operacional suficiente.

## Qualidade

```text
92 testes locais aprovados, 2 integrações condicionais
84% de cobertura
Ruff aprovado
MyPy strict aprovado
PostgreSQL 16/Parquet aprovados em job próprio; skfolio e PyPortfolioOpt em job opcional
```

O roadmap completo está em [`docs/roadmap.md`](docs/roadmap.md). O contexto para agentes e revisores está em [`docs/HANDOFF_GPT_PRO.md`](docs/HANDOFF_GPT_PRO.md).
