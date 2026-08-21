from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum, StrEnum
from itertools import pairwise
from math import isfinite
from typing import Self

from marko.analytics import PerformancePoint
from marko.decision import DecisionPacket
from marko.money import Money, decimal_value
from marko.research_registry import ModelRun
from marko.shadow import ShadowReconciliation, ShadowRunRequest
from marko.snapshots import CashBalance, PortfolioSnapshot, PositionBalance, PriceQuote
from marko.temporal import DataVintage


class ShadowIdentityConflictError(ValueError):
    """A mesma identidade foi reapresentada com conteúdo diferente."""


class ShadowCycleState(StrEnum):
    SCHEDULED = "scheduled"
    BLOCKED = "blocked"
    DRAFT = "draft"
    REVIEWED = "reviewed"
    RECONCILED = "reconciled"


_VALID_TRANSITIONS: dict[ShadowCycleState, frozenset[ShadowCycleState]] = {
    ShadowCycleState.SCHEDULED: frozenset({ShadowCycleState.BLOCKED, ShadowCycleState.DRAFT}),
    ShadowCycleState.BLOCKED: frozenset({ShadowCycleState.DRAFT}),
    ShadowCycleState.DRAFT: frozenset({ShadowCycleState.BLOCKED, ShadowCycleState.REVIEWED}),
    ShadowCycleState.REVIEWED: frozenset({ShadowCycleState.BLOCKED, ShadowCycleState.RECONCILED}),
    ShadowCycleState.RECONCILED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class ShadowCycleEvent:
    cycle_id: str
    sequence: int
    state: ShadowCycleState
    occurred_at: datetime
    previous_hash: str | None = None
    details: tuple[tuple[str, str], ...] = ()
    event_id: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.cycle_id.strip():
            raise ValueError("cycle_id é obrigatório")
        if self.sequence < 0:
            raise ValueError("sequence não pode ser negativa")
        if self.occurred_at.tzinfo is None:
            raise ValueError("occurred_at precisa de timezone")
        if self.sequence == 0 and self.previous_hash is not None:
            raise ValueError("primeiro evento não pode referenciar previous_hash")
        if self.sequence > 0 and not self.previous_hash:
            raise ValueError("evento subsequente exige previous_hash")
        keys = [key for key, _ in self.details]
        if any(not key.strip() for key in keys) or len(keys) != len(set(keys)):
            raise ValueError("details exige chaves únicas e não vazias")
        canonical_details = tuple(sorted(self.details))
        object.__setattr__(self, "details", canonical_details)
        identity = _sha256(("shadow-cycle-event", self.cycle_id, self.sequence))
        payload_hash = _sha256(
            (
                self.cycle_id,
                self.sequence,
                self.state,
                self.occurred_at,
                self.previous_hash,
                canonical_details,
            )
        )
        if self.event_id and self.event_id != identity:
            raise ValueError("event_id não corresponde à identidade canônica")
        if self.content_hash and self.content_hash != payload_hash:
            raise ValueError("content_hash não corresponde ao conteúdo canônico")
        object.__setattr__(self, "event_id", identity)
        object.__setattr__(self, "content_hash", payload_hash)


@dataclass(frozen=True, slots=True)
class ShadowCycleJournal:
    events: tuple[ShadowCycleEvent, ...] = ()

    def __post_init__(self) -> None:
        if not self.events:
            return
        cycle_id = self.events[0].cycle_id
        previous: ShadowCycleEvent | None = None
        for sequence, event in enumerate(self.events):
            if event.cycle_id != cycle_id:
                raise ValueError("diário não pode misturar ciclos")
            if event.sequence != sequence:
                raise ValueError("sequence do diário precisa ser contígua")
            if previous is None:
                if event.state is not ShadowCycleState.SCHEDULED:
                    raise ValueError("diário precisa começar em scheduled")
            else:
                if event.previous_hash != previous.content_hash:
                    raise ValueError("cadeia de hashes do diário é inválida")
                if event.occurred_at < previous.occurred_at:
                    raise ValueError("eventos do diário estão fora de ordem temporal")
                _validate_transition(previous.state, event.state)
            previous = event

    @property
    def cycle_id(self) -> str | None:
        return self.events[0].cycle_id if self.events else None

    @property
    def state(self) -> ShadowCycleState | None:
        return self.events[-1].state if self.events else None

    @property
    def head_hash(self) -> str | None:
        return self.events[-1].content_hash if self.events else None

    def append(self, event: ShadowCycleEvent) -> Self:
        for existing in self.events:
            if existing.event_id != event.event_id:
                continue
            if existing.content_hash != event.content_hash:
                raise ShadowIdentityConflictError(f"event_id conflitante: {event.event_id}")
            return self
        if self.events:
            previous = self.events[-1]
            if event.cycle_id != previous.cycle_id:
                raise ValueError("evento pertence a outro ciclo")
            if event.sequence != previous.sequence + 1:
                raise ValueError("sequence do evento não é a próxima do diário")
            if event.previous_hash != previous.content_hash:
                raise ValueError("previous_hash não corresponde ao diário")
        elif event.sequence != 0 or event.state is not ShadowCycleState.SCHEDULED:
            raise ValueError("primeiro evento precisa ser scheduled com sequence zero")
        return type(self)((*self.events, event))

    def record(
        self,
        *,
        cycle_id: str,
        state: ShadowCycleState,
        occurred_at: datetime,
        details: tuple[tuple[str, str], ...] = (),
    ) -> Self:
        if self.events:
            if cycle_id != self.events[-1].cycle_id:
                raise ValueError("cycle_id não corresponde ao diário")
            sequence = self.events[-1].sequence + 1
            previous_hash = self.events[-1].content_hash
        else:
            sequence = 0
            previous_hash = None
        return self.append(
            ShadowCycleEvent(
                cycle_id,
                sequence,
                state,
                occurred_at,
                previous_hash,
                details,
            )
        )


@dataclass(frozen=True, slots=True)
class ShadowCycleRecord:
    request: ShadowRunRequest
    snapshot: PortfolioSnapshot
    vintages: tuple[DataVintage, ...]
    model_runs: tuple[ModelRun, ...]
    decision_packet: DecisionPacket
    reconciliation: ShadowReconciliation
    journal: ShadowCycleJournal
    record_id: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.decision_packet.shadow_request_id != self.request.request_id:
            raise ValueError("DecisionPacket pertence a outro ShadowRunRequest")
        if self.decision_packet.knowledge_cutoff != self.request.knowledge_cutoff:
            raise ValueError("knowledge_cutoff do DecisionPacket diverge do request")
        if self.snapshot.as_of > self.request.knowledge_cutoff:
            raise ValueError("snapshot sucede o knowledge_cutoff do ciclo")
        vintage_ids = tuple(vintage.vintage_id for vintage in self.vintages)
        if len(vintage_ids) != len(set(vintage_ids)):
            raise ValueError("vintage_id duplicado no ciclo")
        future_vintages = tuple(
            vintage.vintage_id
            for vintage in self.vintages
            if vintage.created_at > self.request.knowledge_cutoff
        )
        if future_vintages:
            raise ValueError(f"vintages posteriores ao knowledge_cutoff: {future_vintages}")
        runs = {run.run_id: run for run in self.model_runs}
        if len(runs) != len(self.model_runs):
            raise ValueError("run_id duplicado no ciclo")
        references = {reference.run_id: reference for reference in self.decision_packet.model_runs}
        unexpected_runs = set(runs) - set(references)
        if unexpected_runs:
            raise ValueError(f"ModelRuns não referenciados pelo DecisionPacket: {unexpected_runs}")
        if self.reconciliation.packet_id != self.decision_packet.packet_id:
            raise ValueError("reconciliação pertence a outro DecisionPacket")
        if self.reconciliation.request_id != self.request.request_id:
            raise ValueError("reconciliação pertence a outro ShadowRunRequest")
        if self.reconciliation.knowledge_cutoff != self.request.knowledge_cutoff:
            raise ValueError("knowledge_cutoff da reconciliação diverge do request")
        if self.reconciliation.checked_at < self.decision_packet.created_at:
            raise ValueError("reconciliação precede o DecisionPacket")
        expected_missing_runs: list[str] = []
        expected_mismatched_runs: list[str] = []
        expected_future_runs: list[str] = []
        expected_missing_datasets: list[str] = []
        expected_mismatched_datasets: list[str] = []
        expected_future_datasets: list[str] = []
        for run_id in self.decision_packet.model_run_ids:
            reference = references[run_id]
            run = runs.get(run_id)
            if run is None:
                expected_missing_runs.append(run_id)
                continue
            if not reference.reconciles_with(run):
                expected_mismatched_runs.append(run_id)
            if run.created_at > self.request.knowledge_cutoff:
                expected_future_runs.append(run_id)
            if reference.dataset_fingerprint is None or reference.dataset_available_at is None:
                expected_missing_datasets.append(run_id)
            else:
                if reference.dataset_fingerprint != run.dataset_fingerprint:
                    expected_mismatched_datasets.append(run_id)
                if reference.dataset_available_at > self.request.knowledge_cutoff:
                    expected_future_datasets.append(run_id)
        expected_failures = (
            ("missing_model_run_ids", tuple(expected_missing_runs)),
            ("mismatched_model_run_ids", tuple(expected_mismatched_runs)),
            ("future_model_run_ids", tuple(expected_future_runs)),
            ("missing_dataset_run_ids", tuple(expected_missing_datasets)),
            ("mismatched_dataset_run_ids", tuple(expected_mismatched_datasets)),
            ("future_dataset_run_ids", tuple(expected_future_datasets)),
        )
        for field_name, expected in expected_failures:
            if getattr(self.reconciliation, field_name) != expected:
                raise ValueError(f"reconciliação não corresponde a {field_name}")
        if self.journal.cycle_id != self.request.request_id:
            raise ValueError("diário pertence a outro ciclo")
        if self.journal.state is ShadowCycleState.RECONCILED and not self.reconciliation.ready:
            raise ValueError("ciclo incompleto não pode ser marcado como reconciled")
        identity = _sha256(("shadow-cycle-record", self.request.request_id))
        payload_hash = _sha256(
            (
                self.request,
                self.snapshot,
                self.vintages,
                self.model_runs,
                self.decision_packet,
                self.reconciliation,
                self.journal,
            )
        )
        if self.record_id and self.record_id != identity:
            raise ValueError("record_id não corresponde à identidade canônica")
        if self.content_hash and self.content_hash != payload_hash:
            raise ValueError("content_hash não corresponde ao conteúdo canônico")
        object.__setattr__(self, "record_id", identity)
        object.__setattr__(self, "content_hash", payload_hash)

    @property
    def request_id(self) -> str:
        return self.request.request_id

    @property
    def knowledge_cutoff(self) -> datetime:
        return self.request.knowledge_cutoff


@dataclass(frozen=True, slots=True)
class ShadowCycleRegistry:
    records: tuple[ShadowCycleRecord, ...] = ()

    def __post_init__(self) -> None:
        seen: dict[str, str] = {}
        for record in self.records:
            previous_hash = seen.get(record.record_id)
            if previous_hash is not None:
                if previous_hash != record.content_hash:
                    raise ShadowIdentityConflictError(f"record_id conflitante: {record.record_id}")
                raise ValueError(f"record_id repetido: {record.record_id}")
            seen[record.record_id] = record.content_hash

    def append(self, record: ShadowCycleRecord) -> Self:
        for existing in self.records:
            if existing.record_id != record.record_id:
                continue
            if existing.content_hash != record.content_hash:
                raise ShadowIdentityConflictError(f"record_id conflitante: {record.record_id}")
            return self
        return type(self)((*self.records, record))


type ShadowJson = bool | int | float | str | list[ShadowJson] | dict[str, ShadowJson] | None


@dataclass(frozen=True, slots=True)
class ShadowCycleEnvelope:
    schema: str
    version: int
    payload: dict[str, ShadowJson]

    def __post_init__(self) -> None:
        if self.schema != "marko.shadow_cycle_record" or self.version != 1:
            raise ValueError("schema/version de ShadowCycleRecord não suportado")

    def canonical_json(self) -> str:
        return json.dumps(
            {"schema": self.schema, "version": self.version, "payload": self.payload},
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, value: str) -> Self:
        document = json.loads(value, object_pairs_hook=_unique_json_object)
        root = _json_mapping(document, "envelope")
        _json_exact(root, {"schema", "version", "payload"}, "envelope")
        schema = _json_text(root.get("schema"), "schema")
        version = _json_integer(root.get("version"), "version")
        payload = _json_mapping(root.get("payload"), "payload")
        return cls(schema, version, dict(payload))


def encode_shadow_cycle_record(record: ShadowCycleRecord) -> ShadowCycleEnvelope:
    payload: dict[str, ShadowJson] = {
        "record_id": record.record_id,
        "content_hash": record.content_hash,
        "knowledge_cutoff": record.knowledge_cutoff.isoformat(),
        "request_ref": {
            "request_id": record.request.request_id,
            "content_hash": _sha256(record.request),
        },
        "snapshot": _snapshot_json(record.snapshot),
        "vintages": [_vintage_json(vintage) for vintage in record.vintages],
        "model_run_refs": [
            {"run_id": run.run_id, "content_hash": _sha256(run)}
            for run in record.model_runs
        ],
        "decision_packet_ref": {
            "packet_id": record.decision_packet.packet_id,
            "content_hash": _sha256(record.decision_packet),
        },
        "reconciliation": _reconciliation_json(record.reconciliation),
        "journal": _journal_json(record.journal),
    }
    return ShadowCycleEnvelope("marko.shadow_cycle_record", 1, payload)


def shadow_cycle_reference_ids(
    envelope: ShadowCycleEnvelope,
) -> tuple[str, tuple[str, ...], str]:
    payload = envelope.payload
    request_ref = _json_mapping(payload.get("request_ref"), "request_ref")
    packet_ref = _json_mapping(payload.get("decision_packet_ref"), "decision_packet_ref")
    run_refs = _json_list(payload.get("model_run_refs"), "model_run_refs")
    request_id = _json_text(request_ref.get("request_id"), "request_id")
    packet_id = _json_text(packet_ref.get("packet_id"), "packet_id")
    run_ids = tuple(
        _json_text(_json_mapping(item, "model_run_ref").get("run_id"), "run_id")
        for item in run_refs
    )
    if len(run_ids) != len(set(run_ids)):
        raise ValueError("model_run_refs contém run_id duplicado")
    return request_id, run_ids, packet_id


def decode_shadow_cycle_record(
    envelope: ShadowCycleEnvelope,
    *,
    request: ShadowRunRequest,
    model_runs: tuple[ModelRun, ...],
    decision_packet: DecisionPacket,
) -> ShadowCycleRecord:
    payload = envelope.payload
    _json_exact(
        payload,
        {
            "record_id",
            "content_hash",
            "knowledge_cutoff",
            "request_ref",
            "snapshot",
            "vintages",
            "model_run_refs",
            "decision_packet_ref",
            "reconciliation",
            "journal",
        },
        "ShadowCycleRecord",
    )
    _validate_reference(
        payload.get("request_ref"), "request_id", request.request_id, _sha256(request)
    )
    if _json_datetime(payload.get("knowledge_cutoff"), "knowledge_cutoff") != (
        request.knowledge_cutoff
    ):
        raise ValueError("knowledge_cutoff persistido diverge do request")
    run_by_id = {run.run_id: run for run in model_runs}
    run_refs = _json_list(payload.get("model_run_refs"), "model_run_refs")
    if len(run_refs) != len(run_by_id):
        raise ValueError("ModelRuns carregados divergem das referências persistidas")
    ordered_runs: list[ModelRun] = []
    for index, raw_reference in enumerate(run_refs):
        reference = _json_mapping(raw_reference, f"model_run_refs[{index}]")
        run_id = _json_text(reference.get("run_id"), "run_id")
        run = run_by_id.get(run_id)
        if run is None:
            raise ValueError(f"ModelRun referenciado não foi carregado: {run_id}")
        _validate_reference(reference, "run_id", run_id, _sha256(run))
        ordered_runs.append(run)
    _validate_reference(
        payload.get("decision_packet_ref"),
        "packet_id",
        decision_packet.packet_id,
        _sha256(decision_packet),
    )
    vintage_values = _json_list(payload.get("vintages"), "vintages")
    record = ShadowCycleRecord(
        request=request,
        snapshot=_snapshot_from_json(payload.get("snapshot")),
        vintages=tuple(_vintage_from_json(value) for value in vintage_values),
        model_runs=tuple(ordered_runs),
        decision_packet=decision_packet,
        reconciliation=_reconciliation_from_json(payload.get("reconciliation")),
        journal=_journal_from_json(payload.get("journal")),
        record_id=_json_text(payload.get("record_id"), "record_id"),
        content_hash=_json_text(payload.get("content_hash"), "content_hash"),
    )
    return record


def _snapshot_json(snapshot: PortfolioSnapshot) -> dict[str, ShadowJson]:
    return {
        "snapshot_id": snapshot.snapshot_id,
        "as_of": snapshot.as_of.isoformat(),
        "last_activity_id": snapshot.last_activity_id,
        "cash": [
            {"account_id": item.account_id, "balance": _money_json(item.balance)}
            for item in snapshot.cash
        ],
        "positions": [
            {
                "account_id": item.account_id,
                "instrument_id": item.instrument_id,
                "quantity": str(item.quantity),
                "quote": _quote_json(item.quote) if item.quote is not None else None,
            }
            for item in snapshot.positions
        ],
    }


def _snapshot_from_json(value: object) -> PortfolioSnapshot:
    payload = _json_mapping(value, "snapshot")
    _json_exact(
        payload, {"snapshot_id", "as_of", "last_activity_id", "cash", "positions"}, "snapshot"
    )
    cash = tuple(
        CashBalance(
            _json_text(item.get("account_id"), "account_id"),
            _money_from_json(item.get("balance")),
        )
        for item in (
            _json_mapping(raw, "cash item") for raw in _json_list(payload.get("cash"), "cash")
        )
    )
    positions = []
    for raw in _json_list(payload.get("positions"), "positions"):
        item = _json_mapping(raw, "position")
        quote = item.get("quote")
        positions.append(
            PositionBalance(
                _json_text(item.get("account_id"), "account_id"),
                _json_text(item.get("instrument_id"), "instrument_id"),
                Decimal(_json_text(item.get("quantity"), "quantity")),
                _quote_from_json(quote) if quote is not None else None,
            )
        )
    last_activity = payload.get("last_activity_id")
    return PortfolioSnapshot(
        _json_text(payload.get("snapshot_id"), "snapshot_id"),
        _json_datetime(payload.get("as_of"), "as_of"),
        None if last_activity is None else _json_text(last_activity, "last_activity_id"),
        cash,
        tuple(positions),
    )


def _money_json(value: Money) -> dict[str, ShadowJson]:
    return {"amount": str(value.amount), "currency": value.currency}


def _money_from_json(value: object) -> Money:
    payload = _json_mapping(value, "money")
    _json_exact(payload, {"amount", "currency"}, "money")
    return Money.of(
        _json_text(payload.get("amount"), "amount"),
        _json_text(payload.get("currency"), "currency"),
    )


def _quote_json(value: PriceQuote) -> dict[str, ShadowJson]:
    return {
        "instrument_id": value.instrument_id,
        "price": _money_json(value.price),
        "as_of": value.as_of.isoformat(),
        "available_at": value.available_at.isoformat(),
        "observation_id": value.observation_id,
        "source": value.source,
        "vintage_id": value.vintage_id,
    }


def _quote_from_json(value: object) -> PriceQuote:
    payload = _json_mapping(value, "quote")
    _json_exact(
        payload,
        {
            "instrument_id",
            "price",
            "as_of",
            "available_at",
            "observation_id",
            "source",
            "vintage_id",
        },
        "quote",
    )
    return PriceQuote(
        _json_text(payload.get("instrument_id"), "instrument_id"),
        _money_from_json(payload.get("price")),
        _json_datetime(payload.get("as_of"), "as_of"),
        _json_datetime(payload.get("available_at"), "available_at"),
        _json_text(payload.get("observation_id"), "observation_id"),
        _json_text(payload.get("source"), "source"),
        _json_text(payload.get("vintage_id"), "vintage_id"),
    )


def _vintage_json(value: DataVintage) -> dict[str, ShadowJson]:
    return {
        "vintage_id": value.vintage_id,
        "created_at": value.created_at.isoformat(),
        "source_hash": value.source_hash,
        "observation_ids": list(value.observation_ids),
    }


def _vintage_from_json(value: object) -> DataVintage:
    payload = _json_mapping(value, "vintage")
    _json_exact(payload, {"vintage_id", "created_at", "source_hash", "observation_ids"}, "vintage")
    return DataVintage(
        _json_text(payload.get("vintage_id"), "vintage_id"),
        _json_datetime(payload.get("created_at"), "created_at"),
        _json_text(payload.get("source_hash"), "source_hash"),
        tuple(
            _json_text(item, "observation_id")
            for item in _json_list(payload.get("observation_ids"), "observation_ids")
        ),
    )


_RECONCILIATION_FIELDS = (
    "missing_model_run_ids",
    "mismatched_model_run_ids",
    "future_model_run_ids",
    "missing_evidence_ids",
    "future_evidence_ids",
    "missing_dataset_run_ids",
    "mismatched_dataset_run_ids",
    "future_dataset_run_ids",
)


def _reconciliation_json(value: ShadowReconciliation) -> dict[str, ShadowJson]:
    payload: dict[str, ShadowJson] = {
        "packet_id": value.packet_id,
        "checked_at": value.checked_at.isoformat(),
        "request_id": value.request_id,
        "knowledge_cutoff": value.knowledge_cutoff.isoformat() if value.knowledge_cutoff else None,
    }
    payload.update({name: list(getattr(value, name)) for name in _RECONCILIATION_FIELDS})
    return payload


def _reconciliation_from_json(value: object) -> ShadowReconciliation:
    payload = _json_mapping(value, "reconciliation")
    _json_exact(
        payload,
        {"packet_id", "checked_at", "request_id", "knowledge_cutoff", *_RECONCILIATION_FIELDS},
        "reconciliation",
    )
    request_id = payload.get("request_id")
    cutoff = payload.get("knowledge_cutoff")
    failures = {
        name: tuple(_json_text(item, name) for item in _json_list(payload.get(name), name))
        for name in _RECONCILIATION_FIELDS
    }
    return ShadowReconciliation(
        packet_id=_json_text(payload.get("packet_id"), "packet_id"),
        checked_at=_json_datetime(payload.get("checked_at"), "checked_at"),
        request_id=None if request_id is None else _json_text(request_id, "request_id"),
        knowledge_cutoff=None if cutoff is None else _json_datetime(cutoff, "knowledge_cutoff"),
        **failures,
    )


def _journal_json(value: ShadowCycleJournal) -> dict[str, ShadowJson]:
    return {
        "events": [
            {
                "cycle_id": event.cycle_id,
                "sequence": event.sequence,
                "state": event.state.value,
                "occurred_at": event.occurred_at.isoformat(),
                "previous_hash": event.previous_hash,
                "details": [[key, item] for key, item in event.details],
                "event_id": event.event_id,
                "content_hash": event.content_hash,
            }
            for event in value.events
        ]
    }


def _journal_from_json(value: object) -> ShadowCycleJournal:
    payload = _json_mapping(value, "journal")
    _json_exact(payload, {"events"}, "journal")
    events = []
    for raw in _json_list(payload.get("events"), "events"):
        item = _json_mapping(raw, "event")
        _json_exact(
            item,
            {
                "cycle_id",
                "sequence",
                "state",
                "occurred_at",
                "previous_hash",
                "details",
                "event_id",
                "content_hash",
            },
            "event",
        )
        previous = item.get("previous_hash")
        details = tuple(
            (_json_text(pair[0], "detail key"), _json_text(pair[1], "detail value"))
            for pair in (
                _json_list(value, "detail")
                for value in _json_list(item.get("details"), "details")
            )
            if len(pair) == 2
        )
        events.append(
            ShadowCycleEvent(
                cycle_id=_json_text(item.get("cycle_id"), "cycle_id"),
                sequence=_json_integer(item.get("sequence"), "sequence"),
                state=ShadowCycleState(_json_text(item.get("state"), "state")),
                occurred_at=_json_datetime(item.get("occurred_at"), "occurred_at"),
                previous_hash=None if previous is None else _json_text(previous, "previous_hash"),
                details=details,
                event_id=_json_text(item.get("event_id"), "event_id"),
                content_hash=_json_text(item.get("content_hash"), "content_hash"),
            )
        )
    return ShadowCycleJournal(tuple(events))


def _validate_reference(
    value: object, identifier_field: str, identifier: str, content_hash: str
) -> None:
    payload = _json_mapping(value, f"{identifier_field} reference")
    _json_exact(payload, {identifier_field, "content_hash"}, "reference")
    if _json_text(payload.get(identifier_field), identifier_field) != identifier:
        raise ValueError(f"referência divergente: {identifier_field}")
    if _json_text(payload.get("content_hash"), "content_hash") != content_hash:
        raise ValueError(f"hash divergente para {identifier_field}: {identifier}")


def _unique_json_object(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in values:
        if key in result:
            raise ValueError(f"chave JSON duplicada: {key}")
        result[key] = value
    return result


def _json_mapping(value: object, name: str) -> dict[str, ShadowJson]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} precisa ser objeto JSON")
    return value


def _json_list(value: object, name: str) -> list[ShadowJson]:
    if not isinstance(value, list):
        raise ValueError(f"{name} precisa ser lista JSON")
    return value


def _json_exact(value: dict[str, ShadowJson], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise ValueError(f"campos inválidos em {name}")


def _json_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} precisa ser texto não vazio")
    return value


def _json_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} precisa ser inteiro")
    return value


