from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from marko.activities import Activity
from marko.decision import DecisionAlternative, DecisionPacket, TradeProposal
from marko.money import Money
from marko.portfolio_lab import PortfolioCandidate
from marko.research_registry import ModelRun, SolverRecord
from marko.temporal import Observation, TimeCoordinates


class ApiModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class StatusDTO(ApiModel):
    status: str
    api_version: str
    mode: str
    synthetic: bool


class MoneyDTO(ApiModel):
    amount: str
    currency: str


class PairDTO(ApiModel):
    key: str
    value: str


class ActivityDTO(ApiModel):
    activity_id: str
    kind: str
    account_id: str
    effective_at: datetime
    recorded_at: datetime
    gross_amount: MoneyDTO | None
    instrument_id: str | None
    quantity: str | None
    fee: MoneyDTO | None
    tax: MoneyDTO | None
    cost_basis: MoneyDTO | None
    counter_amount: MoneyDTO | None
    related_account_id: str | None
    related_activity_id: str | None
    related_instrument_id: str | None
    ratio: str | None
    external_id: str | None
    correction_of: str | None
    is_reversal: bool
    sequence: int


class TimeCoordinatesDTO(ApiModel):
    effective_at: datetime
    observed_at: datetime
    available_at: datetime
    ingested_at: datetime


class ObservationDTO(ApiModel):
    observation_id: str
    series_id: str
    value: str
    unit: str
    source: str
    times: TimeCoordinatesDTO
    vintage_id: str
    raw_payload_hash: str
    dimensions: tuple[PairDTO, ...]
    quality_flags: tuple[str, ...]


class SolverDTO(ApiModel):
    solver_id: str
    version: str
    tolerances: tuple[PairDTO, ...]
    capabilities: tuple[str, ...]


class AssetWeightDTO(ApiModel):
    asset_id: str
    weight: float


class CandidateDTO(ApiModel):
    model_id: str
    weights: tuple[AssetWeightDTO, ...]
    expected_return: float
    volatility: float
    solver_status: str
    diagnostics: tuple[PairDTO, ...]


class ModelRunDTO(ApiModel):
    run_id: str
    created_at: datetime
    model_id: str
    code_version: str
    environment_fingerprint: str
    dataset_fingerprint: str
    policy_id: str
    policy_version: int
    universe_id: str
    universe_version: int
    parameters: tuple[PairDTO, ...]
    random_seed: int
    solver: SolverDTO
    candidate: CandidateDTO
    validated: bool
    violations: tuple[str, ...]


class TradeProposalDTO(ApiModel):
    instrument_id: str
    side: str
    quantity: str
    notional: MoneyDTO
    estimated_cost: MoneyDTO


class ProjectedWeightDTO(ApiModel):
    asset_id: str
    weight: str


class DecisionAlternativeDTO(ApiModel):
    alternative_id: str
    trades: tuple[TradeProposalDTO, ...]
    projected_weights: tuple[ProjectedWeightDTO, ...]
    unallocated_cash: MoneyDTO
    turnover: str
    feasible: bool
    reasons: tuple[str, ...]


class DecisionPacketDTO(ApiModel):
    packet_id: str
    created_at: datetime
    policy_id: str
    policy_version: int
    model_run_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    alternatives: tuple[DecisionAlternativeDTO, ...]
    shadow_request_id: str | None
    knowledge_cutoff: datetime | None


def money_dto(value: Money | None) -> MoneyDTO | None:
    if value is None:
        return None
    return MoneyDTO(amount=str(value.amount), currency=value.currency)


def activity_dto(value: Activity) -> ActivityDTO:
    return ActivityDTO(
        activity_id=value.activity_id,
        kind=value.kind.value,
        account_id=value.account_id,
        effective_at=value.effective_at,
        recorded_at=value.recorded_at,
        gross_amount=money_dto(value.gross_amount),
        instrument_id=value.instrument_id,
        quantity=str(value.quantity) if value.quantity is not None else None,
        fee=money_dto(value.fee),
        tax=money_dto(value.tax),
        cost_basis=money_dto(value.cost_basis),
        counter_amount=money_dto(value.counter_amount),
        related_account_id=value.related_account_id,
        related_activity_id=value.related_activity_id,
        related_instrument_id=value.related_instrument_id,
        ratio=str(value.ratio) if value.ratio is not None else None,
        external_id=value.external_id,
        correction_of=value.correction_of,
        is_reversal=value.is_reversal,
        sequence=value.sequence,
    )


