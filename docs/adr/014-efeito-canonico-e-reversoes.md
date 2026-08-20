# ADR 014 — Efeito contábil canônico e reversões

## Decisão

Cada `ActivityKind` possui campos permitidos e um efeito canônico. Uma reversão referencia um evento anterior e precisa reproduzir integralmente seu payload; o projetor aplica o efeito inverso. Lotes são reconstruídos excluindo o par original/reversão no instante aplicável.

## Consequências

Payload arbitrário de reversão é rejeitado. Nenhum campo monetário aceito pode ser ignorado. Projeções históricas usam `as_of` e preservam o evento original.
