# OpenBB

## Ficha

- Origem: `https://github.com/OpenBB-finance/OpenBB.git`; `develop`; `3e071fcc2cd9f891cac6040ae60296dba76dab46`; core `1.6.13`.
- Linguagens/dependências: Python no platform; TypeScript/Rust no desktop; Pydantic, FastAPI e pacotes por provider.
- Licença: AGPL-3.0. Uso pessoal é possível; distribuição/serviço modificado traz obrigações de fonte. Somente referência nesta fase.
- Arquitetura/APIs: modelo padronizado, query model, `Fetcher`, provider registry, query executor, extensions e API REST/Python.
- Testes: contratos por provider, fixtures e validação dos modelos padronizados.

## Cobertura

Cada fonte transforma uma consulta padrão, extrai dados específicos e os converte ao resultado canônico. Registry e command routing desacoplam consumidores do fornecedor. O clone inspecionado não oferece cobertura nativa suficiente para BCB/Selic, SIDRA, ANBIMA e B3 exigida pelo Marko.

Não resolve point-in-time por si só: disponibilidade, revisão, vintage, proveniência e qualidade ainda precisam estar no nosso envelope.

## Avaliação

- Fortes: isolamento de providers, extensibilidade e schemas validados.
- Fracos: plataforma grande, AGPL e provedores com credenciais/qualidade heterogêneas.
- Duplicações: ingestão com Qlib; UX/API com apps patrimoniais.
- Único: catálogo amplo sob um protocolo comum.
- Classificação: **D — ARCHITECTURAL REFERENCE ONLY**; eventual OpenBB externo passa por adapter.
