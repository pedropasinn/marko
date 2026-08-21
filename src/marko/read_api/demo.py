from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from marko.activities import Activity, ActivityKind
from marko.decision import DecisionAlternative, DecisionPacket, ValidatedModelRunRef
from marko.money import Money
from marko.portfolio_lab import NoAction, PortfolioProblem
from marko.research_registry import ModelRun, SolverRecord, execute_model_run
from marko.shadow import ShadowRunRequest
from marko.temporal import Observation, TimeCoordinates


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 1, day, hour, tzinfo=UTC)


class DemoReadStore:
    """Dataset sintético, imutável e determinístico para demonstração da interface."""

    def __init__(self) -> None:
        self._activities = (
            Activity(
                "demo-activity-001",
                ActivityKind.DEPOSIT,
                "demo-account",
                _at(2),
                _at(2, 13),
                gross_amount=Money.of("10000.00", "BRL"),
            ),
            Activity(
                "demo-activity-002",
                ActivityKind.BUY,
                "demo-account",
                _at(5),
                _at(5, 13),
                gross_amount=Money.of("6000.00", "BRL"),
                instrument_id="DEMO-FUND-A",
                quantity=Decimal("60"),
                fee=Money.of("2.50", "BRL"),
            ),
        )
        self._observations = (
            Observation(
                "demo-observation-001",
                "DEMO_RATE",
                Decimal("0.125"),
                "ratio",
                "synthetic-demo",
                TimeCoordinates(_at(1), _at(2), _at(3), _at(3, 13)),
                "demo-vintage-001",
                "synthetic-hash-001",
                (("region", "demo"),),
            ),
            Observation(
                "demo-observation-002",
                "DEMO_RATE",
                Decimal("0.120"),
                "ratio",
                "synthetic-demo",
                TimeCoordinates(_at(8), _at(9), _at(10), _at(10, 13)),
                "demo-vintage-002",
                "synthetic-hash-002",
                (("region", "demo"),),
            ),
        )
        problem = PortfolioProblem(
            ("DEMO-FUND-A", "DEMO-FUND-B"),
            ((0.01, 0.005), (-0.004, 0.002), (0.006, -0.001)),
            current_weights=(0.6, 0.4),
        )
        run = execute_model_run(
            model=NoAction(),
            problem=problem,
            created_at=_at(11),
            code_version="demo-v1",
            dataset_fingerprint="synthetic-dataset",
            policy_id="demo-policy",
            policy_version=1,
            universe_id="demo-universe",
            universe_version=1,
            parameters=(("purpose", "interface-demo"),),
            random_seed=42,
            solver=SolverRecord("demo-solver", "1", (), ("deterministic",)),
        )
        assert run.validated_candidate is not None
        self._runs = (run,)
        request = ShadowRunRequest.create("demo-monthly", _at(12), _at(11))
        self._shadow_requests = (request,)
        no_action = DecisionAlternative(
            "no_action",
            (),
            (("DEMO-FUND-A", Decimal("0.6")), ("DEMO-FUND-B", Decimal("0.4"))),
            Money.of("0.00", "BRL"),
            Decimal("0"),
            True,
            ("cenário sintético sem execução",),
        )
        self._packets = (
            DecisionPacket(
                "demo-packet-001",
                _at(12),
                "demo-policy",
                1,
                (
                    ValidatedModelRunRef.from_model_run(
                        run,
                        dataset_available_at=_at(10),
                    ),
                ),
                ("demo-observation-002",),
                (no_action,),
                request.request_id,
                request.knowledge_cutoff,
            ),
        )

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        if as_of is None:
            return self._activities
        return tuple(item for item in self._activities if item.recorded_at <= as_of)

    def observations_as_known_at(
        self, series_id: str | None, known_at: datetime
    ) -> tuple[Observation, ...]:
        return tuple(
            item
            for item in self._observations
            if item.times.available_at <= known_at
            and (series_id is None or item.series_id == series_id)
        )

    def model_runs(self) -> tuple[ModelRun, ...]:
        return self._runs

    def shadow_run_requests(self) -> tuple[ShadowRunRequest, ...]:
        return self._shadow_requests

    def decision_packets(self) -> tuple[DecisionPacket, ...]:
        return self._packets

    def get_decision_packet(self, packet_id: str) -> DecisionPacket:
        for packet in self._packets:
            if packet.packet_id == packet_id:
                return packet
        raise KeyError(packet_id)
