from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import numpy as np
import pytest

from marko.activities import Activity, ActivityKind
from marko.decision import (
    CashFlowRebalancer,
    CashTarget,
    Holding,
    TargetAllocation,
    ValidatedModelRunRef,
)
from marko.money import Money
from marko.persistence import (
    SerializationEnvelope,
    UnsupportedSchemaError,
    decode_activity,
    decode_decision_packet,
    decode_model_run,
    decode_observation,
    encode_activity,
    encode_decision_packet,
    encode_model_run,
    encode_observation,
)
from marko.portfolio_lab import MinimumVariance, PortfolioProblem
from marko.research_registry import ModelRun, SolverRecord, execute_model_run
from marko.temporal import Observation, TimeCoordinates

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)


def model_run() -> ModelRun:
    rng = np.random.default_rng(42)
    matrix = rng.normal([0.0002, 0.0004], [0.001, 0.01], size=(80, 2))
    problem = PortfolioProblem(
        ("DEFENSIVE", "RISK"),
        tuple(tuple(float(value) for value in row) for row in matrix),
        current_weights=(0.6, 0.4),
    )
    return execute_model_run(
        model=MinimumVariance(shrinkage=0.1),
        problem=problem,
        created_at=NOW,
        code_version="test",
        dataset_fingerprint="sha256:dataset",
        policy_id="ips",
        policy_version=1,
        universe_id="universe",
        universe_version=1,
        parameters=(("shrinkage", "0.1"),),
        random_seed=42,
        solver=SolverRecord("internal", "1", (("tolerance", 1e-10),), ("quadratic",)),
    )


def test_activity_envelope_is_canonical_versioned_and_round_trips() -> None:
    original = Activity(
        "buy",
        ActivityKind.BUY,
        "broker",
        NOW,
        NOW + timedelta(minutes=1),
        Money.of("100", "BRL"),
        instrument_id="ETF",
        quantity=Decimal("2"),
        fee=Money.of("1", "BRL"),
        tax=Money.of("0.50", "BRL"),
        external_id="broker-1",
    )
    envelope = encode_activity(original)
    restored = decode_activity(SerializationEnvelope.from_json(envelope.canonical_json()))
    assert restored == original
    assert envelope.digest() == SerializationEnvelope.from_json(envelope.canonical_json()).digest()
    with pytest.raises(UnsupportedSchemaError):
        decode_activity(replace(envelope, version=2))
    with pytest.raises(ValueError, match="desconhecidas: unexpected"):
        decode_activity(replace(envelope, payload=envelope.payload | {"unexpected": True}))
    with pytest.raises(ValueError, match="timezone"):
        decode_activity(
            replace(
                envelope,
                payload=envelope.payload | {"effective_at": "2026-08-20T12:00:00"},
            )
        )


def test_observation_round_trip_preserves_four_times_dimensions_and_raw_hash() -> None:
    times = TimeCoordinates(
        NOW,
        NOW + timedelta(minutes=1),
        NOW + timedelta(minutes=2),
        NOW + timedelta(minutes=3),
    )
    observation = Observation(
        "obs",
        "IPCA",
        Decimal("7657.73"),
        "index",
        "IBGE/SIDRA",
        times,
        "vintage",
        "sha256:raw",
        (("territory", "BR"),),
        ("availability_conservative",),
    )
    assert decode_observation(encode_observation(observation)) == observation


def test_model_run_and_decision_packet_round_trip_without_losing_validation() -> None:
    run = model_run()
    restored_run = decode_model_run(encode_model_run(run))
    assert restored_run == run
    assert run.validated_candidate is not None
    packet = CashFlowRebalancer().build_packet(
        packet_id="packet",
        created_at=NOW,
        policy_id="ips",
        policy_version=1,
        holdings=(
            Holding("DEFENSIVE", Money.of("600", "BRL"), Money.of("1", "BRL")),
            Holding("RISK", Money.of("400", "BRL"), Money.of("10", "BRL")),
        ),
        targets=(
            TargetAllocation("DEFENSIVE", Decimal("0.55"), Decimal("0.8")),
            TargetAllocation("RISK", Decimal("0.35"), Decimal("0.7")),
        ),
        cash=Money.zero("BRL"),
        cash_target=CashTarget(Decimal("0.10"), Decimal("0.3")),
        contribution=Money.of("100", "BRL"),
        model_runs=(ValidatedModelRunRef(run.run_id, run.validated_candidate),),
        evidence_ids=("obs",),
    )
    assert decode_decision_packet(encode_decision_packet(packet)) == packet
