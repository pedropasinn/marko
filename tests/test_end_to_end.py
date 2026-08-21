from datetime import UTC, datetime
from decimal import Decimal

import numpy as np

from marko.decision import (
    CashFlowRebalancer,
    CashTarget,
    Holding,
    TargetAllocation,
    ValidatedModelRunRef,
)
from marko.money import Money
from marko.portfolio_lab import MinimumVariance, PortfolioProblem
from marko.research_registry import SolverRecord, execute_model_run


def test_research_result_becomes_auditable_cash_flow_draft() -> None:
    rng = np.random.default_rng(20260820)
    matrix = rng.normal([0.0003, 0.0004, 0.0005], [0.001, 0.006, 0.01], size=(180, 3))
    problem = PortfolioProblem(
        ("CDI", "IPCA", "GLOBAL"),
        tuple(tuple(float(value) for value in row) for row in matrix),
        current_weights=(0.5, 0.2, 0.3),
        maximum_weights=(0.8, 0.5, 0.6),
    )
    run = execute_model_run(
        model=MinimumVariance(shrinkage=0.2),
        problem=problem,
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        code_version="test",
        dataset_fingerprint="sha256:synthetic",
        policy_id="personal-ips",
        policy_version=1,
        universe_id="personal",
        universe_version=1,
        parameters=(("shrinkage", "0.2"),),
        random_seed=20260820,
        solver=SolverRecord("internal-pgd", "1", (("tolerance", 1e-10),), ("quadratic",)),
    )
    raw = [Decimal(str(weight)) for weight in run.candidate.weights]
    normalized = (raw[0], raw[1], Decimal(1) - raw[0] - raw[1])
    targets = tuple(
        TargetAllocation(asset, weight, maximum)
        for asset, weight, maximum in zip(
            problem.assets,
            normalized,
            (Decimal("0.8"), Decimal("0.5"), Decimal("0.6")),
            strict=True,
        )
    )
    holdings = (
        Holding("CDI", Money.of("25000", "BRL"), Money.of("1", "BRL")),
        Holding("IPCA", Money.of("10000", "BRL"), Money.of("10", "BRL")),
        Holding("GLOBAL", Money.of("15000", "BRL"), Money.of("100", "BRL"), True),
    )
    assert run.validated_candidate is not None
    packet = CashFlowRebalancer(Decimal("5")).build_packet(
        packet_id="packet-1",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        policy_id="personal-ips",
        policy_version=1,
        holdings=holdings,
        targets=targets,
        cash=Money.zero("BRL"),
        cash_target=CashTarget(Decimal(0), Decimal(1)),
        contribution=Money.of("2000", "BRL"),
        model_runs=(ValidatedModelRunRef.from_model_run(run),),
    )
    assert packet.model_run_ids == (run.run_id,)
    assert {alternative.alternative_id for alternative in packet.alternatives} == {
        "no_action",
        "cash_flow_only",
    }
