# Data Gateway brasileiro

## Implementado

- BCB/SGS: séries por código, intervalo e unidade declarada;
- IBGE/SIDRA: tabela, variável, território e período;
- Tesouro Direto: adapter JSON com endpoint injetado;
- ANBIMA e B3: adapters autenticados com endpoint/schema injetados;
- calendário de dias úteis;
- store idempotente, leitura `as_known_at`, revisão por período e dimensões e Data Vintage;
- hash do payload bruto para auditoria de mudanças no parser.

BCB e SIDRA foram exercitados contra os endpoints oficiais em 20/08/2026. Como as respostas consultadas não informam o instante histórico de publicação, o adapter usa a ingestão como disponibilidade conservadora e marca `availability_conservative`.

O endpoint JSON legado do Tesouro Direto respondeu HTTP 410. Nenhum substituto foi inventado: o adapter exige endpoint atual configurado. ANBIMA e B3 exigem credenciais e contrato de dados antes de smoke test real.
