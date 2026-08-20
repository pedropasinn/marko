# Marko

[![CI](https://github.com/pedropasinn/marko/actions/workflows/ci.yml/badge.svg)](https://github.com/pedropasinn/marko/actions/workflows/ci.yml)

Núcleo auditável de um gestor quantitativo pessoal orientado a passivos. O estado atual cobre Accounting/Policy, dados ponto-no-tempo, baselines, validação, persistência append-only e preparação de ciclos shadow; não recomenda nem executa investimentos reais.

O desenvolvimento é público. O [estado atual](STATUS.md), o [roadmap](docs/roadmap.md), o [changelog](CHANGELOG.md), o [diário de desenvolvimento](docs/development-log.md), as issues e as discussões mostram o que foi concluído, o que falhou e o que vem depois.

## Desenvolvimento

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run mypy
```

```bash
uv run marko status
uv run marko fetch-bcb 1178 --start 2026-08-18 --end 2026-08-19 --unit "% a.a."
uv run marko fetch-sidra IPCA --table 1737 --variable 2266 --period "last 1"
```

Persistência opcional:

```bash
uv sync --group dev --extra persistence
export MARKO_DATABASE_URL='postgresql://usuario:senha@host/marko'
uv run marko db-migrate
uv run marko backup var/private/backup.json
uv run marko backup-verify var/private/backup.json
```

## Mapas

- [Handoff completo para GPT Pro](docs/HANDOFF_GPT_PRO.md)
- [Contexto do domínio](CONTEXT.md)
- [Arquitetura](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Invariantes](docs/invariants.md)
- [Classificação e fronteira de dados](docs/data-classification.md)
- [Accounting](docs/accounting.md)
- [Casos dourados contábeis](docs/golden-accounting-cases.md)
- [Data Gateway](docs/data-gateway.md)
- [Portfolio Lab](docs/portfolio-lab.md)
- [Decision Engine](docs/decision-engine.md)
- [Persistência e shadow readiness](docs/persistence.md)
- [Auditoria dos upstreams](docs/research/UPSTREAM_AUDIT.md)
- [Spikes quantitativos](research/spikes/README.md)

Os snapshots dos projetos estudados ficam em `/home/pedro/repo/marko-references` e são fixados por [`upstreams.lock.json`](upstreams.lock.json).

Dados pessoais e financeiros reais não pertencem ao repositório. Use `MARKO_CASE_PATH` ou `config/personal-case.local.toml`; o arquivo versionado é apenas um exemplo sintético.
