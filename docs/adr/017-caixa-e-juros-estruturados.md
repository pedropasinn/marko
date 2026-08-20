# ADR 017 — Caixa e termos de juros estruturados

## Decisão

Caixa é parâmetro próprio do rebalanceador e usa `CashTarget`; não depende de instrumento chamado `CASH`. Empréstimos usam `InterestTerms` com taxa, capitalização, day-count, frequência e arredondamento explícitos.

## Consequências

Pesos projetados sempre incluem caixa e somam um. Cálculos do passivo permanecem em `Decimal` e não dependem de uma mini-linguagem textual ambígua.
