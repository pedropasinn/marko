from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from marko.money import decimal_value


@dataclass(frozen=True, slots=True)
class TimeCoordinates:
    effective_at: datetime
    observed_at: datetime
    available_at: datetime
    ingested_at: datetime

    def __post_init__(self) -> None:
        values = (self.effective_at, self.observed_at, self.available_at, self.ingested_at)
        if any(value.tzinfo is None for value in values):
            raise ValueError("todas as coordenadas temporais precisam de timezone")
        if values != tuple(sorted(values)):
            raise ValueError("esperado effective <= observed <= available <= ingested")


@dataclass(frozen=True, slots=True)
class Observation:
    observation_id: str
    series_id: str
    value: Decimal
    unit: str
    source: str
    times: TimeCoordinates
    vintage_id: str
    dimensions: tuple[tuple[str, str], ...] = ()
    quality_flags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        required = (
            self.observation_id,
            self.series_id,
            self.unit,
            self.source,
            self.vintage_id,
        )
        if any(not value.strip() for value in required):
            raise ValueError("identificadores, unidade, fonte e vintage são obrigatórios")
        keys = [key for key, _ in self.dimensions]
        if len(keys) != len(set(keys)):
            raise ValueError("dimensions não pode repetir chaves")
        object.__setattr__(self, "value", decimal_value(self.value))


@dataclass(frozen=True, slots=True)
class DataVintage:
    vintage_id: str
    created_at: datetime
    source_hash: str
    observation_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.vintage_id.strip() or not self.source_hash.strip():
            raise ValueError("vintage_id e source_hash são obrigatórios")
        if self.created_at.tzinfo is None:
            raise ValueError("created_at precisa de timezone")
        if len(self.observation_ids) != len(set(self.observation_ids)):
            raise ValueError("observation_ids duplicados")
