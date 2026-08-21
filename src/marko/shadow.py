from __future__ import annotations

import hashlib
from calendar import monthrange
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from marko.decision import DecisionPacket
from marko.research_registry import ModelRun
from marko.temporal import Observation


@dataclass(frozen=True, slots=True)
class MonthlyShadowSchedule:
    schedule_id: str
    day_of_month: int
    hour: int
    minute: int
    timezone: str

    def __post_init__(self) -> None:
        if not self.schedule_id.strip():
            raise ValueError("schedule_id é obrigatório")
        if not 1 <= self.day_of_month <= 31:
            raise ValueError("day_of_month precisa estar entre 1 e 31")
        if not 0 <= self.hour <= 23 or not 0 <= self.minute <= 59:
            raise ValueError("horário inválido")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone desconhecido") from error

    def due_between(
        self,
        after: datetime,
        until: datetime,
        *,
        limit: int = 24,
    ) -> tuple[ShadowRunRequest, ...]:
        if after.tzinfo is None or until.tzinfo is None:
            raise ValueError("after e until precisam de timezone")
        if until < after:
            raise ValueError("until não pode preceder after")
        if limit <= 0:
            raise ValueError("limit precisa ser positivo")
        timezone = ZoneInfo(self.timezone)
        cursor = after.astimezone(timezone)
        year, month = cursor.year, cursor.month
        requests: list[ShadowRunRequest] = []
        while len(requests) < limit:
            day = min(self.day_of_month, monthrange(year, month)[1])
            local = datetime(year, month, day, self.hour, self.minute, tzinfo=timezone)
            scheduled_for = local.astimezone(UTC)
            if scheduled_for > until.astimezone(UTC):
                break
            if scheduled_for > after.astimezone(UTC):
                requests.append(ShadowRunRequest.create(self.schedule_id, scheduled_for))
            year, month = _next_month(year, month)
        return tuple(requests)


@dataclass(frozen=True, slots=True)
class ShadowRunRequest:
    request_id: str
    schedule_id: str
    scheduled_for: datetime
    knowledge_cutoff: datetime

    def __post_init__(self) -> None:
        if not self.request_id.strip() or not self.schedule_id.strip():
            raise ValueError("request_id e schedule_id são obrigatórios")
        if self.scheduled_for.tzinfo is None or self.knowledge_cutoff.tzinfo is None:
            raise ValueError("timestamps precisam de timezone")
        if self.knowledge_cutoff > self.scheduled_for:
            raise ValueError("knowledge_cutoff não pode suceder scheduled_for")

    @classmethod
    def create(
        cls,
        schedule_id: str,
        scheduled_for: datetime,
        knowledge_cutoff: datetime | None = None,
    ) -> ShadowRunRequest:
        cutoff = scheduled_for if knowledge_cutoff is None else knowledge_cutoff
        if scheduled_for.tzinfo is None or cutoff.tzinfo is None:
            raise ValueError("timestamps precisam de timezone")
        canonical = "|".join(
            (
                schedule_id,
                scheduled_for.astimezone(UTC).isoformat(),
                cutoff.astimezone(UTC).isoformat(),
            )
        )
        request_id = hashlib.sha256(canonical.encode()).hexdigest()
        return cls(request_id, schedule_id, scheduled_for, cutoff)