def _json_datetime(value: object, name: str) -> datetime:
    parsed = datetime.fromisoformat(_json_text(value, name))
    if parsed.tzinfo is None:
        raise ValueError(f"{name} precisa de timezone")
    return parsed


class BenchmarkKind(StrEnum):
    OBSERVED = "observed"
    CDI = "cdi"
    EQUAL_WEIGHT = "1/n"


@dataclass(frozen=True, slots=True)
class ReturnPoint:
    at: datetime
    return_rate: Decimal

    def __post_init__(self) -> None:
        if self.at.tzinfo is None:
            raise ValueError("at precisa de timezone")
        value = decimal_value(self.return_rate)
        if value < -1:
            raise ValueError("retorno não pode ser menor que -100%")
        object.__setattr__(self, "return_rate", value)


@dataclass(frozen=True, slots=True)
class BenchmarkSeries:
    kind: BenchmarkKind
    performance_points: tuple[PerformancePoint, ...] = ()
    returns: tuple[ReturnPoint, ...] = ()
    expected_at: tuple[datetime, ...] = ()
    failures: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.performance_points and self.returns:
            raise ValueError("série deve usar PerformancePoint ou ReturnPoint, não ambos")
        if any(at.tzinfo is None for at in self.expected_at):
            raise ValueError("expected_at precisa de timezone")
        if len(self.expected_at) != len(set(self.expected_at)):
            raise ValueError("expected_at contém instantes duplicados")
        if any(not failure.strip() for failure in self.failures):
            raise ValueError("failures não pode conter texto vazio")


