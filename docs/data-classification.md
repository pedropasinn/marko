# Classificação de dados

## Público

Código, documentação, ADRs, issues, dados sintéticos, resultados de testes e metadados de fontes públicas sem informação pessoal.

## Interno não sensível

Artefatos reproduzíveis de pesquisa que não contêm posições, extratos, credenciais ou fatos pessoais. Só são publicados após inspeção do diff.

## Privado financeiro

Configuração real do caso, saldos, posições, transações, passivos, extratos, declarações, relatórios e decisões individualizadas. Devem ficar fora do Git em `var/private/`, `data/private/`, `config/*.local.toml` ou caminho externo informado por `MARKO_CASE_PATH`.

## Secret

Tokens, chaves, cookies, credenciais de providers, brokers e bancos. Devem usar variáveis de ambiente ou secret manager; nunca arquivos versionados, logs ou fixtures.

## Publicação

Antes de qualquer commit, revisar nomes de arquivos, diff staged e padrões de segredo. Dados privados não podem ser anonimizados apenas removendo o nome: valores, datas e relações também podem identificar o proprietário.

O Console e a Read API públicos operam somente com fixtures sintéticas; o Neon em `gru1` deve permanecer vazio ou conter apenas dados sintéticos. Neon Auth habilitada na infraestrutura não satisfaz sozinha o gate de acesso. Nenhum dado privado financeiro pode ser enviado ao ambiente público antes de autenticação efetiva ponta a ponta, autorização por identidade e IPS armazenado fora do repositório.
