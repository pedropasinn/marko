# Estado do Marko

Atualizado em 20/08/2026. Versão: `0.2.0`.

## Em uma frase

O Marko já possui um núcleo auditável que transforma fatos contábeis, dados ponto-no-tempo e modelos básicos em drafts de rebalanceamento; ainda não recomenda nem executa capital real.

## Gates

| Gate | Estado | Evidência |
|---|---|---|
| Arqueologia open source | concluído | 11 auditorias, lockfile e 8 spikes |
| Accounting kernel | concluído | dinheiro exato, ledger e 55 testes integrados |
| Analytics e reconciliação | concluído no corte inicial | XIRR golden, TWR, drawdown, snapshots e lotes |
| Configuração pessoal | aguardando dados | `uv run marko status` lista nove campos |
| Data Gateway | parcial operacional | BCB/SGS e SIDRA ao vivo; demais aguardam acesso |
| Baseline Portfolio Lab | concluído | cinco baselines e dois adapters factíveis |
| Validation Framework | concluído no corte inicial | walk-forward, purge, embargo, custos e stress |
| Decision Engine | concluído no modo aporte | `NO_ACTION` e `cash_flow_only` |
| Shadow portfolio | não iniciado | depende de IPS e persistência |
| Capital real | bloqueado | depende de todos os gates e revisão humana |

## Agora

1. receber os nove dados do caso pessoal;
2. persistir ledger, observations, ModelRuns e DecisionPackets;
3. adicionar regras fiscais brasileiras e casos TWR multimoeda;
4. configurar Tesouro Direto, ANBIMA e B3;
5. iniciar shadow operation.

## Qualidade

```text
55 testes
85% de cobertura
Ruff aprovado
MyPy strict aprovado
BCB/SGS e SIDRA validados ao vivo
```

O roadmap completo está em [`docs/roadmap.md`](docs/roadmap.md). O contexto para agentes e revisores está em [`docs/HANDOFF_GPT_PRO.md`](docs/HANDOFF_GPT_PRO.md).