@dataclass(frozen=True, slots=True)
class BenchmarkMetrics:
    kind: BenchmarkKind
    twr: Decimal | None
    maximum_drawdown: Decimal | None
    return_drift_from_observed: Decimal | None
    starts_at: datetime | None
    ends_at: datetime | None
    sample_count: int
    complete: bool
    failures: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ShadowBenchmarkReport:
    observed: BenchmarkMetrics
    cdi: BenchmarkMetrics
    equal_weight: BenchmarkMetrics
    report_id: str = ""
    content_hash: str = ""

    def __post_init__(self) -> None:
        if self.observed.kind is not BenchmarkKind.OBSERVED:
            raise ValueError("observed precisa representar a carteira observada")
        if self.cdi.kind is not BenchmarkKind.CDI:
            raise ValueError("cdi precisa representar o CDI")
        if self.equal_weight.kind is not BenchmarkKind.EQUAL_WEIGHT:
            raise ValueError("equal_weight precisa representar 1/N")
        payload = (self.observed, self.cdi, self.equal_weight)
        identity = _sha256(("shadow-benchmark-report", payload))
        payload_hash = _sha256(payload)
        if self.report_id and self.report_id != identity:
            raise ValueError("report_id não corresponde à identidade canônica")
        if self.content_hash and self.content_hash != payload_hash:
            raise ValueError("content_hash não corresponde ao conteúdo canônico")
        object.__setattr__(self, "report_id", identity)
        object.__setattr__(self, "content_hash", payload_hash)

    @property
    def complete(self) -> bool:
        return self.observed.complete and self.cdi.complete and self.equal_weight.complete

    @property
    def failures(self) -> tuple[str, ...]:
        failures: list[str] = []
        for metrics in (self.observed, self.cdi, self.equal_weight):
            failures.extend(f"{metrics.kind.value}: {failure}" for failure in metrics.failures)
        return tuple(failures)


