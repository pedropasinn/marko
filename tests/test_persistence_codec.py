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
    decode_shadow_run_request,
    encode_activity,
    encode_decision_packet,
    encode_model_run,
    encode_observation,
    encode_shadow_run_request,
)
from marko.persistence.codec import JsonValue
from marko.portfolio_lab import MinimumVariance, PortfolioProblem
from marko.research_registry import ModelRun, SolverRecord, execute_model_run
from marko.shadow import ShadowRunRequest
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


def test_codec_rejects_unknown_nested_fields_and_duplicate_json_keys() -> None:
    activity = Activity(
        "deposit",
        ActivityKind.DEPOSIT,
        "broker",
        NOW,
        NOW,
        Money.of("10", "BRL"),
    )
    envelope = encode_activity(activity)
    gross_amount = envelope.payload["gross_amount"]
    assert isinstance(gross_amount, dict)
    tampered = replace(
        envelope,
        payload=envelope.payload | {"gross_amount": gross_amount | {"unexpected": "not-allowed"}},
    )
    with pytest.raises(ValueError, match="desconhecidas: unexpected"):
        decode_activity(tampered)

    raw = envelope.canonical_json().replace(
        '"schema":"marko.activity"',
        '"schema":"marko.activity","schema":"marko.activity"',
    )
    with pytest.raises(ValueError, match="chave JSON duplicada: schema"):
        SerializationEnvelope.from_json(raw)


def test_model_run_revalidates_semantics_and_cryptographic_identity() -> None:
    envelope = encode_model_run(model_run())
    with pytest.raises(ValueError, match="run_id diverge"):
        decode_model_run(replace(envelope, payload=envelope.payload | {"run_id": "0" * 64}))
    candidate = envelope.payload["candidate"]
    assert isinstance(candidate, dict)
    with pytest.raises(ValueError, match="model_id diverge"):
        decode_model_run(
            replace(
                envelope,
                payload=envelope.payload | {"candidate": candidate | {"model_id": "outro-modelo"}},
            )
        )

    non_finite = envelope.canonical_json().replace(
        '"expected_return":',
        '"ignored":NaN,"expected_return":',
        1,
    )
    with pytest.raises(ValueError, match="constante JSON inválida"):
        SerializationEnvelope.from_json(non_finite)


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
    request = ShadowRunRequest.create("monthly", NOW, NOW - timedelta(minutes=1))
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
        model_runs=(
            ValidatedModelRunRef.from_model_run(
                run,
                dataset_available_at=request.knowledge_cutoff,
            ),
        ),
        evidence_ids=("obs",),
        shadow_request_id=request.request_id,
        knowledge_cutoff=request.knowledge_cutoff,
    )
    envelope = encode_decision_packet(packet)
    assert envelope.version == 3
    references = envelope.payload["model_runs"]
    assert isinstance(references, list)
    encoded_reference = references[0]
    assert isinstance(encoded_reference, dict)
    assert set(encoded_reference) == {
        "run_id",
        "run_payload_hash",
        "dataset_fingerprint",
        "candidate_hash",
        "validation_witness",
        "dataset_available_at",
    }
    assert "returns" not in envelope.canonical_json()
    assert "problem" not in envelope.canonical_json()
    restored_packet = decode_decision_packet(envelope)
    assert restored_packet == packet
    assert restored_packet.model_runs[0].reconciles_with(run)
    assert restored_packet.model_runs[0].run_payload_hash == encode_model_run(run).digest()
    assert restored_packet.knowledge_cutoff == request.knowledge_cutoff
    assert restored_packet.model_runs[0].dataset_fingerprint == run.dataset_fingerprint
    assert restored_packet.model_runs[0].dataset_available_at == request.knowledge_cutoff

    request_envelope = encode_shadow_run_request(request)
    assert decode_shadow_run_request(request_envelope) == request


