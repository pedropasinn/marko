from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import asdict, dataclass
from datetime import datetime
from importlib.metadata import PackageNotFoundError, version

from marko.portfolio_lab import (
    PortfolioCandidate,
    PortfolioModel,
    PortfolioProblem,
    ValidatedPortfolioCandidate,
    check_candidate,
    validate_candidate,
)


@dataclass(frozen=True, slots=True)
class SolverRecord:
    solver_id: str
    version: str
    tolerances: tuple[tuple[str, float], ...]
    capabilities: tuple[str, ...]


class SolverRegistry:
    def __init__(self) -> None:
        self._records: dict[str, SolverRecord] = {}

    def register(self, record: SolverRecord) -> None:
        if record.solver_id in self._records and self._records[record.solver_id] != record:
            raise ValueError(f"solver_id já registrado com outro contrato: {record.solver_id}")
        self._records[record.solver_id] = record

    def get(self, solver_id: str) -> SolverRecord:
        try:
            return self._records[solver_id]
        except KeyError as error:
            raise KeyError(f"solver não registrado: {solver_id}") from error


@dataclass(frozen=True, slots=True)
class ModelRun:
    run_id: str
    created_at: datetime
    model_id: str
    code_version: str
    environment_fingerprint: str
    dataset_fingerprint: str
    policy_id: str
    policy_version: int
    universe_id: str
    universe_version: int
    parameters: tuple[tuple[str, str], ...]
    random_seed: int
    solver: SolverRecord
    candidate: PortfolioCandidate
    validated_candidate: ValidatedPortfolioCandidate | None
    violations: tuple[str, ...]


class ModelRunRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, ModelRun] = {}

    def append(self, run: ModelRun) -> None:
        previous = self._runs.get(run.run_id)
        if previous is not None and previous != run:
            raise ValueError(f"run_id conflitante: {run.run_id}")
        self._runs[run.run_id] = run

    def get(self, run_id: str) -> ModelRun:
        try:
            return self._runs[run_id]
        except KeyError as error:
            raise KeyError(f"ModelRun não encontrado: {run_id}") from error

    def all(self) -> tuple[ModelRun, ...]:
        return tuple(sorted(self._runs.values(), key=lambda run: (run.created_at, run.run_id)))


def execute_model_run(
    *,
    model: PortfolioModel,
    problem: PortfolioProblem,
    created_at: datetime,
    code_version: str,
    dataset_fingerprint: str,
    policy_id: str,
    policy_version: int,
    universe_id: str,
    universe_version: int,
    parameters: tuple[tuple[str, str], ...],
    random_seed: int,
    solver: SolverRecord,
) -> ModelRun:
    if created_at.tzinfo is None:
        raise ValueError("created_at precisa de timezone")
    canonical_parameters = tuple(sorted(parameters))
    if len({key for key, _ in canonical_parameters}) != len(canonical_parameters):
        raise ValueError("parâmetros duplicados")
    candidate = model.solve(problem)
    violations = check_candidate(candidate, problem)
    validated = validate_candidate(candidate, problem) if not violations else None
    environment = environment_fingerprint()
    identity = {
        "created_at": created_at.isoformat(),
        "model": candidate.model_id,
        "code": code_version,
        "dataset": dataset_fingerprint,
        "policy": [policy_id, policy_version],
        "universe": [universe_id, universe_version],
        "parameters": canonical_parameters,
        "seed": random_seed,
        "solver": asdict(solver),
        "environment": environment,
        "candidate": asdict(candidate),
    }
    run_id = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    return ModelRun(
        run_id,
        created_at,
        candidate.model_id,
        code_version,
        environment,
        dataset_fingerprint,
        policy_id,
        policy_version,
        universe_id,
        universe_version,
        canonical_parameters,
        random_seed,
        solver,
        candidate,
        validated,
        violations,
    )


def environment_fingerprint() -> str:
    packages = {}
    for name in ("marko", "numpy", "skfolio", "pyportfolioopt"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = "not-installed"
    payload = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packages": packages,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
