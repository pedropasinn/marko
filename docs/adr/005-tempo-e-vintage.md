# ADR 005 — Quatro tempos e Data Vintage

Status: aceita

## Decisão

Dados guardam `effective_at`, `observed_at`, `available_at`, `ingested_at` e pertencem a um vintage versionado.

## Consequência

Datasets ponto-no-tempo podem ser reconstruídos e auditados contra look-ahead.
