# ADR 019 — PostgreSQL operacional e Parquet de pesquisa

## Decisão

PostgreSQL guarda os fatos operacionais append-only. Parquet guarda datasets de observações imutáveis e endereçados pelo hash do conteúdo. O banco é a fonte operacional; artefatos de pesquisa não sobrescrevem fatos contábeis ou decisões.

## Consequências

Consultas e integridade transacional ficam separadas de varreduras analíticas. O Parquet preserva o envelope canônico em vez de criar um segundo contrato de domínio.
