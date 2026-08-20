# Ghostfolio

## Ficha

- Origem: `https://github.com/ghostfolio/ghostfolio.git`; `main`; `7a2ba0d8d665c2bd58a4ca04fb44a66e190bad0c`; versão `3.56.0`.
- Linguagem/dependências: TypeScript; Angular, NestJS, Prisma, PostgreSQL e Nx.
- Licença: AGPL-3.0. Uso pessoal possível; não copiar para produto fechado sem cumprir a licença.
- Arquitetura/APIs: monorepo web/API, serviços de portfolio, data providers, regras, importação, contas, ordens e modelo Prisma.
- Testes: Jest e testes de serviços/componentes; regras de análise e imports têm casos próprios.

## Cobertura

Múltiplas contas, atividades, holdings, alocação, composição, performance, benchmarks, importação e dashboards maduros. A arquitetura de providers e regras é útil como referência de UX. No commit auditado, implementações de calculadores TWR e MWR ainda lançam `Method not implemented`, portanto não são oráculos contábeis confiáveis.

## Avaliação

- Fortes: visão consolidada de produto, fluxos de importação e apresentação patrimonial.
- Fracos: AGPL, domínio acoplado à aplicação e lacuna nos calculadores citados.
- Duplicações: tracking e dashboard com Wealthfolio/Portfolio Performance.
- Único: conjunto maduro de regras de saúde do portfólio em aplicação web.
- Classificação: **D — ARCHITECTURAL REFERENCE ONLY**.
