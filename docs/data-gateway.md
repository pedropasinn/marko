# Data Gateway brasileiro

## Implementado

- BCB/SGS: séries por código, intervalo e unidade declarada;
- IBGE/SIDRA: tabela, variável, território e período;
- Tesouro Direto: descoberta do CSV pelo catálogo CKAN oficial do Tesouro Transparente, com normalização decimal pt-BR, proveniência do recurso e hash do CSV;
- ANBIMA e B3: adapters autenticados com endpoint/schema injetados;
- calendário de dias úteis;
- store idempotente, leitura `as_known_at`, revisão por período e dimensões e Data Vintage;
- hash do payload bruto para auditoria de mudanças no parser.

BCB e SIDRA foram exercitados contra os endpoints oficiais em 20/08/2026. Como as respostas consultadas não informam o instante histórico de publicação, o adapter usa a ingestão como disponibilidade conservadora e marca `availability_conservative`.

O provider do Tesouro consulta o pacote `taxas-dos-titulos-ofertados-pelo-tesouro-direto` em `https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show`, seleciona o recurso CSV HTTPS mais recente e preserva URL, data de modificação e SHA-256 do arquivo na evidência. O endpoint JSON injetável permanece apenas como seam de integração/teste; não é o default operacional.

ANBIMA e B3 continuam bloqueados por credenciais e contrato de dados. Nenhum smoke real desses providers deve ser declarado antes de acesso autorizado.
