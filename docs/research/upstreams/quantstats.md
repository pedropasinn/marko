# QuantStats

## Ficha

- Origem: `https://github.com/ranaroussi/quantstats.git`; `main`; `fbd10daed0227aa0d10da6513f1b15e7e98d7fae`; versão `0.0.81`.
- Linguagem/dependências: Python; pandas, NumPy, SciPy, Matplotlib, Seaborn e yfinance.
- Licença: Apache-2.0; permissiva, preservando avisos.
- Arquitetura/APIs: `stats`, `reports`, `plots` e `utils`, com integração opcional a pandas.
- Testes: unitários para métricas e geração de relatórios; analytics e apresentação ainda se misturam.

## Cobertura

Sharpe, Sortino, volatilidade, drawdown, VaR/CVaR, rolling metrics, retornos por período, benchmark e tearsheets HTML. Não é ledger, backtest ou motor de decisão. Download implícito via yfinance não deve existir no domínio.

## Avaliação

- Fortes: cobertura prática e relatório rápido.
- Fracos: convenções/annualization exigem alinhamento e algumas funções combinam transformação e apresentação.
- Duplicações: métricas presentes em todos os simuladores.
- Único: tearsheet compacto.
- Classificação: **C — REIMPLEMENT WITH TESTS** para TWR, XIRR, drawdown, Sharpe, Sortino e CVaR; QuantStats permanece oráculo.
