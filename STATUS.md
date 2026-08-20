# Estado do Marko

Atualizado em 20/08/2026. Versão em desenvolvimento: `0.2.1`.

## Em uma frase

O Marko já possui um núcleo auditável que transforma fatos contábeis, dados ponto-no-tempo e modelos básicos em drafts de rebalanceamento; ainda não recomenda nem executa capital real.

## Gates

| Gate | Estado | Evidência |
|---|---|---|
| Arqueologia open source | concluído | 11 auditorias, lockfile e 8 spikes |
| Accounting kernel | endurecimento em curso | reversões derivadas, activity matrix e lotes `as_of` |
| Analytics e reconciliação | endurecimento em curso | valuation falha fechado e atribuição separa principal |
| Configuração pessoal | aguardando dados | `uv run marko status` lista nove campos |
| Data Gateway | parcial operacional | BCB/SGS e SIDRA ao vivo; demais aguardam acesso |
| Baseline Portfolio Lab | concluído | cinco baselines e adapters opcionais testáveis no CI |
| Validation Framework | endurecimento em curso | candidato validado, drift, step e PSD explícitos |
| Decision Engine | endurecimento em curso | caixa explícito e ModelRun validado |
| Persistência | bloqueada | depende da conclusão da v0.2.1 |
| Shadow portfolio | não iniciado | depende de IPS e v0.3.0 |
| Capital real | bloqueado | depende de todos os gates e revisão humana |

## Agora

1. concluir os invariantes e golden cases da v0.2.1;
2. receber os dados ainda ausentes do caso pessoal em configuração privada;
3. iniciar persistência somente após o gate de integridade;
4. configurar Tesouro Direto, ANBIMA e B3;
5. preparar shadow operation.

## Qualidade

```text
75 testes do quality gate e 1 integração opcional
86% de cobertura
Ruff aprovado
MyPy strict aprovado
skfolio e PyPortfolioOpt em job opcional
```

O roadmap completo está em [`docs/roadmap.md`](docs/roadmap.md). O contexto para agentes e revisores está em [`docs/HANDOFF_GPT_PRO.md`](docs/HANDOFF_GPT_PRO.md).
