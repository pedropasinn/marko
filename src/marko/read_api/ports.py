from __future__ import annotations

from datetime import datetime
from typing import Protocol

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.research_registry import ModelRun
from marko.temporal import Observation


class ReadStore(Protocol):
    """Porta mínima usada pela API; operações de escrita não fazem parte do contrato."""

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]: ...

    def observations_as_known_at(
        self, series_id: str | None, known_at: datetime
    ) -> tuple[Observation, ...]: ...

    def model_runs(self) -> tuple[ModelRun, ...]: ...

    def decision_packets(self) -> tuple[DecisionPacket, ...]: ...

    def get_decision_packet(self, packet_id: str) -> DecisionPacket: ...
