from __future__ import annotations

import json
import os
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from marko.__main__ import main
from marko.activities import Activity, ActivityKind
from marko.decision import (
    CashFlowRebalancer,
    CashTarget,
    DecisionPacket,
    Holding,
    TargetAllocation,
    ValidatedModelRunRef,
)
from marko.ledger import Ledger
from marko.money import Money
from marko.persistence import (
    ParquetObservationStore,
    PersistenceConflictError,
    PersistenceIntegrityError,
    PostgresStore,
    create_backup,
    restore_backup,
    verify_backup,
)
from marko.portfolio_lab import MinimumVariance, PortfolioProblem
from marko.research_registry import ModelRun, SolverRecord, execute_model_run
from marko.temporal import Observation, TimeCoordinates

NOW = datetime(2026, 8, 20, 12, tzinfo=UTC)


class MemoryStore:
    def __init__(self) -> None:
        self.migrated = False
        self.activity_values: dict[str, Activity] = {}
        self.observation_values: dict[str, Observation] = {}
        self.run_values: dict[str, ModelRun] = {}
        self.packet_values: dict[str, DecisionPacket] = {}

    def migrate(self) -> None:
        self.migrated = True

    def append_activity(self, activity: Activity) -> None:
        self.append_activities((activity,))

    def append_activities(self, activities: tuple[Activity, ...]) -> None:
        pending = dict(self.activity_values)
        for activity in activities:
            _append(pending, activity.activity_id, activity)
        ledger = Ledger(
            sorted(
                pending.values(),
                key=lambda value: (
                    value.effective_at,
                    value.recorded_at,
                    value.sequence,
                    value.activity_id,
                ),
            )
        )
        ledger.validate_integrity()
        self.activity_values = pending

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        return tuple(
            sorted(
                (
                    value
                    for value in self.activity_values.values()
                    if as_of is None or value.effective_at <= as_of
                ),
                key=lambda value: value.activity_id,
            )
        )

    def append_observation(self, observation: Observation) -> None:
        _append(self.observation_values, observation.observation_id, observation)

    def observations_as_known_at(
        self, series_id: str, known_at: datetime
    ) -> tuple[Observation, ...]:
        return tuple(
            value
            for value in self.observations()
            if value.series_id == series_id and value.times.available_at <= known_at
        )

    def observations(self) -> tuple[Observation, ...]:
        return tuple(
            sorted(self.observation_values.values(), key=lambda value: value.observation_id)
        )

    def append_model_run(self, run: ModelRun) -> None:
        _append(self.run_values, run.run_id, run)

    def get_model_run(self, run_id: str) -> ModelRun:
        return self.run_values[run_id]

    def model_runs(self) -> tuple[ModelRun, ...]:
        return tuple(sorted(self.run_values.values(), key=lambda value: value.run_id))

    def append_decision_packet(self, packet: DecisionPacket) -> None:
        _append(self.packet_values, packet.packet_id, packet)

    def get_decision_packet(self, packet_id: str) -> DecisionPacket:
        return self.packet_values[packet_id]

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        return tuple(sorted(self.packet_values.values(), key=lambda value: value.packet_id))


def _append[T](values: dict[str, T], identifier: str, value: T) -> None:
    previous = values.get(identifier)
    if previous is not None and previous != value:
        raise PersistenceConflictError(identifier)
    values[identifier] = value


