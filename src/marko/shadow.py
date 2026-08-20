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
    def create(cls, schedule_id: str, scheduled_for: datetime) -> ShadowRunRequest:
        canonical = f"{schedule_id}|{scheduled_for.astimezone(UTC).isoformat()}"
        request_id = hashlib.sha256(canonical.encode()).hexdigest()
        return cls(request_id, schedule_id, scheduled_for, scheduled_for)


@dataclass(frozen=True, slots=True)
class ShadowReconciliation:
    packet_id: str
    checked_at: datetime
    missing_model_run_ids: tuple[str, ...]
    mismatched_model_run_ids: tuple[str, ...]
    future_model_run_ids: tuple[str, ...]
    missing_evidence_ids: tuple[str, ...]
    future_evidence_ids: tuple[str, ...]

    @property
    def ready(self) -> bool:
        return not any(
            (
                self.missing_model_run_ids,
                self.mismatched_model_run_ids,
                self.future_model_run_ids,
                self.missing_evidence_ids,
                self.future_evidence_ids,
            )
        )


def reconcile_shadow_packet(
    packet: DecisionPacket,
    *,
    model_runs: tuple[ModelRun, ...],
    observations: tuple[Observation, ...],
    checked_at: datetime,
) -> ShadowReconciliation:
    if checked_at.tzinfo is None:
        raise ValueError("checked_at precisa de timezone")
    if checked_at < packet.created_at:
        raise ValueError("checked_at não pode preceder o DecisionPacket")
    runs = _unique_by_id(model_runs, "run_id")
    evidence = _unique_by_id(observations, "observation_id")
    missing_runs = []
    mismatched_runs = []
    future_runs = []
    for reference in packet.model_runs:
        run = runs.get(reference.run_id)
        if run is None:
            missing_runs.append(reference.run_id)
            continue
        if run.validated_candidate != reference.candidate:
            mismatched_runs.append(reference.run_id)
        if run.created_at > packet.created_at:
            future_runs.append(reference.run_id)
    missing_evidence = []
    future_evidence = []
    for identifier in packet.evidence_ids:
        observation = evidence.get(identifier)
        if observation is None:
            missing_evidence.append(identifier)
        elif observation.times.available_at > packet.created_at:
            future_evidence.append(identifier)
    return ShadowReconciliation(
        packet.packet_id,
        checked_at,
        tuple(missing_runs),
        tuple(mismatched_runs),
        tuple(future_runs),
        tuple(missing_evidence),
        tuple(future_evidence),
    )


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
