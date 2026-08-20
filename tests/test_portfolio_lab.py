from datetime import UTC, datetime

import numpy as np

from marko.portfolio_lab import (
    EqualWeight,
    InverseVolatility,
    MinimumVariance,
    NoAction,
    PortfolioProblem,
    RiskBudgeting,
    check_candidate,
)
from marko.research_registry import ModelRunRegistry, SolverRecord, execute_model_run


def problem() -> PortfolioProblem:
    rng = np.random.default_rng(20260820)
    returns = rng.multivariate_normal(
        [0.0003, 0.0004, 0.0005],
        [
            [0.00001, 0.000002, 0.000001],
            [0.000002, 0.00009, 0.00002],
            [0.000001, 0.00002, 0.00016],
        ],
        size=300,
    )
    return PortfolioProblem(
        ("LOW", "MID", "HIGH"),
        tuple(tuple(float(value) for value in row) for row in returns),
        current_weights=(0.5, 0.3, 0.2),
        maximum_weights=(0.8, 0.8, 0.8),
    )


def test_baselines_are_feasible_and_distinct() -> None:
    task = problem()
    candidates = [
        NoAction().solve(task),
        EqualWeight().solve(task),
        InverseVolatility().solve(task),
        MinimumVariance(shrinkage=0.1).solve(task),
        RiskBudgeting().solve(task),
    ]
    assert all(not check_candidate(candidate, task) for candidate in candidates)
    assert candidates[3].weight_map()["LOW"] > candidates[3].weight_map()["HIGH"]
    assert len({candidate.weights for candidate in candidates}) == len(candidates)


def test_bounds_are_enforced_by_closed_form_projection() -> None:
    task = PortfolioProblem(
        ("A", "B"),
        ((0.01, 0.02), (0.02, 0.01), (0.0, 0.01)),
        minimum_weights=(0.4, 0.0),
        maximum_weights=(0.6, 0.6),
    )
    candidate = EqualWeight().solve(task)
    assert candidate.weights == (0.5, 0.5)


def test_model_run_fixes_context_and_checks_feasibility() -> None:
    solver = SolverRecord("internal-pgd", "1", (("tolerance", 1e-10),), ("quadratic",))
    run = execute_model_run(
        model=MinimumVariance(),
        problem=problem(),
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        code_version="test",
        dataset_fingerprint="sha256:dataset",
        policy_id="ips",
        policy_version=1,
        universe_id="universe",
        universe_version=1,
        parameters=(),
        random_seed=20260820,
        solver=solver,
    )
    assert len(run.run_id) == 64
    assert run.violations == ()
    assert run.dataset_fingerprint == "sha256:dataset"
    registry = ModelRunRegistry()
    registry.append(run)
    registry.append(run)
    assert registry.get(run.run_id) == run
