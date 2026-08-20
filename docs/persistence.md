# Persistência e shadow readiness

## Contratos

O domínio depende das portas `ActivityRepository`, `ObservationRepository`, `ModelRunRepository` e `DecisionPacketRepository`. `PostgresStore` implementa as quatro portas sem expor tipos do driver. Transferências e suas reversões entram por `append_activities`, no mesmo commit; um evento pareado isolado é rejeitado.

Os objetos são serializados em envelopes próprios:

```json
{"schema":"marko.activity","version":1,"payload":{}}
```

O JSON canônico e seu SHA-256 sustentam idempotência, conflito e verificação de leitura.

## PostgreSQL

```bash
export MARKO_DATABASE_URL='postgresql://usuario:senha@host/marko'
uv run marko db-migrate
```

As migrações usam advisory lock, checksum e transação. Activity, Observation, ModelRun e DecisionPacket aceitam somente `INSERT`; triggers bloqueiam `UPDATE` e `DELETE`.

## Backup e restore

```bash
uv run marko backup var/private/backup.json
uv run marko backup-verify var/private/backup.json
uv run marko backup-restore var/private/backup.json
```

O backup contém envelopes canônicos e hash global. O restore é idempotente e rejeita conflito de identidade.

## Parquet

`ParquetObservationStore` grava datasets imutáveis com Zstandard. O nome contém o hash do conteúdo; os metadados registram schema, dataset e hash. Parquet é artefato de pesquisa, não fonte operacional.

## Shadow

```bash
uv run marko shadow-due \
  --day 20 \
  --after 2026-07-20T13:00:00+00:00 \
  --until 2026-08-20T13:00:00+00:00

uv run marko shadow-reconcile packet-id \
  --checked-at 2026-08-20T13:05:00+00:00
```

A reconciliação bloqueia ModelRun ausente ou divergente e Observation indisponível no instante da decisão. Nenhum comando executa capital real.