def _times_dto(value: TimeCoordinates) -> TimeCoordinatesDTO:
    return TimeCoordinatesDTO(
        effective_at=value.effective_at,
        observed_at=value.observed_at,
        available_at=value.available_at,
        ingested_at=value.ingested_at,
    )


def _pairs(values: tuple[tuple[str, str], ...]) -> tuple[PairDTO, ...]:
    return tuple(PairDTO(key=key, value=value) for key, value in values)


def observation_dto(value: Observation) -> ObservationDTO:
    return ObservationDTO(
        observation_id=value.observation_id,
        series_id=value.series_id,
        value=str(value.value),
        unit=value.unit,
        source=value.source,
        times=_times_dto(value.times),
        vintage_id=value.vintage_id,
        raw_payload_hash=value.raw_payload_hash,
        dimensions=_pairs(value.dimensions),
        quality_flags=value.quality_flags,
    )


def _solver_dto(value: SolverRecord) -> SolverDTO:
    return SolverDTO(
        solver_id=value.solver_id,
        version=value.version,
        tolerances=tuple(
            PairDTO(key=key, value=str(tolerance)) for key, tolerance in value.tolerances
        ),
        capabilities=value.capabilities,
    )


def _candidate_dto(value: PortfolioCandidate) -> CandidateDTO:
    return CandidateDTO(
        model_id=value.model_id,
        weights=tuple(
            AssetWeightDTO(asset_id=asset_id, weight=weight)
            for asset_id, weight in zip(value.assets, value.weights, strict=True)
        ),
        expected_return=value.expected_return,
        volatility=value.volatility,
        solver_status=value.solver_status,
        diagnostics=_pairs(value.diagnostics),
    )


def model_run_dto(value: ModelRun) -> ModelRunDTO:
    # A projeção nunca atravessa ValidatedPortfolioCandidate.problem, que contém retornos.
    return ModelRunDTO(
        run_id=value.run_id,
        created_at=value.created_at,
        model_id=value.model_id,
        code_version=value.code_version,
        environment_fingerprint=value.environment_fingerprint,
        dataset_fingerprint=value.dataset_fingerprint,
        policy_id=value.policy_id,
        policy_version=value.policy_version,
        universe_id=value.universe_id,
        universe_version=value.universe_version,
        parameters=_pairs(value.parameters),
        random_seed=value.random_seed,
        solver=_solver_dto(value.solver),
        candidate=_candidate_dto(value.candidate),
        validated=value.validated_candidate is not None,
        violations=value.violations,
    )


def _trade_dto(value: TradeProposal) -> TradeProposalDTO:
    notional = money_dto(value.notional)
    estimated_cost = money_dto(value.estimated_cost)
    assert notional is not None and estimated_cost is not None
    return TradeProposalDTO(
        instrument_id=value.instrument_id,
        side=value.side.value,
        quantity=str(value.quantity),
        notional=notional,
        estimated_cost=estimated_cost,
    )


def _alternative_dto(value: DecisionAlternative) -> DecisionAlternativeDTO:
    unallocated = money_dto(value.unallocated_cash)
    assert unallocated is not None
    return DecisionAlternativeDTO(
        alternative_id=value.alternative_id,
        trades=tuple(_trade_dto(trade) for trade in value.trades),
        projected_weights=tuple(
            ProjectedWeightDTO(asset_id=asset_id, weight=str(weight))
            for asset_id, weight in value.projected_weights
        ),
        unallocated_cash=unallocated,
        turnover=str(value.turnover),
        feasible=value.feasible,
        reasons=value.reasons,
    )


def decision_packet_dto(value: DecisionPacket) -> DecisionPacketDTO:
    return DecisionPacketDTO(
        packet_id=value.packet_id,
        created_at=value.created_at,
        policy_id=value.policy_id,
        policy_version=value.policy_version,
        model_run_ids=value.model_run_ids,
        evidence_ids=value.evidence_ids,
        alternatives=tuple(_alternative_dto(item) for item in value.alternatives),
        shadow_request_id=value.shadow_request_id,
        knowledge_cutoff=value.knowledge_cutoff,
    )
