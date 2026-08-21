from __future__ import annotations

from typing import Any, cast

from marko.persistence.codec import (
    SerializationEnvelope,
    decode_decision_packet,
    decode_model_run,
    decode_shadow_run_request,
)
from marko.persistence.errors import PersistenceConflictError, PersistenceIntegrityError
from marko.shadow_operation import (
    ShadowCycleEnvelope,
    ShadowCycleRecord,
    decode_shadow_cycle_record,
    encode_shadow_cycle_record,
    shadow_cycle_reference_ids,
)


class ShadowPostgresStore:
    """Adapter append-only dos ciclos shadow; as entidades-base continuam normalizadas."""

    def __init__(self, dsn: str) -> None:
        if not dsn.strip():
            raise ValueError("dsn é obrigatório")
        self._dsn = dsn

    def append_shadow_cycle_record(self, record: ShadowCycleRecord) -> None:
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            self._append_shadow_cycle_with_cursor(cursor, record)

    @classmethod
    def _append_shadow_cycle_with_cursor(
        cls,
        cursor: Any,
        record: ShadowCycleRecord,
    ) -> None:
        envelope = encode_shadow_cycle_record(record)
        cls._validate_references(cursor, record)
        cursor.execute(
            """
            INSERT INTO marko_shadow_cycle_records (
                record_id, request_id, packet_id, knowledge_cutoff,
                journal_state, journal_head_hash, payload, payload_hash
            ) VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (record_id) DO NOTHING
            """,
            (
                record.record_id,
                record.request_id,
                record.decision_packet.packet_id,
                record.knowledge_cutoff,
                record.journal.state.value if record.journal.state is not None else None,
                record.journal.head_hash,
                envelope.canonical_json(),
                envelope.digest(),
            ),
        )
        cursor.execute(
            "SELECT payload_hash FROM marko_shadow_cycle_records WHERE record_id = %s",
            (record.record_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise PersistenceIntegrityError(f"ciclo shadow não persistido: {record.record_id}")
        if str(row[0]) != envelope.digest():
            raise PersistenceConflictError(f"record_id conflitante: {record.record_id}")

    def get_shadow_cycle_record(self, record_id: str) -> ShadowCycleRecord:
        if not record_id.strip():
            raise ValueError("record_id é obrigatório")
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload::text, payload_hash
                FROM marko_shadow_cycle_records WHERE record_id = %s
                """,
                (record_id,),
            )
            row = cursor.fetchone()
            if row is None:
                raise KeyError(f"registro não encontrado: {record_id}")
            return self._decode_row(cursor, row)

    def shadow_cycle_records(self) -> tuple[ShadowCycleRecord, ...]:
        psycopg = _psycopg()
        with psycopg.connect(self._dsn) as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload::text, payload_hash
                FROM marko_shadow_cycle_records
                ORDER BY knowledge_cutoff, request_id
                """
            )
            return tuple(self._decode_row(cursor, row) for row in cursor.fetchall())

    @staticmethod
    def _decode_row(cursor: Any, row: Any) -> ShadowCycleRecord:
        raw = str(row[0])
        envelope = ShadowCycleEnvelope.from_json(raw)
        if envelope.digest() != str(row[1]):
            raise PersistenceIntegrityError("hash do ShadowCycleRecord persistido diverge")
        request_id, run_ids, packet_id = shadow_cycle_reference_ids(envelope)
        request = decode_shadow_run_request(
            _core_envelope(cursor, "marko_shadow_run_requests", "request_id", request_id)
        )
        packet = decode_decision_packet(
            _core_envelope(cursor, "marko_decision_packets", "packet_id", packet_id)
        )
        runs = tuple(
            decode_model_run(_core_envelope(cursor, "marko_model_runs", "run_id", run_id))
            for run_id in run_ids
        )
        try:
            return decode_shadow_cycle_record(
                envelope,
                request=request,
                model_runs=runs,
                decision_packet=packet,
            )
        except (TypeError, ValueError) as error:
            raise PersistenceIntegrityError("conteúdo do ciclo shadow é inválido") from error

    @staticmethod
    def _validate_references(cursor: Any, record: ShadowCycleRecord) -> None:
        request = decode_shadow_run_request(
            _core_envelope(
                cursor, "marko_shadow_run_requests", "request_id", record.request.request_id
            )
        )
        if request != record.request:
            raise PersistenceConflictError("ShadowRunRequest persistido diverge do ciclo")
        packet = decode_decision_packet(
            _core_envelope(
                cursor,
                "marko_decision_packets",
                "packet_id",
                record.decision_packet.packet_id,
            )
        )
        if packet != record.decision_packet:
            raise PersistenceConflictError("DecisionPacket persistido diverge do ciclo")
        for run in record.model_runs:
            stored = decode_model_run(
                _core_envelope(cursor, "marko_model_runs", "run_id", run.run_id)
            )
            if stored != run:
                raise PersistenceConflictError(
                    f"ModelRun persistido diverge do ciclo: {run.run_id}"
                )


def _core_envelope(
    cursor: Any, table: str, identifier_column: str, identifier: str
) -> SerializationEnvelope:
    cursor.execute(
        f"SELECT payload::text, payload_hash FROM {table} WHERE {identifier_column} = %s",
        (identifier,),
    )
    row = cursor.fetchone()
    if row is None:
        raise PersistenceIntegrityError(f"referência persistida ausente: {identifier}")
    envelope = SerializationEnvelope.from_json(str(row[0]))
    if envelope.digest() != str(row[1]):
        raise PersistenceIntegrityError(f"hash da referência persistida diverge: {identifier}")
    return envelope


def _psycopg() -> Any:
    try:
        import psycopg
    except ImportError as error:
        raise RuntimeError("instale o extra persistence para usar PostgreSQL") from error
    return cast(Any, psycopg)
