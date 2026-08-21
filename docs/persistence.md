# Persistência e shadow readiness

## Contratos

O domínio depende das portas `ActivityRepository`, `ObservationRepository`, `ModelRunRepository`, `ShadowRunRequestRepository`, `DecisionPacketRepository` e `ShadowCycleRepository`. `PostgresStore` implementa as seis portas sem expor tipos do driver. Transferências e suas reversões entram por `append_activities`, no mesmo commit; um evento pareado isolado é rejeitado.

Os objetos são serializados em envelopes próprios:

```json
{"schema":"marko.activity","version":1,"payload":{}}
```

O JSON canônico e seu SHA-256 sustentam idempotência, conflito e verificação de leitura. O decoder exige chaves exatas, rejeita duplicatas, `NaN`/infinito, timestamps sem timezone e identidades semânticas divergentes. `DecisionPacket` v3 preserva o vínculo com `ShadowRunRequest` e o `knowledge_cutoff` usando referências compactas e verificáveis aos `ModelRun`; v1 e v2 continuam legíveis.

## PostgreSQL

```bash
export MARKO_DATABASE_URL='postgresql://usuario:senha@host/marko'
uv run marko db-migrate
```

As migrações usam advisory lock, checksum e transação. Activity, Observation, ModelRun, ShadowRunRequest e DecisionPacket aceitam somente `INSERT`; triggers bloqueiam `UPDATE` e `DELETE`. Colunas derivadas são conferidas contra o payload canônico durante a leitura.

No deploy, migrações e seed usam a credencial proprietária fora do runtime. A Read API recebe uma credencial dedicada com somente `SELECT` e `default_transaction_read_only=on`; ela não possui autoridade para escrever fatos nem alterar schema ou o ledger de migrações.

## Backup e restore

```bash
export MARKO_BACKUP_ENCRYPTION_KEY='<chave-base64-de-32-bytes>'
uv run marko backup --private var/private/backup.json
uv run marko backup-verify var/private/backup.json
uv run marko backup-restore var/private/backup.json
```

O documento interno de backup v3 com `metadata.version = 4` contém envelopes canônicos das seis coleções, incluindo `ShadowCycleRecord`, metadados de schemas e hash global. O backup privado conserva o envelope externo v4 e cifra e autentica esse documento com AES-256-GCM, chave base64 externa de 32 bytes, nonce aleatório e `key_id` não secreto; o arquivo nunca armazena a chave. Documentos publicados com formatos v1–v3, metadados v1–v3 e HMAC-SHA256 permanecem legíveis para migração.

Antes de escrever, o restore decodifica e valida o lote inteiro: IDs únicos, integridade do ledger, ModelRuns referenciados, vínculos entre DecisionPacket e ShadowRunRequest e todas as referências, hashes, reconciliação e diário dos ciclos shadow. O envelope do ciclo contém apenas referências canônicas aos objetos core, sem repetir matriz de retornos. O PostgreSQL insere core e ciclos na mesma transação. Reexecução idêntica é idempotente; referência ausente, conflito de identidade ou autenticação falha fechado.

## Parquet

`ParquetObservationStore` grava datasets imutáveis com Zstandard. O nome contém o hash do conteúdo; os metadados registram schema, dataset e hash. Antes da publicação atômica, o arquivo temporário passa por round trip completo. A leitura valida:

- schema, `dataset_id` e hash em formato estrito;
- conjunto exato de colunas;
- payload JSON canônico e SHA-256 do conteúdo;
- ordem canônica e unicidade de `observation_id`;
- igualdade entre colunas derivadas e o envelope decodificado;
- SHA-256 do arquivo como evidência adicional.

Parquet é artefato de pesquisa, não fonte operacional.

## Shadow

```bash
uv run marko shadow-due \
  --day 20 \
  --after 2026-07-20T13:00:00+00:00 \
  --until 2026-08-20T13:00:00+00:00

uv run marko shadow-reconcile packet-id \
  --checked-at 2026-08-20T13:05:00+00:00
```

Cada execução nasce de um `ShadowRunRequest` com identidade determinística, instante agendado e `knowledge_cutoff`. O DecisionPacket carrega o mesmo par; a reconciliação bloqueia request divergente, ModelRun ausente/futuro, fingerprint de dataset divergente e Observation indisponível no corte.

`ShadowCycleJournal` preserva transições `scheduled -> draft -> reviewed -> reconciled`, com estado `blocked` explícito e cadeia de hashes append-only. `ShadowCycleRecord` liga request, snapshot, vintages, ModelRuns, DecisionPacket, reconciliação e diário sem transformar revisão em aprovação ou execução. Relatórios de benchmark calculam TWR, drawdown e drift para carteira observada, CDI e 1/N; séries ausentes permanecem visíveis como falha.

Nenhum comando executa capital real.
