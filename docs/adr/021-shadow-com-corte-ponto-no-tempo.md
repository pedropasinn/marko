# ADR 021 — Shadow com corte ponto-no-tempo

## Decisão

Cada solicitação shadow possui instante agendado e `knowledge_cutoff`. Antes de considerar um DecisionPacket pronto, a reconciliação exige os ModelRuns exatos e todas as evidências disponíveis até o instante da decisão.

## Consequências

Evidência futura, execução ausente ou candidato divergente bloqueiam o ciclo. O scheduler produz solicitações determinísticas, mas não aprova, registra nem envia ordens.
