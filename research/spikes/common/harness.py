from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pandas as pd

ASSETS = ["CDI", "IPCA", "BR_EQ", "GLOBAL_EQ"]
SEED = 20260820
UPSTREAM_COMMITS = {
    "skfolio": "07dd64b3640fc4350d3d092837a978a87e9e4b34",
    "riskfolio-lib": "632a9e48fbaf2b9f8e83864a492332364b6ed32c",
    "pyportfolioopt": "a6638d2e06dae6f444fd022cfd4b3c528902a85b",
    "cvxportfolio": "351c782b9b8b395c1a5f886b77e0d55f1bc9396e",
    "quantstats": "fbd10daed0227aa0d10da6513f1b15e7e98d7fae",
}


def returns() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    annual_mean = np.array([0.115, 0.105, 0.135, 0.125])
    annual_vol = np.array([0.008, 0.045, 0.235, 0.185])
    corr = np.array(
        [
            [1.00, 0.18, -0.06, -0.04],
            [0.18, 1.00, 0.10, 0.08],
            [-0.06, 0.10, 1.00, 0.52],
            [-0.04, 0.08, 0.52, 1.00],
        ]
    )
    cov = np.outer(annual_vol, annual_vol) * corr / 252
    values = rng.multivariate_normal(annual_mean / 252, cov, size=504)
    index = pd.bdate_range("2024-08-01", periods=504)
    return pd.DataFrame(values, index=index, columns=ASSETS)


def dataset_hash(data: pd.DataFrame) -> str:
    payload = data.to_csv(index=True, float_format="%.17g").encode()
    return hashlib.sha256(payload).hexdigest()


def run(
    result_path: Path,
    packages: list[str],
    config: dict,
    experiment: Callable[[pd.DataFrame], dict],
) -> None:
    data = returns()
    started = time.perf_counter()
    result = experiment(data)
    elapsed = time.perf_counter() - started
    record = {
        "python": platform.python_version(),
        "packages": {name: importlib.metadata.version(name) for name in packages},
        "commits": {name: UPSTREAM_COMMITS[name] for name in packages},
        "dataset_sha256": dataset_hash(data),
        "observations": len(data),
        "assets": ASSETS,
        "seed": SEED,
        "configuration": config,
        "runtime_seconds": elapsed,
        "result": result,
    }
    result_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
