# Spikes quantitativos

Todos usam 504 retornos diários sintéticos, quatro ativos, semente `20260820` e o mesmo hash serializado. Os ambientes são separados porque Riskfolio exige CVXPY recente e cvxportfolio fixa CVXPY `<1.7`.

```bash
research/.venv-quant/bin/python research/spikes/001-skfolio-minvar/run.py
research/.venv-quant/bin/python research/spikes/002-riskfolio-minvar/run.py
research/.venv-quant/bin/python research/spikes/003-pypfopt-minvar/run.py
research/.venv-quant/bin/python research/spikes/004-black-litterman/run.py
research/.venv-quant/bin/python research/spikes/005-hrp/run.py
research/.venv-quant/bin/python research/spikes/006-cvar/run.py
research/.venv-cvxportfolio/bin/python research/spikes/007-cvxportfolio-costs/run.py
research/.venv-quant/bin/python research/spikes/008-quantstats/run.py
```

Cada `result.json` registra Python, pacote, commit, hash do dataset, configuração, semente, solver, duração e resultado. Os arquivos são evidência do snapshot, não dados de produção.