def samples() -> tuple[Activity, Observation, ModelRun, DecisionPacket]:
    activity = Activity(
        "deposit-1",
        ActivityKind.DEPOSIT,
        "broker",
        NOW,
        NOW + timedelta(minutes=1),
        Money.of("1000", "BRL"),
    )
    times = TimeCoordinates(
        NOW,
        NOW + timedelta(minutes=1),
        NOW + timedelta(minutes=2),
        NOW + timedelta(minutes=3),
    )
    observation = Observation(
        "obs-1",
        "IPCA",
        Decimal("7657.73"),
        "index",
        "IBGE/SIDRA",
        times,
        "vintage-1",
        "sha256:raw",
        (("territory", "BR"),),
    )
    rng = np.random.default_rng(42)
    matrix = rng.normal([0.0002, 0.0004], [0.001, 0.01], size=(80, 2))
    problem = PortfolioProblem(
        ("DEFENSIVE", "RISK"),
        tuple(tuple(float(value) for value in row) for row in matrix),
        current_weights=(0.6, 0.4),
    )
    run = execute_model_run(
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
    assert run.validated_candidate is not None
    packet = CashFlowRebalancer().build_packet(
        packet_id="packet-1",
        created_at=NOW + timedelta(minutes=4),
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
        evidence_ids=(observation.observation_id,),
    )
    return activity, observation, run, packet


def populated_store() -> MemoryStore:
    store = MemoryStore()
    activity, observation, run, packet = samples()
    store.append_activity(activity)
    store.append_observation(observation)
    store.append_model_run(run)
    store.append_decision_packet(packet)
    return store


def test_backup_verification_restore_and_idempotency(tmp_path: Path) -> None:
    source = populated_store()
    backup = tmp_path / "marko-backup.json"
    created = create_backup(backup, source)
    assert created == verify_backup(backup)
    counts = (
        created.activities,
        created.observations,
        created.model_runs,
        created.decision_packets,
    )
    assert counts == (
        1,
        1,
        1,
        1,
    )

    restored = MemoryStore()
    assert restore_backup(backup, restored) == created
    assert restore_backup(backup, restored) == created
    assert restored.activities() == source.activities()
    assert restored.observations() == source.observations()
    assert restored.model_runs() == source.model_runs()
    assert restored.decision_packets() == source.decision_packets()


def test_backup_rejects_tampered_content(tmp_path: Path) -> None:
    backup = tmp_path / "marko-backup.json"
    create_backup(backup, populated_store())
    document = json.loads(backup.read_text(encoding="utf-8"))
    document["collections"]["activities"][0]["payload"]["account_id"] = "altered"
    backup.write_text(json.dumps(document), encoding="utf-8")
    with pytest.raises(PersistenceIntegrityError, match="hash do backup"):
        verify_backup(backup)


def test_backup_restores_paired_transfers_atomically(tmp_path: Path) -> None:
    source = MemoryStore()
    transfer_out = Activity(
        "pair-out",
        ActivityKind.CASH_TRANSFER_OUT,
        "broker",
        NOW,
        NOW + timedelta(minutes=1),
        Money.of("100", "BRL"),
        related_account_id="bank",
        related_activity_id="pair-in",
        sequence=1,
    )
    transfer_in = Activity(
        "pair-in",
        ActivityKind.CASH_TRANSFER_IN,
        "bank",
        NOW,
        NOW + timedelta(minutes=1),
        Money.of("100", "BRL"),
        related_account_id="broker",
        related_activity_id="pair-out",
        sequence=2,
    )
    source.append_activities((transfer_out, transfer_in))
    backup = tmp_path / "transfer-backup.json"
    create_backup(backup, source)
    restored = MemoryStore()
    restore_backup(backup, restored)
    assert set(restored.activities()) == {transfer_out, transfer_in}


def test_cli_verifies_backup_and_requires_explicit_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    backup = tmp_path / "marko-backup.json"
    create_backup(backup, populated_store())
    assert main(["backup-verify", str(backup)]) == 0
    assert '"activities": 1' in capsys.readouterr().out
    monkeypatch.delenv("MARKO_DATABASE_URL", raising=False)
    assert main(["db-migrate"]) == 2
    assert "MARKO_DATABASE_URL" in capsys.readouterr().err


def test_cli_operates_backup_restore_and_shadow_reconciliation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = populated_store()
    monkeypatch.setattr("marko.__main__._postgres_store", lambda _: source)
    assert main(["db-migrate", "--dsn", "test"]) == 0
    assert source.migrated
    capsys.readouterr()

    backup = tmp_path / "cli-backup.json"
    assert main(["backup", str(backup), "--dsn", "test"]) == 0
    assert '"decision_packets": 1' in capsys.readouterr().out

    restored = MemoryStore()
    monkeypatch.setattr("marko.__main__._postgres_store", lambda _: restored)
    assert main(["backup-restore", str(backup), "--dsn", "test"]) == 0
    assert restored.migrated
    assert restored.activities() == source.activities()
    capsys.readouterr()

    monkeypatch.setattr("marko.__main__._postgres_store", lambda _: source)
    packet = source.decision_packets()[0]
    assert (
        main(
            [
                "shadow-reconcile",
                packet.packet_id,
                "--checked-at",
                (packet.created_at + timedelta(minutes=1)).isoformat(),
                "--dsn",
                "test",
            ]
        )
        == 0
    )
    assert '"ready": true' in capsys.readouterr().out


@pytest.mark.persistence
def test_parquet_observations_are_immutable_and_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")
    _, observation, _, _ = samples()
    store = ParquetObservationStore(tmp_path)
    first = store.write("ipca-vintage-1", (observation,))
    second = store.write("ipca-vintage-1", (observation,))
    restored_artifact, restored = store.read(first.path)
    assert first == second == restored_artifact
    assert restored == (observation,)
    assert first.rows == 1


@pytest.mark.persistence
def test_postgres_append_only_round_trips_and_point_in_time() -> None:
    dsn = os.environ.get("MARKO_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("MARKO_TEST_POSTGRES_DSN ausente")
    store = PostgresStore(dsn)
    store.migrate()
    store.migrate()
    activity, observation, run, packet = samples()
    store.append_activity(activity)
    store.append_activity(activity)
    store.append_observation(observation)
    store.append_model_run(run)
    store.append_decision_packet(packet)

    assert activity in store.activities()
    assert store.activities(activity.effective_at - timedelta(seconds=1)) == ()
    assert observation in store.observations_as_known_at("IPCA", NOW + timedelta(minutes=2))
    assert store.observations_as_known_at("IPCA", NOW + timedelta(minutes=1)) == ()
    assert store.get_model_run(run.run_id) == run
    assert store.get_decision_packet(packet.packet_id) == packet

    with pytest.raises(PersistenceConflictError):
        store.append_activity(replace(activity, account_id="another"))

    transfer_out = Activity(
        "transfer-out-1",
        ActivityKind.CASH_TRANSFER_OUT,
        "broker",
        NOW + timedelta(minutes=10),
        NOW + timedelta(minutes=11),
        Money.of("100", "BRL"),
        related_account_id="bank",
        related_activity_id="transfer-in-1",
        sequence=1,
    )
    transfer_in = Activity(
        "transfer-in-1",
        ActivityKind.CASH_TRANSFER_IN,
        "bank",
        NOW + timedelta(minutes=10),
        NOW + timedelta(minutes=11),
        Money.of("100", "BRL"),
        related_account_id="broker",
        related_activity_id="transfer-out-1",
        sequence=2,
    )
    with pytest.raises(ValueError, match="transferência sem par"):
        store.append_activity(transfer_out)
    store.append_activities((transfer_out, transfer_in))
    assert transfer_out in store.activities()
    assert transfer_in in store.activities()

    import psycopg

    with (
        pytest.raises(psycopg.errors.RaiseException),
        psycopg.connect(dsn) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "UPDATE marko_activities SET sequence = sequence + 1 WHERE activity_id = %s",
            (activity.activity_id,),
        )
