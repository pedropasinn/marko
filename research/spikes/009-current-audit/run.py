"""Auditoria sintética; não consulta provedores nem grava no ledger."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import subprocess
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

import numpy as np

from marko.decision import (
    CashFlowRebalancer,
    CashTarget,
    Holding,
    TargetAllocation,
    ValidatedModelRunRef,
)
from marko.money import Money
from marko.portfolio_lab import (
    MinimumVariance,
    NoAction,
    PortfolioCandidate,
    PortfolioProblem,
    SkfolioMinimumVarianceAdapter,
    validate_candidate,
)
from marko.research_registry import SolverRecord, execute_model_run
from marko.validation import TemporalSplit, evaluate_walk_forward

ROOT = Path(__file__).resolve().parents[3]
REFERENCES = ROOT.parent / "marko-references"


def git_head(path: Path) -> str:
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()


def error_from(call):
    try:
        call()
    except (ValueError, RuntimeError) as error:
        return f"{type(error).__name__}: {error}"
    return None


def audit():
    problem = PortfolioProblem(
        ("A", "B"),
        ((0.01, 0.0), (0.0, 0.01), (1.0, 0.0), (-0.5, 0.0)),
        current_weights=(0.5, 0.5),
    )
    result = evaluate_walk_forward(NoAction(), problem, (TemporalSplit((0, 1), (2, 3)),))[0]
    failed = PortfolioCandidate("failed", problem.assets, (0.5, 0.5), 0.0, 0.1, "infeasible")
    drift = PortfolioProblem(
        ("A", "B"),
        ((0.01, 0.0), (0.0, 0.01), (1.0, 0.0), (0.0, 0.0), (0.01, 0.01), (0.0, 0.01)),
        current_weights=(0.5, 0.5),
        maximum_weights=(0.6, 0.6),
    )
    findings = {
        "no_action": {
            "reported_return": result.gross_return,
            "buy_and_hold_return": float(
                np.prod(1 + problem.matrix()[[2, 3]], axis=0) @ np.array([0.5, 0.5]) - 1
            ),
            "reported_turnover": result.turnover,
        },
        "infeasible_solver_accepted": (
            error_from(lambda: validate_candidate(failed, problem)) is None
        ),
        "future_training_accepted": error_from(
            lambda: evaluate_walk_forward(NoAction(), problem, (TemporalSplit((2, 3), (0, 1)),))
        )
        is None,
        "drift_above_bound": error_from(
            lambda: evaluate_walk_forward(
                NoAction(),
                drift,
                (TemporalSplit((0, 1), (2, 3)), TemporalSplit((2, 3), (4, 5))),
            )
        ),
        "single_asset": error_from(
            lambda: MinimumVariance().solve(PortfolioProblem(("A",), ((0.01,), (0.02,))))
        ),
    }

    # Isola a função pura real do upstream, sem instalar ou iniciar agentes/LLMs.
    source = REFERENCES / "TradingAgents/tradingagents/dataflows/alpha_vantage_fundamentals.py"
    node = next(
        node
        for node in ast.parse(source.read_text()).body
        if isinstance(node, ast.FunctionDef) and node.name == "_filter_reports_by_date"
    )
    namespace = {"json": json}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), namespace)
    report = {"fiscalDateEnding": "2024-03-31", "reportedDate": "2024-05-01"}
    filtered = namespace["_filter_reports_by_date"](
        json.dumps({"quarterlyReports": [report]}), "2024-04-01"
    )
    findings["tradingagents_unpublished_report_accepted"] = bool(
        json.loads(filtered)["quarterlyReports"]
    )

    import skfolio
    from skfolio import RiskMeasure
    from skfolio.optimization import HierarchicalRiskParity, MeanRisk, ObjectiveFunction
    from skfolio.optimization import RiskBudgeting as UpstreamRiskBudgeting

    matrix = np.random.default_rng(42).normal(
        [0.0003, 0.0004, 0.0005], [0.004, 0.012, 0.018], size=(252, 3)
    )
    dataset_hash = hashlib.sha256(matrix.tobytes()).hexdigest()
    task = PortfolioProblem(
        ("SYNTH_A", "SYNTH_B", "SYNTH_C"),
        tuple(map(tuple, matrix)),
        current_weights=(0.5, 0.2, 0.3),
        maximum_weights=(0.8, 0.8, 0.8),
    )
    run = execute_model_run(
        model=SkfolioMinimumVarianceAdapter(),
        problem=task,
        created_at=datetime(2026, 9, 11, tzinfo=UTC),
        code_version=git_head(ROOT),
        dataset_fingerprint=dataset_hash,
        policy_id="synthetic-audit",
        policy_version=1,
        universe_id="synthetic-audit",
        universe_version=1,
        parameters=(),
        random_seed=42,
        solver=SolverRecord("CLARABEL", version("clarabel"), (), ("quadratic",)),
    )
    models = {
        "minvar_adapter": run.candidate.weight_map(),
        "risk_budgeting": dict(
            zip(
                task.assets,
                UpstreamRiskBudgeting(max_weights=0.8).fit(matrix).weights_,
                strict=True,
            )
        ),
        "hrp": dict(
            zip(
                task.assets,
                HierarchicalRiskParity(max_weights=0.8).fit(matrix).weights_,
                strict=True,
            )
        ),
        "cvar": dict(
            zip(
                task.assets,
                MeanRisk(
                    objective_function=ObjectiveFunction.MINIMIZE_RISK,
                    risk_measure=RiskMeasure.CVAR,
                    max_weights=0.8,
                )
                .fit(matrix)
                .weights_,
                strict=True,
            )
        ),
    }
    weights = [Decimal(str(weight)) for weight in run.candidate.weights]
    weights[-1] = Decimal(1) - sum(weights[:-1])
    holdings = tuple(
        Holding(asset, Money.of(value, "BRL"), Money.of("1", "BRL"))
        for asset, value in zip(task.assets, ("25000", "10000", "15000"), strict=True)
    )
    targets = tuple(
        TargetAllocation(asset, weight, Decimal("0.8"))
        for asset, weight in zip(task.assets, weights, strict=True)
    )

    def packet(cost, selected_targets=targets, policy_id="synthetic-audit"):
        return CashFlowRebalancer(Decimal(cost)).build_packet(
            packet_id=f"synthetic-{cost}",
            created_at=run.created_at,
            policy_id=policy_id,
            policy_version=1,
            holdings=holdings,
            targets=selected_targets,
            cash=Money.zero("BRL"),
            cash_target=CashTarget(Decimal(0), Decimal(1)),
            contribution=Money.of("2000", "BRL"),
            model_runs=(ValidatedModelRunRef.from_model_run(run),),
        )

    mismatch = tuple(
        TargetAllocation(asset, weight, Decimal("0.8"))
        for asset, weight in zip(
            task.assets, (Decimal("0.2"), Decimal("0.4"), Decimal("0.4")), strict=True
        )
    )
    findings["different_policy_and_targets_accepted"] = (
        error_from(lambda: packet("0", mismatch, "another-policy")) is None
    )
    return {
        "synthetic": True,
        "seed": 42,
        "observations": 252,
        "dataset_sha256": dataset_hash,
        "marko_commit": git_head(ROOT),
        "skfolio_source": skfolio.__file__,
        "skfolio_reference_commit": git_head(REFERENCES / "skfolio"),
        "tradingagents_commit": git_head(REFERENCES / "TradingAgents"),
        "installed_distributions": {
            name: version(name)
            for name in (
                "skfolio",
                "PyPortfolioOpt",
                "numpy",
                "scipy",
                "scikit-learn",
                "cvxpy",
                "clarabel",
            )
        },
        "findings": findings,
        "model_weights": models,
        "contribution_simulation": {
            "initial_brl": "50000",
            "contribution_brl": "2000",
            "zero_cost": asdict(packet("0")),
            "five_bps": asdict(packet("5")),
        },
        "limitations": [
            "Um ciclo sintético; não mede rentabilidade nem valida estratégia.",
            "Código skfolio pode vir de PYTHONPATH; metadados instalados não mudam.",
            "Não executa o grafo TradingAgents nem reproduz resultados do paper.",
        ],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(audit(), indent=2, default=str, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")
