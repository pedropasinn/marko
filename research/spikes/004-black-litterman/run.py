import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

from harness import run
from pypfopt import EfficientFrontier, black_litterman


def experiment(data):
    covariance = data.cov() * 252
    caps = {"CDI": 35, "IPCA": 20, "BR_EQ": 15, "GLOBAL_EQ": 30}
    prior = black_litterman.market_implied_prior_returns(caps, 2.5, covariance, risk_free_rate=0.10)
    views = {"CDI": 0.115, "IPCA": 0.105, "BR_EQ": 0.135, "GLOBAL_EQ": 0.125}
    model = black_litterman.BlackLittermanModel(
        covariance,
        pi=prior,
        absolute_views=views,
        omega="idzorek",
        view_confidences=[0.85, 0.65, 0.35, 0.45],
    )
    posterior = model.bl_returns()
    ef = EfficientFrontier(posterior, model.bl_cov(), solver="CLARABEL")
    ef.max_quadratic_utility(risk_aversion=2.5)
    return {
        "posterior_returns": posterior.to_dict(),
        "weights": ef.clean_weights(),
        "solver": "CLARABEL",
    }


run(
    Path(__file__).with_name("result.json"),
    ["pyportfolioopt"],
    {"model": "black_litterman", "tau": 0.05},
    experiment,
)
