import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

from harness import run
from skfolio import RiskMeasure
from skfolio.optimization import HierarchicalRiskParity


def experiment(data):
    model = HierarchicalRiskParity(risk_measure=RiskMeasure.VARIANCE).fit(data)
    return {"weights": dict(zip(data.columns, model.weights_.tolist(), strict=True))}


run(
    Path(__file__).with_name("result.json"),
    ["skfolio"],
    {"model": "hrp", "distance": "correlation"},
    experiment,
)
