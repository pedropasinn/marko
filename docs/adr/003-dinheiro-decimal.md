# ADR 003 — Dinheiro decimal e moeda explícita

Status: aceita

## Decisão

Usar `Decimal` quantizado pela moeda para fatos liquidados. Float fica restrito a retornos e matrizes de pesquisa.

## Consequência

Operações entre moedas diferentes falham; FX exige evento e taxa explícitos.
