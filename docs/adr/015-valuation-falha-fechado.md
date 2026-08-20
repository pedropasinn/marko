# ADR 015 — Valuation falha fechado

## Decisão

Valuation retorna valor, completude, preços ausentes, FX ausente, cotações vencidas e evidências. `net_liquidation_value` só retorna `Money` quando o resultado é completo.

## Consequências

Patrimônio parcial não pode ser confundido com patrimônio líquido total. Preços e FX carregam observação, fonte, vintage, `as_of` e `available_at`.