@dataclass(frozen=True, slots=True)
class ShadowReconciliation:
    packet_id: str
    checked_at: datetime
    missing_model_run_ids: tuple[str, ...]
    mismatched_model_run_ids: tuple[str, ...]
    future_model_run_ids: tuple[str, ...]
    missing_evidence_ids: tuple[str, ...]
    future_evidence_ids: tuple[str, ...]
    request_id: str | None = None
    knowledge_cutoff: datetime | None = None
    missing_dataset_run_ids: tuple[str, ...] = ()
    mismatched_dataset_run_ids: tuple[str, ...] = ()
    future_dataset_run_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.packet_id.strip() or self.checked_at.tzinfo is None:
            raise ValueError("packet_id e checked_at com timezone são obrigatórios")
        if (self.request_id is None) != (self.knowledge_cutoff is None):
            raise ValueError("request_id e knowledge_cutoff precisam ser informados juntos")
        if self.request_id is not None and not self.request_id.strip():
            raise ValueError("request_id não pode ser vazio")
        if self.knowledge_cutoff is not None and self.knowledge_cutoff.tzinfo is None:
            raise ValueError("knowledge_cutoff precisa de timezone")

    @property
    def ready(self) -> bool:
        return (
            self.request_id is not None
            and self.knowledge_cutoff is not None
            and not any(
                (
                    self.missing_model_run_ids,
                    self.mismatched_model_run_ids,
                    self.future_model_run_ids,
                    self.missing_evidence_ids,
                    self.future_evidence_ids,
                    self.missing_dataset_run_ids,
                    self.mismatched_dataset_run_ids,
                    self.future_dataset_run_ids,
                )
            )
        )


def reconcile_shadow_packet(
    packet: DecisionPacket,
    *,
    request: ShadowRunRequest,
    model_runs: tuple[ModelRun, ...],
    observations: tuple[Observation, ...],
    checked_at: datetime,
) -> ShadowReconciliation:
    if checked_at.tzinfo is None:
        raise ValueError("checked_at precisa de timezone")
    if checked_at < packet.created_at:
        raise ValueError("checked_at não pode preceder o DecisionPacket")
    request_id, knowledge_cutoff = _shadow_context(packet, request)
    runs = _unique_by_id(model_runs, "run_id")
    evidence = _unique_by_id(observations, "observation_id")
    missing_runs = []
    mismatched_runs = []
    future_runs = []
    missing_datasets = []
    mismatched_datasets = []
    future_datasets = []
    for reference in packet.model_runs:
        run = runs.get(reference.run_id)
        if run is None:
            missing_runs.append(reference.run_id)
            continue
        if not reference.reconciles_with(run):
            mismatched_runs.append(reference.run_id)
        if run.created_at > knowledge_cutoff:
            future_runs.append(reference.run_id)
        if reference.dataset_available_at is None or reference.dataset_fingerprint is None:
            missing_datasets.append(reference.run_id)
        else:
            if reference.dataset_fingerprint != run.dataset_fingerprint:
                mismatched_datasets.append(reference.run_id)
            if reference.dataset_available_at > knowledge_cutoff:
                future_datasets.append(reference.run_id)
    missing_evidence = []
    future_evidence = []
    for identifier in packet.evidence_ids:
        observation = evidence.get(identifier)
        if observation is None:
            missing_evidence.append(identifier)
        elif observation.times.available_at > knowledge_cutoff:
            future_evidence.append(identifier)
    return ShadowReconciliation(
        packet.packet_id,
        checked_at,
        tuple(missing_runs),
        tuple(mismatched_runs),
        tuple(future_runs),
        tuple(missing_evidence),
        tuple(future_evidence),
        request_id,
        knowledge_cutoff,
        tuple(missing_datasets),
        tuple(mismatched_datasets),
        tuple(future_datasets),
    )


def _shadow_context(packet: DecisionPacket, request: ShadowRunRequest) -> tuple[str, datetime]:
    if packet.shadow_request_id is None or packet.knowledge_cutoff is None:
        raise ValueError("DecisionPacket não está ligado a um ShadowRunRequest")
    if (
        request.request_id != packet.shadow_request_id
        or request.knowledge_cutoff != packet.knowledge_cutoff
    ):
        raise ValueError("DecisionPacket não corresponde ao ShadowRunRequest")
    return packet.shadow_request_id, packet.knowledge_cutoff


def _unique_by_id[T](values: tuple[T, ...], attribute: str) -> dict[str, T]:
    result: dict[str, T] = {}
    for value in values:
        identifier = getattr(value, attribute)
        if not isinstance(identifier, str):
            raise TypeError(f"{attribute} precisa ser texto")
        if identifier in result:
            raise ValueError(f"{attribute} duplicado: {identifier}")
        result[identifier] = value
    return result


def _next_month(year: int, month: int) -> tuple[int, int]:
    return (year + 1, 1) if month == 12 else (year, month + 1)
