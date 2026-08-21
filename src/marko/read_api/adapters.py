from __future__ import annotations

from datetime import datetime

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.persistence.postgres import PostgresStore
from marko.research_registry import ModelRun
from marko.temporal import Observation


class PostgresReadStore:
    """Expõe somente consultas, mesmo que o adaptador persistente tenha comandos."""

    def __init__(self, dsn: str) -> None:
        self._store = PostgresStore(dsn)

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        return self._store.activities(as_of)

    def observations_as_known_at(
        self, series_id: str | None, known_at: datetime
    ) -> tuple[Observation, ...]:
        if series_id is not None:
            return self._store.observations_as_known_at(series_id, known_at)
        return tuple(
            observation
            for observation in self._store.observations()
            if observation.times.available_at <= known_at
        )

    def model_runs(self) -> tuple[ModelRun, ...]:
        return self._store.model_runs()

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        return self._store.decision_packets()

    def get_decision_packet(self, packet_id: str) -> DecisionPacket:
        return self._store.get_decision_packet(packet_id)
