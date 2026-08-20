import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

from harness import run
from pypfopt import EfficientCVaR


def experiment(data):
    model = EfficientCVaR(data.mean(), data, beta=0.95, solver="CLARABEL")
    model.min_cvar()
    return {"weights": model.clean_weights(), "solver": "CLARABEL"}


run(
    Path(__file__).with_name("result.json"),
    ["pyportfolioopt"],
    {"model": "minimum_cvar", "beta": 0.95},
    experiment,
)