def build_shadow_benchmark_report(
    *,
    observed: BenchmarkSeries | None,
    cdi: BenchmarkSeries | None,
    equal_weight: BenchmarkSeries | None,
) -> ShadowBenchmarkReport:
    inputs = (
        _series_or_missing(observed, BenchmarkKind.OBSERVED),
        _series_or_missing(cdi, BenchmarkKind.CDI),
        _series_or_missing(equal_weight, BenchmarkKind.EQUAL_WEIGHT),
    )
    metrics = tuple(_measure_series(series) for series in inputs)
    observed_metrics = metrics[0]
    compared = [observed_metrics]
    for current in metrics[1:]:
        failures = list(current.failures)
        drift: Decimal | None = None
        if observed_metrics.twr is None:
            failures.append("drift indisponível: carteira observada sem TWR")
        elif current.twr is not None:
            drift = current.twr - observed_metrics.twr
        if (
            observed_metrics.starts_at is not None
            and current.starts_at is not None
            and (
                current.starts_at != observed_metrics.starts_at
                or current.ends_at != observed_metrics.ends_at
            )
        ):
            failures.append("janela temporal diverge da carteira observada")
        compared.append(
            replace(
                current,
                return_drift_from_observed=drift,
                complete=not failures,
                failures=tuple(failures),
            )
        )
    return ShadowBenchmarkReport(compared[0], compared[1], compared[2])


