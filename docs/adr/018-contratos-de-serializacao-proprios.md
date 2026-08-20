# ADR 018 — Contratos de serialização próprios

## Decisão

Activity, Observation, ModelRun e DecisionPacket são persistidos em envelopes JSON canônicos com `schema`, `version` e `payload`. Cada envelope possui SHA-256 calculado após ordenação determinística das chaves.

## Consequências

O storage não depende da representação interna de dataclasses nem de objetos de bibliotecas upstream. Versões desconhecidas falham explicitamente; mudanças futuras exigem novo codec e migração declarada.
