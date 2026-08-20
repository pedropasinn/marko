# ADR 007 — skfolio como motor principal atrás de adapter

Status: aceita

## Decisão

Usar skfolio para portfolio construction e validação temporal sem expor sua API no domínio.

## Consequência

PyPortfolioOpt e Riskfolio permanecem oráculos independentes; resultados passam por pós-validação própria.