def _series_or_missing(
    series: BenchmarkSeries | None, expected_kind: BenchmarkKind
) -> BenchmarkSeries:
    if series is None:
        return BenchmarkSeries(expected_kind, failures=("série não fornecida",))
    if series.kind is not expected_kind:
        raise ValueError(f"esperado benchmark {expected_kind.value}, recebido {series.kind.value}")
    return series


def _measure_series(series: BenchmarkSeries) -> BenchmarkMetrics:
    failures = list(series.failures)
    if series.performance_points:
        ordered_points = tuple(sorted(series.performance_points, key=lambda point: point.at))
        instants = tuple(point.at for point in ordered_points)
        rates = _performance_returns(ordered_points, failures)
    else:
        ordered_returns = tuple(sorted(series.returns, key=lambda point: point.at))
        instants = tuple(point.at for point in ordered_returns)
        rates = tuple(point.return_rate for point in ordered_returns)
        if not ordered_returns:
            failures.append("série sem retornos")
    if len(instants) != len(set(instants)):
        failures.append("série contém instantes duplicados")
        rates = ()
    missing = tuple(sorted(set(series.expected_at) - set(instants)))
    if missing:
        failures.append("pontos esperados ausentes: " + ", ".join(_utc(at) for at in missing))
    twr: Decimal | None = None
    drawdown: Decimal | None = None
    if rates:
        twr, drawdown = _return_metrics(rates)
    return BenchmarkMetrics(
        series.kind,
        twr,
        drawdown,
        Decimal(0) if series.kind is BenchmarkKind.OBSERVED and twr is not None else None,
        min(instants) if instants else None,
        max(instants) if instants else None,
        len(instants),
        not failures and twr is not None and drawdown is not None,
        tuple(failures),
    )


