from __future__ import annotations

import hashlib
from datetime import datetime
from importlib import resources
from typing import Any, cast

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.ledger import Ledger
from marko.persistence.codec import (
    SerializationEnvelope,
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
from marko.persistence.errors import PersistenceConflictError, PersistenceIntegrityError
from marko.persistence.shadow_postgres import ShadowPostgresStore
from marko.research_registry import ModelRun
from marko.shadow import ShadowRunRequest
from marko.shadow_operation import ShadowCycleRecord
from marko.temporal import Observation


class PostgresStore(ShadowPostgresStore):
    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("dsn é obrigatório")
        self._dsn = dsn

    def migrate(self) -> None:
        psycopg = _psycopg()
        migration_root = resources.files("marko.persistence.migrations")
        migrations = sorted(
            (
                resource
                for resource in migration_root.iterdir()
                if resource.name.endswith(".sql") and resource.name[:3].isdigit()
            ),
            key=lambda resource: resource.name,
        )
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (749_201_303,))
            cursor.execute(
                """
                    CREATE TABLE IF NOT EXISTS marko_schema_migrations (
                        version integer PRIMARY KEY,
                        name text NOT NULL,
                        checksum text NOT NULL,
                        applied_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
            )
            for migration in migrations:
                version = int(migration.name[:3])
                sql = migration.read_text(encoding="utf-8")
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                cursor.execute(
                    "SELECT checksum FROM marko_schema_migrations WHERE version = %s",
                    (version,),
                )
                row = cursor.fetchone()
                if row is not None:
                    if str(row[0]) != checksum:
                        raise PersistenceIntegrityError(
                            f"checksum divergente na migração {migration.name}"
                        )
                    continue
                cursor.execute(sql)
                cursor.execute(
                    """
                    INSERT INTO marko_schema_migrations (version, name, checksum)
                    VALUES (%s, %s, %s)
                    """,
                    (version, migration.name, checksum),
                )

    def append_activity(self, activity: Activity) -> None:
        self.append_activities((activity,))

    def append_activities(self, activities: tuple[Activity, ...]) -> None:
        if not activities:
            return
        identifiers = [activity.activity_id for activity in activities]
        if len(identifiers) != len(set(identifiers)):
            raise PersistenceConflictError("lote contém activity_id duplicado")
        ordered = tuple(
            sorted(
                activities,
                key=lambda value: (
                    value.effective_at,
                    value.recorded_at,
                    value.sequence,
                    value.activity_id,
                ),
            )
        )
        envelopes = {activity.activity_id: encode_activity(activity) for activity in ordered}
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            self._append_activities_with_cursor(cursor, ordered, identifiers, envelopes)

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        if as_of is not None and as_of.tzinfo is None:
            raise ValueError("as_of precisa de timezone")
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_activities
            ORDER BY effective_at, recorded_at, sequence, activity_id
            """,
            (),
        )
        ledger = Ledger(decode_activity(SerializationEnvelope.from_json(row)) for row in rows)
        return ledger.activities(as_of)

    def append_observation(self, observation: Observation) -> None:
        envelope = encode_observation(observation)
        self._append(
            """
            INSERT INTO marko_observations (
                observation_id, series_id, effective_at, available_at, vintage_id,
                dimensions, payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
            ON CONFLICT (observation_id) DO NOTHING
            """,
            (
                observation.observation_id,
                observation.series_id,
                observation.times.effective_at,
                observation.times.available_at,
                observation.vintage_id,
                _json_pairs(observation.dimensions),
                envelope.canonical_json(),
                envelope.digest(),
            ),
            "marko_observations",
            "observation_id",
            observation.observation_id,
            envelope.digest(),
        )

    def observations_as_known_at(
        self, series_id: str, known_at: datetime
    ) -> tuple[Observation, ...]:
        if not series_id.strip() or known_at.tzinfo is None:
            raise ValueError("series_id e known_at com timezone são obrigatórios")
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_observations
            WHERE series_id = %s AND available_at <= %s
            ORDER BY effective_at, available_at, observation_id
            """,
            (series_id, known_at),
        )
        return tuple(decode_observation(SerializationEnvelope.from_json(row)) for row in rows)

    def observations(self) -> tuple[Observation, ...]:
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_observations
            ORDER BY effective_at, available_at, observation_id
            """,
            (),
        )
        return tuple(decode_observation(SerializationEnvelope.from_json(row)) for row in rows)

    def append_model_run(self, run: ModelRun) -> None:
        envelope = encode_model_run(run)
        self._append(
            """
            INSERT INTO marko_model_runs (run_id, created_at, payload, payload_hash)
            VALUES (%s, %s, %s::jsonb, %s)
            ON CONFLICT (run_id) DO NOTHING
            """,
            (run.run_id, run.created_at, envelope.canonical_json(), envelope.digest()),
            "marko_model_runs",
            "run_id",
            run.run_id,
            envelope.digest(),
        )

    def get_model_run(self, run_id: str) -> ModelRun:
        return decode_model_run(self._get("marko_model_runs", "run_id", run_id))

    def model_runs(self) -> tuple[ModelRun, ...]:
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_model_runs
            ORDER BY created_at, run_id
            """,
            (),
        )
        return tuple(decode_model_run(SerializationEnvelope.from_json(row)) for row in rows)

    def append_decision_packet(self, packet: DecisionPacket) -> None:
        envelope = encode_decision_packet(packet)
        self._append(
            """
            INSERT INTO marko_decision_packets (
                packet_id, created_at, shadow_request_id, knowledge_cutoff, payload, payload_hash
            )
            VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (packet_id) DO NOTHING
            """,
            (
                packet.packet_id,
                packet.created_at,
                packet.shadow_request_id,
                packet.knowledge_cutoff,
                envelope.canonical_json(),
                envelope.digest(),
            ),
            "marko_decision_packets",
            "packet_id",
            packet.packet_id,
            envelope.digest(),
        )

    def get_decision_packet(self, packet_id: str) -> DecisionPacket:
        return decode_decision_packet(self._get("marko_decision_packets", "packet_id", packet_id))

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_decision_packets
            ORDER BY created_at, packet_id
            """,
            (),
        )
        return tuple(decode_decision_packet(SerializationEnvelope.from_json(row)) for row in rows)

    def append_shadow_run_request(self, request: ShadowRunRequest) -> None:
        envelope = encode_shadow_run_request(request)
        self._append(
            """
            INSERT INTO marko_shadow_run_requests (
                request_id, schedule_id, scheduled_for, knowledge_cutoff, payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (request_id) DO NOTHING
            """,
            (
                request.request_id,
                request.schedule_id,
                request.scheduled_for,
                request.knowledge_cutoff,
                envelope.canonical_json(),
                envelope.digest(),
            ),
            "marko_shadow_run_requests",
            "request_id",
            request.request_id,
            envelope.digest(),
        )

    def get_shadow_run_request(self, request_id: str) -> ShadowRunRequest:
        return decode_shadow_run_request(
            self._get("marko_shadow_run_requests", "request_id", request_id)
        )

    def shadow_run_requests(self) -> tuple[ShadowRunRequest, ...]:
        rows = self._payload_rows(
            """
            SELECT payload::text, payload_hash FROM marko_shadow_run_requests
            ORDER BY scheduled_for, request_id
            """,
            (),
        )
        return tuple(
            decode_shadow_run_request(SerializationEnvelope.from_json(row)) for row in rows
        )

    def restore_validated(
        self,
        activities: tuple[Activity, ...],
        observations: tuple[Observation, ...],
        model_runs: tuple[ModelRun, ...],
        shadow_run_requests: tuple[ShadowRunRequest, ...],
        decision_packets: tuple[DecisionPacket, ...],
        shadow_cycle_records: tuple[ShadowCycleRecord, ...],
    ) -> None:
        """Restaura um lote já validado em uma única transação PostgreSQL."""
        ordered_activities = tuple(
            sorted(
                activities,
                key=lambda value: (
                    value.effective_at,
                    value.recorded_at,
                    value.sequence,
                    value.activity_id,
                ),
            )
        )
        activity_ids = [activity.activity_id for activity in ordered_activities]
        if len(activity_ids) != len(set(activity_ids)):
            raise PersistenceConflictError("lote contém activity_id duplicado")
        activity_envelopes = {
            activity.activity_id: encode_activity(activity) for activity in ordered_activities
        }
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (749_201_305,))
            if ordered_activities:
                self._append_activities_with_cursor(
                    cursor,
                    ordered_activities,
                    activity_ids,
                    activity_envelopes,
                )
            for observation in observations:
                envelope = encode_observation(observation)
                self._append_with_cursor(
                    cursor,
                    """
                    INSERT INTO marko_observations (
                        observation_id, series_id, effective_at, available_at, vintage_id,
                        dimensions, payload, payload_hash
                    ) VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                    ON CONFLICT (observation_id) DO NOTHING
                    """,
                    (
                        observation.observation_id,
                        observation.series_id,
                        observation.times.effective_at,
                        observation.times.available_at,
                        observation.vintage_id,
                        _json_pairs(observation.dimensions),
                        envelope.canonical_json(),
                        envelope.digest(),
                    ),
                    "marko_observations",
                    "observation_id",
                    observation.observation_id,
                    envelope.digest(),
                )
            for run in model_runs:
                envelope = encode_model_run(run)
                self._append_with_cursor(
                    cursor,
                    """
                    INSERT INTO marko_model_runs (run_id, created_at, payload, payload_hash)
                    VALUES (%s, %s, %s::jsonb, %s)
                    ON CONFLICT (run_id) DO NOTHING
                    """,
                    (run.run_id, run.created_at, envelope.canonical_json(), envelope.digest()),
                    "marko_model_runs",
                    "run_id",
                    run.run_id,
                    envelope.digest(),
                )
            for request in shadow_run_requests:
                envelope = encode_shadow_run_request(request)
                self._append_with_cursor(
                    cursor,
                    """
                    INSERT INTO marko_shadow_run_requests (
                        request_id, schedule_id, scheduled_for, knowledge_cutoff,
                        payload, payload_hash
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (request_id) DO NOTHING
                    """,
                    (
                        request.request_id,
                        request.schedule_id,
                        request.scheduled_for,
                        request.knowledge_cutoff,
                        envelope.canonical_json(),
                        envelope.digest(),
                    ),
                    "marko_shadow_run_requests",
                    "request_id",
                    request.request_id,
                    envelope.digest(),
                )
            for packet in decision_packets:
                envelope = encode_decision_packet(packet)
                self._append_with_cursor(
                    cursor,
                    """
                    INSERT INTO marko_decision_packets (
                        packet_id, created_at, shadow_request_id, knowledge_cutoff,
                        payload, payload_hash
                    )
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (packet_id) DO NOTHING
                    """,
                    (
                        packet.packet_id,
                        packet.created_at,
                        packet.shadow_request_id,
                        packet.knowledge_cutoff,
                        envelope.canonical_json(),
                        envelope.digest(),
                    ),
                    "marko_decision_packets",
                    "packet_id",
                    packet.packet_id,
                    envelope.digest(),
                )
            for record in shadow_cycle_records:
                self._append_shadow_cycle_with_cursor(cursor, record)

    def _append_activities_with_cursor(
        self,
        cursor: Any,
        ordered: tuple[Activity, ...],
        identifiers: list[str],
        envelopes: dict[str, SerializationEnvelope],
    ) -> None:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", (749_201_304,))
        cursor.execute(
            """
            SELECT activity_id, payload_hash FROM marko_activities
            WHERE activity_id = ANY(%s)
            """,
            (identifiers,),
        )
        existing_hashes = {str(row[0]): str(row[1]) for row in cursor.fetchall()}
        for identifier, stored_hash in existing_hashes.items():
            if stored_hash != envelopes[identifier].digest():
                raise PersistenceConflictError(f"ID conflitante: {identifier}")
        pending = tuple(
            activity for activity in ordered if activity.activity_id not in existing_hashes
        )
        if not pending:
            return
        cursor.execute(
            """
            SELECT payload::text, payload_hash FROM marko_activities
            ORDER BY effective_at, recorded_at, sequence, activity_id
            """
        )
        ledger = Ledger(
            decode_activity(SerializationEnvelope.from_json(raw))
            for raw in self._verified_rows(cursor.fetchall())
        )
        for activity in pending:
            ledger.append(activity)
        ledger.validate_integrity()
        cursor.executemany(
            """
            INSERT INTO marko_activities (
                activity_id, effective_at, recorded_at, sequence, payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            [
                (
                    activity.activity_id,
                    activity.effective_at,
                    activity.recorded_at,
                    activity.sequence,
                    envelopes[activity.activity_id].canonical_json(),
                    envelopes[activity.activity_id].digest(),
                )
                for activity in pending
            ],
        )

    def _append(
        self,
        statement: str,
        parameters: tuple[object, ...],
        table: str,
        identifier_column: str,
        identifier: str,
        expected_hash: str,
    ) -> None:
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            self._append_with_cursor(
                cursor,
                statement,
                parameters,
                table,
                identifier_column,
                identifier,
                expected_hash,
            )

    @staticmethod
    def _append_with_cursor(
        cursor: Any,
        statement: str,
        parameters: tuple[object, ...],
        table: str,
        identifier_column: str,
        identifier: str,
        expected_hash: str,
    ) -> None:
        cursor.execute(statement, parameters)
        cursor.execute(
            f"SELECT payload_hash FROM {table} WHERE {identifier_column} = %s",
            (identifier,),
        )
        row = cursor.fetchone()
        if row is None:
            raise PersistenceIntegrityError(f"registro não persistido: {identifier}")
        if str(row[0]) != expected_hash:
            raise PersistenceConflictError(f"ID conflitante: {identifier}")

    def _get(self, table: str, identifier_column: str, identifier: str) -> SerializationEnvelope:
        if not identifier.strip():
            raise ValueError("identificador é obrigatório")
        rows = self._payload_rows(
            f"SELECT payload::text, payload_hash FROM {table} WHERE {identifier_column} = %s",
            (identifier,),
        )
        if not rows:
            raise KeyError(f"registro não encontrado: {identifier}")
        return SerializationEnvelope.from_json(rows[0])

    def _payload_rows(self, statement: str, parameters: tuple[object, ...]) -> tuple[str, ...]:
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(statement, parameters)
            return self._verified_rows(cursor.fetchall())

    @staticmethod
    def _verified_rows(rows: Any) -> tuple[str, ...]:
        payloads = []
        for row in rows:
            raw = str(row[0])
            envelope = SerializationEnvelope.from_json(raw)
            if envelope.digest() != str(row[1]):
                raise PersistenceIntegrityError("hash do payload persistido diverge")
            payloads.append(raw)
        return tuple(payloads)


def _json_pairs(values: tuple[tuple[str, str], ...]) -> str:
    import json

    return json.dumps(values, ensure_ascii=False, separators=(",", ":"))


def _psycopg() -> Any:
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("instale o extra persistence para usar PostgreSQL") from error
    return cast(Any, psycopg)
