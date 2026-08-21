from __future__ import annotations

import json
import os
from base64 import b64encode
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import numpy as np
import pytest
from test_persistence import MemoryStore

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
    PersistenceConflictError,
    PersistenceIntegrityError,
    PostgresStore,
    ShadowCycleEnvelope,
    ShadowPostgresStore,
    create_backup,
    decode_shadow_cycle_record,
    encode_shadow_cycle_record,
    restore_backup,
    verify_backup,
)
from marko.portfolio_lab import MinimumVariance, PortfolioProblem
from marko.research_registry import SolverRecord, execute_model_run
from marko.shadow import ShadowRunRequest, reconcile_shadow_packet
from marko.shadow_operation import ShadowCycleJournal, ShadowCycleRecord, ShadowCycleState
from marko.snapshots import PortfolioSnapshot
from marko.temporal import DataVintage, Observation, TimeCoordinates

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)


def test_shadow_cycle_envelope_round_trips_references_and_integrity() -> None:
    record = _current_cycle_record()
    envelope = encode_shadow_cycle_record(record)

    assert '"returns"' not in envelope.canonical_json()
    assert '"problem"' not in envelope.canonical_json()
    assert record.model_runs[0].run_id in envelope.canonical_json()
    assert len(envelope.payload["model_run_refs"]) == 1
    restored = decode_shadow_cycle_record(
        ShadowCycleEnvelope.from_json(envelope.canonical_json()),
        request=record.request,
        model_runs=record.model_runs,
        decision_packet=record.decision_packet,
    )
    assert restored == record


def test_shadow_cycle_read_revalidates_journal_and_reconciliation() -> None:
    record = _current_cycle_record()
    envelope = encode_shadow_cycle_record(record)
    document = json.loads(envelope.canonical_json())
    document["payload"]["journal"]["events"][-1]["content_hash"] = "0" * 64
    tampered = ShadowCycleEnvelope.from_json(json.dumps(document))

    with pytest.raises(ValueError, match="content_hash"):
        decode_shadow_cycle_record(
            tampered,
            request=record.request,
            model_runs=record.model_runs,
            decision_packet=record.decision_packet,
        )


def test_backup_round_trips_shadow_cycle_and_is_idempotent(tmp_path: Path) -> None:
    record = _current_cycle_record()
    source = _store_with_cycle(record)
    backup = tmp_path / "shadow-cycle-backup.json"

    manifest = create_backup(backup, source)

    assert manifest.shadow_cycle_records == 1
    assert verify_backup(backup) == manifest
    document = json.loads(backup.read_text(encoding="utf-8"))
    assert document["metadata"]["version"] == 4
    assert document["metadata"]["schemas"]["shadow_cycle_records"] == (
        "marko.shadow_cycle_record@1"
    )
    encoded_cycle = json.dumps(document["collections"]["shadow_cycle_records"][0])
    assert '"returns"' not in encoded_cycle
    assert '"problem"' not in encoded_cycle

    restored = MemoryStore()
    assert restore_backup(backup, restored) == manifest
    assert restore_backup(backup, restored) == manifest
    assert restored.shadow_cycle_records() == (record,)

    encrypted_backup = tmp_path / "shadow-cycle-private.json"
    encryption_key = b64encode(b"s" * 32).decode("ascii")
    encrypted_manifest = create_backup(
        encrypted_backup,
        source,
        encryption_key=encryption_key,
        key_id="shadow-cycle-test",
    )
    encrypted_restored = MemoryStore()
    assert encrypted_manifest.format_version == 4
    restore_backup(
        encrypted_backup,
        encrypted_restored,
        encryption_key=encryption_key,
    )
    assert encrypted_restored.shadow_cycle_records() == (record,)


