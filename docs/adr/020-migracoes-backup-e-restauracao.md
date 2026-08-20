# ADR 020 — Migrações, backup e restauração

## Decisão

Migrações SQL são numeradas, empacotadas, protegidas por advisory lock e registradas com checksum. As tabelas operacionais rejeitam UPDATE e DELETE. Backup usa documento canônico com hash global, escrita atômica e restore idempotente.

## Consequências

Uma migração aplicada não pode ser reescrita silenciosamente. Backup adulterado falha antes do restore; IDs iguais com conteúdo divergente continuam sendo conflitos.
