from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class PortfolioProblem:
    assets: tuple[str, ...]
    returns: tuple[tuple[float, ...], ...]
    current_weights: tuple[float, ...] = ()
    minimum_weights: tuple[float, ...] = ()
    maximum_weights: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.assets or len(set(self.assets)) != len(self.assets):
            raise ValueError("assets precisam ser únicos e não vazios")
        matrix = self.matrix()
        if matrix.ndim != 2 or matrix.shape[1] != len(self.assets) or matrix.shape[0] < 2:
            raise ValueError("matriz de retornos incompatível")
        if not np.isfinite(matrix).all():
            raise ValueError("retornos precisam ser finitos")
        for vector in (self.current_weights, self.minimum_weights, self.maximum_weights):
            if vector and len(vector) != len(self.assets):
                raise ValueError("vetor de pesos incompatível")
            if vector and not np.isfinite(np.asarray(vector)).all():
                raise ValueError("vetor de pesos precisa ser finito")
        lower, upper = self.bounds()
        if np.any(lower > upper) or lower.sum() > 1 + 1e-12 or upper.sum() < 1 - 1e-12:
            raise ValueError("bounds inviáveis")
        if self.current_weights:
            current = np.asarray(self.current_weights)
            if abs(float(current.sum()) - 1) > 1e-7:
                raise ValueError("pesos atuais precisam somar um")
            if np.any(current < lower - 1e-7) or np.any(current > upper + 1e-7):
                raise ValueError("pesos atuais violam bounds")

    def matrix(self) -> npt.NDArray[np.float64]:
        return np.asarray(self.returns, dtype=float)

    def bounds(self) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64]]:
        size = len(self.assets)
        lower = np.asarray(self.minimum_weights or (0.0,) * size, dtype=float)
        upper = np.asarray(self.maximum_weights or (1.0,) * size, dtype=float)
        return lower, upper


@dataclass(frozen=True, slots=True)
class PortfolioCandidate:
    model_id: str
    assets: tuple[str, ...]
    weights: tuple[float, ...]
    expected_return: float
    volatility: float
    solver_status: str
    diagnostics: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if (
            not self.model_id.strip()
            or not self.assets
            or len(set(self.assets)) != len(self.assets)
        ):
            raise ValueError("candidato exige modelo e assets únicos")
        if len(self.assets) != len(self.weights):
            raise ValueError("assets e weights incompatíveis")
        values = (*self.weights, self.expected_return, self.volatility)
        if not all(isfinite(value) for value in values):
            raise ValueError("candidato contém valor não finito")
        if self.volatility < 0:
            raise ValueError("volatilidade não pode ser negativa")
        if not self.solver_status.strip():
            raise ValueError("solver_status é obrigatório")

    def weight_map(self) -> dict[str, float]:
        return dict(zip(self.assets, self.weights, strict=True))


class PortfolioModel(Protocol):
    model_id: str

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate: ...


@dataclass(frozen=True, slots=True)
class ValidatedPortfolioCandidate:
    candidate: PortfolioCandidate
    problem: PortfolioProblem

    def __post_init__(self) -> None:
        violations = check_candidate(self.candidate, self.problem)
        if violations:
            raise ValueError("candidato rejeitado: " + ", ".join(violations))


class NoAction:
    model_id = "no_action"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        if not problem.current_weights:
            raise ValueError("NO_ACTION exige pesos atuais")
        return _candidate(self.model_id, problem, np.asarray(problem.current_weights), "not_solved")


class EqualWeight:
    model_id = "equal_weight"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        lower, upper = problem.bounds()
        weights = _bounded_simplex(
            np.repeat(1 / len(problem.assets), len(problem.assets)), lower, upper
        )
        return _candidate(self.model_id, problem, weights, "closed_form")


class InverseVolatility:
    model_id = "inverse_volatility"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        volatility = problem.matrix().std(axis=0, ddof=1)
        if np.any(volatility <= 0):
            raise ValueError("inverse volatility exige volatilidades positivas")
        raw = 1 / volatility
        lower, upper = problem.bounds()
        weights = _bounded_simplex(raw / raw.sum(), lower, upper)
        return _candidate(self.model_id, problem, weights, "closed_form")


class MinimumVariance:
    model_id = "minimum_variance"

    def __init__(self, shrinkage: float = 0.0, tolerance: float = 1e-10) -> None:
        if not 0 <= shrinkage <= 1:
            raise ValueError("shrinkage precisa estar entre zero e um")
        self.shrinkage = shrinkage
        self.tolerance = tolerance

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        covariance = np.cov(problem.matrix(), rowvar=False, ddof=1)
        covariance = (1 - self.shrinkage) * covariance + self.shrinkage * np.diag(
            np.diag(covariance)
        )
        lower, upper = problem.bounds()
        weights = _bounded_simplex(
            np.repeat(1 / len(problem.assets), len(problem.assets)), lower, upper
        )
        lipschitz = max(2 * float(np.linalg.eigvalsh(covariance).max()), 1e-12)
        status = "max_iterations"
        for _ in range(20_000):
            updated = _bounded_simplex(
                weights - (2 * covariance @ weights) / lipschitz, lower, upper
            )
            if np.max(np.abs(updated - weights)) <= self.tolerance:
                weights = updated
                status = "converged"
                break
            weights = updated
        return _candidate(
            self.model_id,
            problem,
            weights,
            status,
            (("shrinkage", str(self.shrinkage)),),
        )


