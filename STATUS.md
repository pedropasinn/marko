# Estado do Marko

Atualizado em 20/08/2026. Versão atual: `0.3.2` — Packaging Integrity.

## Em uma frase

O Marko persiste fatos contábeis, dados ponto-no-tempo, pesquisa, solicitações e decisões shadow em contratos auditáveis, e os expõe por API e Console somente leitura; capital real e dados reais continuam bloqueados.

## Gates

| Gate | Estado | Evidência |
|---|---|---|
| Arqueologia open source | concluído | 11 auditorias, lockfile e 8 spikes |
| Accounting kernel | concluído | reversões derivadas, activity matrix e lotes `as_of` |
| Analytics e reconciliação | concluído no corte atual | valuation falha fechado e atribuição separa principal |
| Configuração pessoal | aguardando dados | `uv run marko status` lista nove campos |
| Data Gateway | parcial operacional | BCB/SGS e SIDRA ao vivo; Tesouro Direto usa o CKAN oficial; ANBIMA/B3 aguardam credenciais |
| Baseline Portfolio Lab | concluído | cinco baselines e adapters opcionais testáveis no CI |
| Validation Framework | concluído no corte atual | candidato validado, drift, step e PSD explícitos |
| Decision Engine | concluído no corte atual | caixa explícito e ModelRun validado |
| Persistência | endurecida | backup privado AES-256-GCM, restore validado, codecs estritos e Parquet verificado |
| Shadow portfolio | integridade operacional concluída | `ShadowRunRequest`, `knowledge_cutoff`, diário append-only, reconciliação PIT e benchmarks sintéticos |
| Read API | concluída no corte atual | `/api/v1` somente leitura, modo demo explícito, erros sanitizados e CORS restrito |
| Marko Console | concluído no corte atual | React/TypeScript/PWA; estados sintético, HTTP e indisponível sem fallback enganoso |
| Deploy público | sintético | Console e API na Vercel; Neon exclusivamente sintético em `gru1`; API usa role PostgreSQL somente leitura |
| Capital real | bloqueado | depende de todos os gates e revisão humana |

## Agora

1. cadastrar as duas identidades fora do Git e ativar o modo privado já implementado;
2. receber os dados ainda ausentes e gerar o IPS apenas em configuração privada;
3. obter as credenciais e contratos atuais de ANBIMA e B3;
4. definir duração mínima e iniciar ciclos shadow sem capital real;
5. manter capital real bloqueado até revisão humana e histórico operacional suficiente.

## Qualidade

O CI preserva Ruff, MyPy strict, cobertura mínima de 80%, integração PostgreSQL/Parquet, adapters opcionais e smokes de providers. A versão `0.3.2` também inspeciona conteúdo e tamanho do source distribution; wheel e Console continuam com build e smoke próprios. A validação local atual tem 156 testes aprovados, 3 integrações condicionais ignoradas e 82,77% de cobertura.

Ambiente público: [Console](https://marko-console.vercel.app) e [Read API](https://marko-api.vercel.app/api/v1/status). Ambos são sintéticos; Neon Auth apenas habilitada não autoriza ingestão de dados reais.

O roadmap completo está em [`docs/roadmap.md`](docs/roadmap.md). O contexto para agentes e revisores está em [`docs/HANDOFF_GPT_PRO.md`](docs/HANDOFF_GPT_PRO.md).
