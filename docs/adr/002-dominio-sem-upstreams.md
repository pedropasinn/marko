# ADR 002 — Domínio independente de upstreams

Status: aceita

## Decisão

Bibliotecas quantitativas e providers só entram por adapters. Tipos externos não atravessam as portas do núcleo.

## Consequência

O motor principal pode mudar sem migrar ledger, IPS ou decisões históricas.
