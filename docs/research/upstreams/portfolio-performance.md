# Portfolio Performance

## Ficha

- Origem: `https://github.com/portfolio-performance/portfolio.git`; `master`; `90b27560fc0804878386911227cac6d01b7a28fa`; versão `0.87.1-SNAPSHOT`.
- Linguagem/dependências: Java; Eclipse RCP/SWT e módulos Maven.
- Licença: EPL-1.0. Uso pessoal permitido; modificações e redistribuição exigem atenção à reciprocidade por módulo. Usar como referência/oráculo.
- Arquitetura/APIs: model, money, snapshot, performance, taxonomy, importers e UI separados em módulos.
- Testes: JUnit, fixtures de extratos e testes de cálculo/importação.

## Cobertura

Valores monetários inteiros/exatos, moedas e câmbio; securities, accounts e portfolios; BUY, SELL, DELIVERY, TRANSFER, dividendos, juros, taxas e impostos; gross value, ordenação estável e snapshots. Calcula TWR, IRR/XIRR, drawdown, volatilidade, benchmarks, FIFO/média móvel e atribuição. `Trail` explica a composição de resultados. Importadores de PDF/bancos normalizam documentos variados e reconciliação ocorre por contas e transações.

Corporate actions e tax lots expõem edge cases essenciais: splits, spin-offs, transferências, forex, arredondamento, ordem no mesmo instante e correções sem reescrever história.

## Avaliação

- Fortes: maturidade contábil, variedade de casos e explicabilidade.
- Fracos: desktop Java, regras europeias e EPL; não é motor quantitativo.
- Duplicações: ledger com Wealthfolio/Ghostfolio.
- Único: profundidade dos importadores e trilha explicativa dos cálculos.
- Classificação: **C — REIMPLEMENT WITH TESTS** para invariantes; **D** para arquitetura/importadores; oráculo manual para casos dourados.
