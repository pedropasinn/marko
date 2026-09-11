import numpy as np
import pytest

from marko.portfolio_lab import EqualWeight, MinimumVariance, NoAction, PortfolioProblem
from marko.validation import (
    TemporalSplit,
    evaluate_walk_forward,
    perturbation_sensitivity,
    purged_kfold_splits,
    stress_return,
    stress_volatility,
    walk_forward_splits,
)


def sample_problem() -> PortfolioProblem:
    rng = np.random.default_rng(7)
    matrix = rng.normal([0.0002, 0.0004], [0.001, 0.01], size=(120, 2))
    return PortfolioProblem(
        ("DEFENSIVE", "RISK"),
        tuple(tuple(float(value) for value in row) for row in matrix),
        current_weights=(0.6, 0.4),
    )


def test_walk_forward_has_purge_and_no_overlap() -> None:
    splits = walk_forward_splits(120, train_size=60, test_size=20, purge=5)
    assert len(splits) == 2
    assert max(splits[0].train_indices) == 59
    assert min(splits[0].test_indices) == 65
    results = evaluate_walk_forward(
        EqualWeight(), sample_problem(), splits, transaction_cost_bps=10
    )
    assert len(results) == 2
    assert results[0].realized_return == pytest.approx(
        (1 - results[0].estimated_cost) * (1 + results[0].gross_return) - 1
    )


def test_no_action_returns_follow_unchanged_quantities_and_allow_drift() -> None:
    problem = PortfolioProblem(
        ("A", "B"),
        ((0.01, 0.02), (0.02, 0.01), (1.0, 0.0), (-0.5, 0.0)),
        current_weights=(0.5, 0.5),
        maximum_weights=(0.6, 0.6),
    )
    combined = evaluate_walk_forward(NoAction(), problem, (TemporalSplit((0, 1), (2, 3)),))
    assert combined[0].gross_return == pytest.approx(0.0)
    sequential = evaluate_walk_forward(
        NoAction(),
        problem,
        (TemporalSplit((0, 1), (2,)), TemporalSplit((0, 1, 2), (3,))),
        transaction_cost_bps=10,
    )
    assert sequential[0].gross_return == pytest.approx(0.5)
    assert sequential[1].gross_return == pytest.approx(-1 / 3)
    assert sequential[1].violations == ("maximum_weight",)
    assert sequential[1].estimated_cost == pytest.approx(0)
    assert np.prod([1 + row.realized_return for row in sequential]) == pytest.approx(1.0)


def test_rebalance_costs_cover_both_legs_and_reduce_invested_capital() -> None:
    problem = PortfolioProblem(
        ("A", "B"),
        ((0.01, 0.0), (0.0, 0.01), (0.1, 0.1)),
        current_weights=(1.0, 0.0),
    )
    result = evaluate_walk_forward(
        EqualWeight(),
        problem,
        (TemporalSplit((0, 1), (2,)),),
        transaction_cost_bps=100,
    )[0]
    assert result.estimated_cost == pytest.approx(0.01)
    assert result.realized_return == pytest.approx(0.089)
    assert result.volatility == 0


@pytest.mark.parametrize(
    "splits",
    [
        (TemporalSplit((3, 4), (2,)),),
        (TemporalSplit((0, 1, 2), (2,)),),
        (TemporalSplit((0, 0), (2,)),),
        (TemporalSplit((-1, 0), (2,)),),
        (TemporalSplit((0, 1), (120,)),),
        (TemporalSplit((0, 1), (2, 3)), TemporalSplit((0, 1), (3, 4))),
        (TemporalSplit((0, 1), (2,)), TemporalSplit((0, 1), (4,))),
    ],
)
def test_walk_forward_rejects_invalid_temporal_order(splits: tuple[TemporalSplit, ...]) -> None:
    with pytest.raises(ValueError):
        evaluate_walk_forward(EqualWeight(), sample_problem(), splits)


@pytest.mark.parametrize("step", [0, -1])
def test_walk_forward_rejects_non_positive_step(step: int) -> None:
    with pytest.raises(ValueError, match="step"):
        walk_forward_splits(120, 60, 20, step=step)


def test_purged_kfold_removes_neighbours_and_embargo() -> None:
    splits = purged_kfold_splits(20, folds=4, purge=2, embargo=2)
    first = splits[0]
    assert first.test_indices == (0, 1, 2, 3, 4)
    assert min(first.train_indices) == 7
    middle = splits[2]
    assert 8 not in middle.train_indices
    assert 16 not in middle.train_indices


def test_sensitivity_and_stress_are_explicit() -> None:
    stability = perturbation_sensitivity(
        MinimumVariance(shrinkage=0.2), sample_problem(), repetitions=3
    )
    assert stability.candidates == 3
    candidate = EqualWeight().solve(sample_problem())
    assert stress_return(candidate, (-0.01, -0.30)) == pytest.approx(-0.155)
    assert stress_volatility(candidate, (0.01, 0.20), 1.0) == pytest.approx(0.105)
    with pytest.raises(ValueError, match="correlação"):
        stress_volatility(candidate, (0.01, 0.20), -1.01)