@pytest.mark.parametrize("tampering", ["missing_request", "reference_hash"])
def test_backup_rejects_shadow_cycle_with_missing_or_tampered_reference(
    tmp_path: Path,
    tampering: str,
) -> None:
    record = _current_cycle_record()
    backup = tmp_path / f"shadow-cycle-{tampering}.json"
    create_backup(backup, _store_with_cycle(record))
    document = json.loads(backup.read_text(encoding="utf-8"))
    cycle = document["collections"]["shadow_cycle_records"][0]["payload"]
    if tampering == "missing_request":
        cycle["request_ref"]["request_id"] = "missing-request"
    else:
        cycle["model_run_refs"][0]["content_hash"] = "0" * 64
    collections = document["collections"]
    canonical = json.dumps(
        collections,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    document["content_hash"] = sha256(canonical.encode()).hexdigest()
    backup.write_text(json.dumps(document), encoding="utf-8")
    destination = MemoryStore()

    with pytest.raises(PersistenceIntegrityError, match="conteúdo semântico"):
        restore_backup(backup, destination)
    assert destination.activities() == ()
    assert destination.shadow_cycle_records() == ()


@pytest.mark.persistence
def test_postgres_shadow_cycle_is_idempotent_and_rejects_conflict() -> None:
    dsn = os.environ.get("MARKO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("MARKO_TEST_POSTGRES_DSN ausente")
    record = _current_cycle_record()
    core = PostgresStore(dsn)
    core.migrate()
    core.append_model_run(record.model_runs[0])
    core.append_shadow_run_request(record.request)
    core.append_decision_packet(record.decision_packet)
    store = ShadowPostgresStore(dsn)

    store.append_shadow_cycle_record(record)
    store.append_shadow_cycle_record(record)
    assert store.get_shadow_cycle_record(record.record_id) == record
    assert record in store.shadow_cycle_records()

    conflicting = replace(
        record,
        snapshot=replace(record.snapshot, last_activity_id="different"),
        content_hash="",
    )
    with pytest.raises(PersistenceConflictError, match="record_id conflitante"):
        store.append_shadow_cycle_record(conflicting)


@pytest.mark.persistence
def test_postgres_backup_restore_rolls_back_core_if_shadow_cycle_conflicts(
    tmp_path: Path,
) -> None:
    dsn = os.environ.get("MARKO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("MARKO_TEST_POSTGRES_DSN ausente")
    record = _current_cycle_record()
    core = PostgresStore(dsn)
    core.migrate()
    core.append_model_run(record.model_runs[0])
    core.append_shadow_run_request(record.request)
    core.append_decision_packet(record.decision_packet)
    core.append_shadow_cycle_record(record)
    conflicting = replace(
        record,
        snapshot=replace(record.snapshot, last_activity_id="backup-conflict"),
        content_hash="",
    )
    source = _store_with_cycle(conflicting)
    activity_id = f"backup-atomic-{uuid4()}"
    source.append_activity(
        Activity(
            activity_id,
            ActivityKind.DEPOSIT,
            "backup-test",
            NOW,
            NOW,
            Money.of("1", "BRL"),
        )
    )
    backup = tmp_path / "shadow-cycle-conflict.json"
    create_backup(backup, source)

    with pytest.raises(PersistenceConflictError, match="record_id conflitante"):
        restore_backup(backup, core)

    assert all(activity.activity_id != activity_id for activity in core.activities())


def _store_with_cycle(record: ShadowCycleRecord) -> MemoryStore:
    store = MemoryStore()
    for run in record.model_runs:
        store.append_model_run(run)
    store.append_shadow_run_request(record.request)
    store.append_decision_packet(record.decision_packet)
    store.append_shadow_cycle_record(record)
    return store


def _current_cycle_record() -> ShadowCycleRecord:
    observation = Observation(
        "shadow-observation-1",
        "IPCA",
        Decimal("0.31"),
        "% a.m.",
        "IBGE/SIDRA",
        TimeCoordinates(
            NOW,
            NOW + timedelta(minutes=1),
            NOW + timedelta(minutes=2),
            NOW + timedelta(minutes=3),
        ),
        "shadow-vintage-1",
        "sha256:raw-shadow",
    )
    matrix = np.random.default_rng(42).normal([0.0002, 0.0004], [0.001, 0.01], size=(20, 2))
    problem = PortfolioProblem(
        ("DEFENSIVE", "RISK"),
        tuple(tuple(float(value) for value in row) for row in matrix),
        current_weights=(0.6, 0.4),
    )
    run = execute_model_run(
        model=MinimumVariance(shrinkage=0.1),
        problem=problem,
        created_at=NOW,
        code_version="shadow-test",
        dataset_fingerprint="sha256:shadow-dataset",
        policy_id="ips",
        policy_version=1,
        universe_id="shadow-universe",
        universe_version=1,
        parameters=(),
        random_seed=42,
        solver=SolverRecord("internal", "1", (), ("quadratic",)),
    )
    request = ShadowRunRequest.create(
        "monthly-shadow-test",
        NOW + timedelta(minutes=5),
        NOW + timedelta(minutes=3),
    )
    packet = CashFlowRebalancer().build_packet(
        packet_id="shadow-packet-1",
        created_at=NOW + timedelta(minutes=5),
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
            ValidatedModelRunRef.from_model_run(run, dataset_available_at=request.knowledge_cutoff),
        ),
        evidence_ids=(observation.observation_id,),
        shadow_request_id=request.request_id,
        knowledge_cutoff=request.knowledge_cutoff,
    )
    reconciliation = reconcile_shadow_packet(
        packet,
        request=request,
        model_runs=(run,),
        observations=(observation,),
        checked_at=packet.created_at + timedelta(minutes=1),
    )
    journal = ShadowCycleJournal()
    for index, state in enumerate(
        (
            ShadowCycleState.SCHEDULED,
            ShadowCycleState.DRAFT,
            ShadowCycleState.REVIEWED,
            ShadowCycleState.RECONCILED,
        )
    ):
        journal = journal.record(
            cycle_id=request.request_id,
            state=state,
            occurred_at=request.scheduled_for + timedelta(minutes=index),
        )
    return ShadowCycleRecord(
        request=request,
        snapshot=PortfolioSnapshot("shadow-snapshot-1", request.knowledge_cutoff, None, (), ()),
        vintages=(
            DataVintage(
                observation.vintage_id,
                observation.times.available_at,
                observation.raw_payload_hash,
                (observation.observation_id,),
            ),
        ),
        model_runs=(run,),
        decision_packet=packet,
        reconciliation=reconciliation,
        journal=journal,
    )
