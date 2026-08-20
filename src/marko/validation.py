from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from marko.portfolio_lab import (
    PortfolioCandidate,
    PortfolioModel,
    PortfolioProblem,
    validate_candidate,
)


@dataclass(frozen=True, slots=True)
class TemporalSplit:
    train_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


def walk_forward_splits(
    sample_count: int,
    train_size: int,
    test_size: int,
    step: int | None = None,
    purge: int = 0,
) -> tuple[TemporalSplit, ...]:
    if min(sample_count, train_size, test_size) <= 0 or purge < 0:
        raise ValueError("dimensões de split inválidas")
    if step is not None and step <= 0:
        raise ValueError("step precisa ser positivo")
    stride = test_size if step is None else step
    splits = []
    test_start = train_size + purge
    while test_start + test_size <= sample_count:
        train_end = test_start - purge
        train_start = max(0, train_end - train_size)
        splits.append(
            TemporalSplit(
                tuple(range(train_start, train_end)),
                tuple(range(test_start, test_start + test_size)),
            )
        )
        test_start += stride
    return tuple(splits)


def purged_kfold_splits(
    sample_count: int,
    folds: int,
    purge: int = 0,
    embargo: int = 0,
) -> tuple[TemporalSplit, ...]:
    if folds < 2 or folds > sample_count or purge < 0 or embargo < 0:
        raise ValueError("configuração de k-fold inválida")
    blocks = np.array_split(np.arange(sample_count), folds)
    splits = []
    for block in blocks:
        test_start, test_end = int(block[0]), int(block[-1])
        excluded_start = max(0, test_start - purge)
        excluded_end = min(sample_count, test_end + embargo + 1)
        train = tuple(
            index for index in range(sample_count) if not excluded_start <= index < excluded_end
        )
        splits.append(TemporalSplit(train, tuple(int(index) for index in block)))
    return tuple(splits)


@dataclass(frozen=True, slots=True)
class WalkForwardResult:
    model_id: str
    split: int
    gross_return: float
    realized_return: float
    volatility: float
    turnover: float
    estimated_cost: float
    weights: tuple[float, ...]


def evaluate_walk_forward(
    model: PortfolioModel,
    problem: PortfolioProblem,
    splits: tuple[TemporalSplit, ...],
    transaction_cost_bps: float = 0.0,
) -> tuple[WalkForwardResult, ...]:
    if transaction_cost_bps < 0:
        raise ValueError("transaction_cost_bps não pode ser negativo")
    matrix = problem.matrix()
    previous = np.asarray(problem.current_weights) if problem.current_weights else None
    results = []
    for split_index, split in enumerate(splits):
        train = matrix[list(split.train_indices)]
        test = matrix[list(split.test_indices)]
        task = PortfolioProblem(
            problem.assets,
            tuple(tuple(float(value) for value in row) for row in train),
            tuple(previous.tolist()) if previous is not None else (),
            problem.minimum_weights,
            problem.maximum_weights,
        )
        candidate = model.solve(task)
        validate_candidate(candidate, task)
        weights = np.asarray(candidate.weights)
        portfolio_returns = test @ weights
        current_turnover = turnover(previous, weights) if previous is not None else 0.0
        gross_return = float(np.prod(1 + portfolio_returns) - 1)
        estimated_cost = current_turnover * transaction_cost_bps / 10_000
        results.append(
            WalkForwardResult(
                candidate.model_id,
                split_index,
                gross_return,
                gross_return - estimated_cost,
                float(portfolio_returns.std(ddof=1)),
                current_turnover,
                estimated_cost,
                candidate.weights,
            )
        )
        asset_growth = np.prod(1 + test, axis=0)
        drifted = weights * asset_growth
        total = float(drifted.sum())
        if not np.isfinite(total) or total <= 0:
            raise ValueError("pesos após drift são inválidos")
        previous = drifted / total
    return tuple(results)


def turnover(previous: np.ndarray, current: np.ndarray) -> float:
    if previous.shape != current.shape:
        raise ValueError("pesos incompatíveis")
    return float(np.abs(current - previous).sum() / 2)


@dataclass(frozen=True, slots=True)
class StabilityResult:
    mean_l1_distance: float
    maximum_weight_deviation: float
    candidates: int


def weight_stability(candidates: tuple[PortfolioCandidate, ...]) -> StabilityResult:
    if len(candidates) < 2:
        raise ValueError("estabilidade exige ao menos dois candidatos")
    if any(candidate.assets != candidates[0].assets for candidate in candidates[1:]):
        raise ValueError("candidatos precisam usar os mesmos assets e ordem")
    matrix = np.asarray([candidate.weights for candidate in candidates])
    center = matrix.mean(axis=0)
    distances = np.abs(matrix - center).sum(axis=1)
    return StabilityResult(
        float(distances.mean()), float(np.abs(matrix - center).max()), len(candidates)
    )


def perturbation_sensitivity(
    model: PortfolioModel,
    problem: PortfolioProblem,
    noise_scale: float = 0.01,
    repetitions: int = 20,
    seed: int = 20260820,
) -> StabilityResult:
    if noise_scale < 0 or repetitions < 2:
        raise ValueError("configuração de perturbação inválida")
    rng = np.random.default_rng(seed)
    matrix = problem.matrix()
    candidates = []
    for _ in range(repetitions):
        perturbed = matrix * (1 + rng.normal(0, noise_scale, size=matrix.shape))
        task = PortfolioProblem(
            problem.assets,
            tuple(tuple(float(value) for value in row) for row in perturbed),
            problem.current_weights,
            problem.minimum_weights,
            problem.maximum_weights,
        )
        candidates.append(model.solve(task))
    return weight_stability(tuple(candidates))


def stress_return(candidate: PortfolioCandidate, asset_shocks: tuple[float, ...]) -> float:
    if len(candidate.weights) != len(asset_shocks):
        raise ValueError("cenário incompatível")
    return float(np.asarray(candidate.weights) @ np.asarray(asset_shocks))


def stress_volatility(
    candidate: PortfolioCandidate,
    asset_volatilities: tuple[float, ...],
    correlation: float,
) -> float:
    size = len(candidate.weights)
    lower_correlation = -1 / (size - 1) if size > 1 else 0
    if (
        size != len(asset_volatilities)
        or not lower_correlation <= correlation <= 1
        or any(volatility < 0 for volatility in asset_volatilities)
    ):
        raise ValueError("cenário de correlação incompatível")
    volatilities = np.asarray(asset_volatilities)
    covariance = np.outer(volatilities, volatilities) * correlation
    np.fill_diagonal(covariance, volatilities**2)
    weights = np.asarray(candidate.weights)
    eigenvalues = np.linalg.eigvalsh(covariance)
    if eigenvalues.min() < -1e-12:
        raise ValueError("matriz de stress não é positiva semidefinida")
    return float(np.sqrt(max(float(weights @ covariance @ weights), 0.0)))
