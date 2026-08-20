# Marko v0.3.0 — Persistence and Shadow Readiness

## Objetivo

Persistir Accounting, Data, Research e Decision Truth sem acoplar o domínio ao banco e preparar ciclos shadow reproduzíveis, sem execução real.

## Escopo

- portas próprias de repositório;
- envelopes JSON canônicos e versionados;
- PostgreSQL append-only para Activity, Observation, ModelRun e DecisionPacket;
- artefatos Parquet imutáveis para datasets de observações;
- migrações com checksum e serialização concorrente;
- idempotência e detecção de conflitos por hash;
- backup, verificação e restore idempotente;
- agenda shadow mensal e reconciliação ponto-no-tempo;
- golden cases de TWR, transferências, FX e corporate actions;
- CLI e CI de integração com PostgreSQL 16.

## Fora de escopo

- integração de escrita com corretoras;
- envio ou aprovação automática de ordens;
- capital real;
- novos modelos de portfólio;
- mudança do PostgreSQL por uma abstração de ORM.

## Invariantes de aceite

1. schemas desconhecidos falham explicitamente;
2. serialização e hashes são canônicos;
3. repetir o mesmo ID e payload é idempotente;
4. repetir o mesmo ID com payload diferente é conflito;
5. UPDATE e DELETE das quatro verdades persistidas são bloqueados;
6. migrações aplicadas não podem mudar de checksum;
7. backup adulterado não é restaurado;
8. Parquet preserva envelopes e proveniência sem virar fonte operacional;
9. ciclo shadow usa somente evidência disponível no instante da decisão;
10. nenhuma função deste marco habilita capital real.

## Verificação

```bash
uv sync --group dev --extra persistence --frozen
uv run ruff check .
uv run mypy
uv run pytest --cov=marko --cov-report=term-missing --cov-fail-under=80
MARKO_TEST_POSTGRES_DSN=postgresql://... uv run pytest -m persistence
uv build
```
