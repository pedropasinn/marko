import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

from harness import run
from pypfopt import EfficientFrontier


def experiment(data):
    ef = EfficientFrontier(data.mean(), data.cov(), weight_bounds=(0.0, 1.0), solver="CLARABEL")
    ef.min_volatility()
    return {
        "weights": dict(zip(data.columns, ef.weights.tolist(), strict=True)),
        "solver": "CLARABEL",
    }


run(
    Path(__file__).with_name("result.json"),
    ["pyportfolioopt"],
    {"model": "minimum_variance", "long_only": True},
    experiment,
)
