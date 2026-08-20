# ADR 013 — Fronteira entre código público e estado financeiro privado

## Decisão

O repositório contém somente configuração sintética. O caso real é carregado por `MARKO_CASE_PATH` ou arquivo local ignorado. Extratos, bancos, Parquet bruto, logs e secrets ficam fora do Git.

## Consequências

O projeto continua reproduzível sem publicar fatos financeiros. Testes não podem depender do caso real. Todo exemplo precisa declarar que é sintético.
