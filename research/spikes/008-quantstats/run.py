import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

import quantstats.stats as stats
from harness import run


def experiment(data):
    portfolio = data.mean(axis=1)
    return {
        "sharpe": float(stats.sharpe(portfolio, periods=252, annualize=True)),
        "sortino": float(stats.sortino(portfolio, periods=252, annualize=True)),
        "max_drawdown": float(stats.max_drawdown(portfolio)),
        "cvar_95": float(stats.cvar(portfolio, confidence=0.95)),
        "volatility": float(stats.volatility(portfolio, periods=252, annualize=True)),
    }


run(
    Path(__file__).with_name("result.json"),
    ["quantstats"],
    {"portfolio": "equal_weight", "periods": 252},
    experiment,
)
