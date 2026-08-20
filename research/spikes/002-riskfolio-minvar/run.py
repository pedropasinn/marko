import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

import riskfolio as rp
from harness import run


def experiment(data):
    portfolio = rp.Portfolio(returns=data)
    portfolio.assets_stats(method_mu="hist", method_cov="hist")
    weights = portfolio.optimization(model="Classic", rm="MV", obj="MinRisk", rf=0, l=0, hist=True)
    return {"weights": weights["weights"].to_dict(), "solver": str(portfolio.solvers)}


run(
    Path(__file__).with_name("result.json"),
    ["riskfolio-lib"],
    {"model": "minimum_variance", "long_only": True},
    experiment,
)
