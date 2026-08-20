# Wealthfolio

## Ficha

- Origem: `https://github.com/wealthfolio/wealthfolio.git`; `main`; `ac95f786f83c37009dc8d623bca7244bd76c4a24`; versão `3.7.0`.
- Linguagens/dependências: Rust e TypeScript; Tauri, web frontend, SQLite e servidor opcional.
- Licença: AGPL-3.0. Arquitetura pode ser estudada; código não será incorporado nesta fase.
- Arquitetura/APIs: core local-first em Rust, boundary Tauri/HTTP, storage, addons, portfolio domain, agent tools e MCP.
- Testes: unitários Rust/TS, fixtures, evals de ferramentas de agente e fluxos de importação.

## Cobertura

Ledger e snapshots, FX, posições, metas, drift absoluto/híbrido, contribuições, whole shares, minimum trade e algoritmo guloso de redução de drift. Modos `CashFlowOnly`, `SellToRebalance` e `Hybrid` tornam explícita a política de rebalanceamento. Importação, reconciliação e health checks completam o fluxo local-first.

As ferramentas de agente separam `Read`, `Suggest`, `Draft` e `Write`, scopes e pré-requisitos. Mudança é preparada, apresentada, autorizada e só então persistida; auditoria sanitiza parâmetros sensíveis. É o padrão do Marko Agent.

## Avaliação

- Fortes: domínio exato, privacidade, cenários de drift e governança do agente.
- Fracos: AGPL e regras tributárias/mercados diferentes do Brasil.
- Duplicações: tracking com Ghostfolio; accounting com Portfolio Performance.
- Único: união de produto local-first, rebalanceamento por aporte e tool permissions.
- Classificação: **D — ARCHITECTURAL REFERENCE ONLY**; especificações próprias serão reimplementadas com testes.
