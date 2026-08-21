from __future__ import annotations

from datetime import datetime
from typing import Protocol

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.research_registry import ModelRun
from marko.shadow import ShadowRunRequest
from marko.shadow_operation import ShadowCycleRecord
from marko.temporal import Observation


class ActivityRepository(Protocol):
    def append_activity(self, activity: Activity) -> None: ...

    def append_activities(self, activities: tuple[Activity, ...]) -> None: ...

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]: ...


class ObservationRepository(Protocol):
    def append_observation(self, observation: Observation) -> None: ...

    def observations_as_known_at(
        self, series_id: str, known_at: datetime
    ) -> tuple[Observation, ...]: ...

    def observations(self) -> tuple[Observation, ...]: ...


class ModelRunRepository(Protocol):
    def append_model_run(self, run: ModelRun) -> None: ...

    def get_model_run(self, run_id: str) -> ModelRun: ...

    def model_runs(self) -> tuple[ModelRun, ...]: ...


class DecisionPacketRepository(Protocol):
    def append_decision_packet(self, packet: DecisionPacket) -> None: ...

    def get_decision_packet(self, packet_id: str) -> DecisionPacket: ...

    def decision_packets(self) -> tuple[DecisionPacket, ...]: ...


class ShadowRunRequestRepository(Protocol):
    def append_shadow_run_request(self, request: ShadowRunRequest) -> None: ...

    def get_shadow_run_request(self, request_id: str) -> ShadowRunRequest: ...

    def shadow_run_requests(self) -> tuple[ShadowRunRequest, ...]: ...


class ShadowCycleRepository(Protocol):
    def append_shadow_cycle_record(self, record: ShadowCycleRecord) -> None: ...

    def get_shadow_cycle_record(self, record_id: str) -> ShadowCycleRecord: ...

    def shadow_cycle_records(self) -> tuple[ShadowCycleRecord, ...]: ...


class PersistenceStore(
    ActivityRepository,
    ObservationRepository,
    ModelRunRepository,
    DecisionPacketRepository,
    ShadowRunRequestRepository,
    ShadowCycleRepository,
    Protocol,
):
    pass
