from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent / "common"))
from harness import ASSETS, dataset_hash, returns

ROOT = Path(__file__).parent
FILES = {
    "skfolio": ROOT / "001-skfolio-minvar/result.json",
    "riskfolio": ROOT / "002-riskfolio-minvar/result.json",
    "pyportfolioopt": ROOT / "003-pypfopt-minvar/result.json",
}


def main() -> None:
    data = returns()
    covariance = data.cov().to_numpy()
    weights = {}
    for name, path in FILES.items():
        result = json.loads(path.read_text())
        weights[name] = np.array([result["result"]["weights"][asset] for asset in ASSETS])

    metrics = {}
    for name, vector in weights.items():
        metrics[name] = {
            "sum": float(vector.sum()),
            "daily_volatility": float(np.sqrt(vector @ covariance @ vector)),
            "weights": dict(zip(ASSETS, vector.tolist(), strict=True)),
        }
    pairs = {}
    names = list(weights)
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            pairs[f"{left}__{right}"] = {
                "l1": float(np.abs(weights[left] - weights[right]).sum()),
                "max_abs": float(np.abs(weights[left] - weights[right]).max()),
            }
    payload = {
        "dataset_sha256": dataset_hash(data),
        "metrics": metrics,
        "pairwise_weight_distance": pairs,
    }
    (ROOT / "minvar-cross-validation.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    main()
