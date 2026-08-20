import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

from harness import run
from skfolio import RiskMeasure
from skfolio.optimization import MeanRisk, ObjectiveFunction


def experiment(data):
    model = MeanRisk(
        objective_function=ObjectiveFunction.MINIMIZE_RISK,
        risk_measure=RiskMeasure.VARIANCE,
        min_weights=0.0,
        max_weights=1.0,
        solver="CLARABEL",
    ).fit(data)
    return {
        "weights": dict(zip(data.columns, model.weights_.tolist(), strict=True)),
        "solver": "CLARABEL",
    }


run(
    Path(__file__).with_name("result.json"),
    ["skfolio"],
    {"model": "minimum_variance", "long_only": True},
    experiment,
)