def _performance_returns(
    points: tuple[PerformancePoint, ...], failures: list[str]
) -> tuple[Decimal, ...]:
    if len(points) < 2:
        failures.append("PerformancePoint exige ao menos dois pontos")
        return ()
    rates: list[Decimal] = []
    for previous, current in pairwise(points):
        try:
            previous.value._check_currency(current.value)
            previous.value._check_currency(current.external_flow)
        except ValueError as error:
            failures.append(str(error))
            return ()
        if previous.value.amount <= 0:
            failures.append("patrimônio precisa ser positivo para calcular retorno")
            return ()
        growth = (current.value.amount - current.external_flow.amount) / previous.value.amount
        if growth < 0:
            failures.append("fluxo externo implica retorno menor que -100%")
            return ()
        rates.append(growth - Decimal(1))
    return tuple(rates)


def _return_metrics(rates: tuple[Decimal, ...]) -> tuple[Decimal, Decimal]:
    cumulative = Decimal(1)
    peak = Decimal(1)
    maximum_drawdown = Decimal(0)
    for rate in rates:
        cumulative *= Decimal(1) + rate
        peak = max(peak, cumulative)
        if peak != 0:
            maximum_drawdown = min(maximum_drawdown, cumulative / peak - Decimal(1))
    return cumulative - Decimal(1), maximum_drawdown


def _validate_transition(previous: ShadowCycleState, current: ShadowCycleState) -> None:
    if current not in _VALID_TRANSITIONS[previous]:
        raise ValueError(f"transição shadow inválida: {previous.value} -> {current.value}")


def _sha256(value: object) -> str:
    encoded = json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode()
    return hashlib.sha256(encoded).hexdigest()


def _canonical(value: object) -> object:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, Decimal):
        normalized = value.normalize()
        return "0" if normalized == 0 else format(normalized, "f")
    if isinstance(value, float):
        if not isfinite(value):
            raise ValueError("hash canônico não aceita float não finito")
        return repr(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("hash canônico não aceita datetime sem timezone")
        return _utc(value)
    if isinstance(value, Enum):
        return _canonical(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _canonical(getattr(value, field.name))
            for field in fields(value)
            if field.name not in {"event_id", "record_id", "report_id", "content_hash"}
        }
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise TypeError("hash canônico exige chaves textuais")
        return {key: _canonical(item) for key, item in value.items()}
    raise TypeError(f"tipo não suportado pelo hash canônico: {type(value).__name__}")


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()