class RiskBudgeting:
    model_id = "risk_budgeting"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        covariance = np.cov(problem.matrix(), rowvar=False, ddof=1)
        lower, upper = problem.bounds()
        weights = InverseVolatility().solve(problem).weights
        vector = np.asarray(weights)
        target = np.repeat(1 / len(vector), len(vector))
        status = "max_iterations"
        for _ in range(10_000):
            marginal = covariance @ vector
            variance = float(vector @ marginal)
            contribution = vector * marginal / variance
            if np.any(contribution <= 0):
                raise ValueError("risk budgeting encontrou contribuição não positiva")
            updated = _bounded_simplex(vector * np.sqrt(target / contribution), lower, upper)
            if np.max(np.abs(updated - vector)) <= 1e-9:
                vector = updated
                status = "converged"
                break
            vector = updated
        return _candidate(self.model_id, problem, vector, status)


class SkfolioMinimumVarianceAdapter:
    model_id = "skfolio_minimum_variance"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        try:
            from skfolio import RiskMeasure
            from skfolio.optimization import (
                MeanRisk,
                ObjectiveFunction,
            )
        except ImportError as error:
            raise RuntimeError("instale o extra de pesquisa skfolio") from error
        lower, upper = problem.bounds()
        model = MeanRisk(
            objective_function=ObjectiveFunction.MINIMIZE_RISK,
            risk_measure=RiskMeasure.VARIANCE,
            min_weights=lower,
            max_weights=upper,
        ).fit(problem.matrix())
        return _candidate(self.model_id, problem, np.asarray(model.weights_), "upstream")


class PyPortfolioOptMinimumVarianceAdapter:
    model_id = "pypfopt_minimum_variance"

    def solve(self, problem: PortfolioProblem) -> PortfolioCandidate:
        try:
            from pypfopt import EfficientFrontier
        except ImportError as error:
            raise RuntimeError("instale o extra de pesquisa PyPortfolioOpt") from error
        lower, upper = problem.bounds()
        bounds = list(zip(lower.tolist(), upper.tolist(), strict=True))
        matrix = problem.matrix()
        frontier = EfficientFrontier(matrix.mean(axis=0), np.cov(matrix, rowvar=False), bounds)
        frontier.min_volatility()
        return _candidate(self.model_id, problem, np.asarray(frontier.weights), "upstream")


def check_candidate(
    candidate: PortfolioCandidate,
    problem: PortfolioProblem,
    tolerance: float = 1e-7,
) -> tuple[str, ...]:
    weights = np.asarray(candidate.weights)
    lower, upper = problem.bounds()
    violations = []
    if candidate.assets != problem.assets:
        violations.append("asset_order")
    if len(candidate.weights) != len(problem.assets):
        return tuple((*violations, "weight_dimension"))
    if not np.isfinite(weights).all():
        violations.append("non_finite_weights")
    if abs(float(weights.sum()) - 1) > tolerance:
        violations.append("weights_do_not_sum_to_one")
    if np.any(weights < lower - tolerance):
        violations.append("minimum_weight")
    if np.any(weights > upper + tolerance):
        violations.append("maximum_weight")
    return tuple(violations)


def validate_candidate(
    candidate: PortfolioCandidate,
    problem: PortfolioProblem,
    tolerance: float = 1e-7,
) -> ValidatedPortfolioCandidate:
    violations = check_candidate(candidate, problem, tolerance)
    if violations:
        raise ValueError("candidato rejeitado: " + ", ".join(violations))
    return ValidatedPortfolioCandidate(candidate, problem)


def _candidate(
    model_id: str,
    problem: PortfolioProblem,
    weights: npt.NDArray[np.float64],
    status: str,
    diagnostics: tuple[tuple[str, str], ...] = (),
) -> PortfolioCandidate:
    matrix = problem.matrix()
    expected_return = float(matrix.mean(axis=0) @ weights)
    volatility = float(np.sqrt(weights @ np.cov(matrix, rowvar=False, ddof=1) @ weights))
    return PortfolioCandidate(
        model_id,
        problem.assets,
        tuple(float(value) for value in weights),
        expected_return,
        volatility,
        status,
        diagnostics,
    )


def _bounded_simplex(
    values: npt.NDArray[np.float64],
    lower: npt.NDArray[np.float64],
    upper: npt.NDArray[np.float64],
) -> npt.NDArray[np.float64]:
    low = float(np.min(values - upper))
    high = float(np.max(values - lower))
    for _ in range(100):
        threshold = (low + high) / 2
        projected = np.clip(values - threshold, lower, upper)
        if projected.sum() > 1:
            low = threshold
        else:
            high = threshold
    return np.clip(values - (low + high) / 2, lower, upper)