@pytest.mark.parametrize("legacy_version", [1, 2])
def test_legacy_decision_packets_remain_readable_without_retaining_returns(
    legacy_version: int,
) -> None:
    run = model_run()
    assert run.validated_candidate is not None
    request = ShadowRunRequest.create("legacy", NOW)
    packet = CashFlowRebalancer().build_packet(
        packet_id="legacy-packet",
        created_at=NOW,
        policy_id="ips",
        policy_version=1,
        holdings=(Holding("ASSET", Money.of("100", "BRL"), Money.of("1", "BRL")),),
        targets=(TargetAllocation("ASSET", Decimal("0.9"), Decimal("1")),),
        cash=Money.zero("BRL"),
        cash_target=CashTarget(Decimal("0.1"), Decimal("1")),
        contribution=Money.of("10", "BRL"),
        model_runs=(
            ValidatedModelRunRef.from_model_run(
                run,
                dataset_available_at=request.knowledge_cutoff,
            ),
        ),
        shadow_request_id=request.request_id,
        knowledge_cutoff=request.knowledge_cutoff,
    )
    current = encode_decision_packet(packet)
    payload = dict(current.payload)
    encoded_run = encode_model_run(run).payload
    candidate = encoded_run["validated_candidate"]
    assert isinstance(candidate, dict)
    legacy_reference: dict[str, JsonValue] = {
        "run_id": run.run_id,
        "candidate": candidate,
    }
    if legacy_version == 1:
        del payload["shadow_request_id"]
        del payload["knowledge_cutoff"]
    else:
        legacy_reference |= {
            "dataset_fingerprint": run.dataset_fingerprint,
            "dataset_available_at": request.knowledge_cutoff.isoformat(),
        }
    payload["model_runs"] = [legacy_reference]

    restored = decode_decision_packet(replace(current, version=legacy_version, payload=payload))
    reference = restored.model_runs[0]
    assert reference.run_id == run.run_id
    assert reference.run_payload_hash is None
    assert reference.candidate_hash == packet.model_runs[0].candidate_hash
    assert reference.validation_witness == packet.model_runs[0].validation_witness
    assert not hasattr(reference, "candidate")
    assert reference.reconciles_with(run)


@pytest.mark.parametrize(
    ("field", "tampered_value"),
    [
        ("run_id", "0" * 64),
        ("run_payload_hash", "0" * 64),
        ("dataset_fingerprint", "sha256:other-dataset"),
        ("candidate_hash", "0" * 64),
        ("validation_witness", "0" * 64),
    ],
)
def test_decision_packet_ref_rejects_unknown_fields_and_detects_tampering(
    field: str,
    tampered_value: str,
) -> None:
    run = model_run()
    reference = ValidatedModelRunRef.from_model_run(run, dataset_available_at=NOW)
    packet = CashFlowRebalancer().build_packet(
        packet_id="tamper-check",
        created_at=NOW,
        policy_id="ips",
        policy_version=1,
        holdings=(Holding("ASSET", Money.of("100", "BRL"), Money.of("1", "BRL")),),
        targets=(TargetAllocation("ASSET", Decimal("0.9"), Decimal("1")),),
        cash=Money.zero("BRL"),
        cash_target=CashTarget(Decimal("0.1"), Decimal("1")),
        contribution=Money.of("10", "BRL"),
        model_runs=(reference,),
    )
    envelope = encode_decision_packet(packet)
    raw_references = envelope.payload["model_runs"]
    assert isinstance(raw_references, list)
    raw_reference = raw_references[0]
    assert isinstance(raw_reference, dict)

    with pytest.raises(UnsupportedSchemaError, match="@1, @2 ou @3"):
        decode_decision_packet(replace(envelope, version=4))
    with pytest.raises(ValueError, match="desconhecidas: unexpected"):
        decode_decision_packet(
            replace(
                envelope,
                payload=envelope.payload | {"model_runs": [raw_reference | {"unexpected": True}]},
            )
        )
    with pytest.raises(ValueError, match="SHA-256"):
        decode_decision_packet(
            replace(
                envelope,
                payload=envelope.payload
                | {"model_runs": [raw_reference | {"candidate_hash": "invalid"}]},
            )
        )

    tampered = decode_decision_packet(
        replace(
            envelope,
            payload=envelope.payload | {"model_runs": [raw_reference | {field: tampered_value}]},
        )
    )
    assert not tampered.model_runs[0].reconciles_with(run)


def test_model_run_ref_requires_a_validated_run() -> None:
    run = model_run()
    with pytest.raises(ValueError, match="ModelRun validado"):
        ValidatedModelRunRef.from_model_run(replace(run, validated_candidate=None))

    updated = ValidatedModelRunRef.from_model_run(run).with_dataset_available_at(
        NOW + timedelta(minutes=1)
    )
    assert updated.dataset_available_at == NOW + timedelta(minutes=1)
    assert updated.reconciles_with(run)


def test_shadow_request_rejects_noncanonical_identity() -> None:
    request = ShadowRunRequest.create("monthly", NOW)
    envelope = encode_shadow_run_request(request)

    with pytest.raises(ValueError, match="request_id diverge"):
        decode_shadow_run_request(
            replace(envelope, payload=envelope.payload | {"request_id": "wrong"})
        )
