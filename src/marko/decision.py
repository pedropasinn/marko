from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import Enum, StrEnum
from typing import cast

from marko.money import Money, decimal_value
from marko.portfolio_lab import ValidatedPortfolioCandidate
from marko.research_registry import ModelRun


class TradeSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Holding:
    instrument_id: str
    value: Money
    price: Money
    whole_shares: bool = False
    minimum_trade: Money | None = None

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id é obrigatório")
        self.value._check_currency(self.price)
        if self.value.amount < 0 or self.price.amount <= 0:
            raise ValueError("holding exige valor não negativo e preço positivo")
        if self.minimum_trade is not None:
            self.value._check_currency(self.minimum_trade)


@dataclass(frozen=True, slots=True)
class TargetAllocation:
    instrument_id: str
    target_weight: Decimal
    maximum_weight: Decimal

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id é obrigatório")
        target = decimal_value(self.target_weight)
        maximum = decimal_value(self.maximum_weight)
        if not 0 <= target <= maximum <= 1:
            raise ValueError("pesos-alvo inválidos")
        object.__setattr__(self, "target_weight", target)
        object.__setattr__(self, "maximum_weight", maximum)


@dataclass(frozen=True, slots=True)
class CashTarget:
    target_weight: Decimal
    maximum_weight: Decimal

    def __post_init__(self) -> None:
        target = decimal_value(self.target_weight)
        maximum = decimal_value(self.maximum_weight)
        if not 0 <= target <= maximum <= 1:
            raise ValueError("pesos-alvo de caixa inválidos")
        object.__setattr__(self, "target_weight", target)
        object.__setattr__(self, "maximum_weight", maximum)


@dataclass(frozen=True, slots=True, init=False)
class ValidatedModelRunRef:
    run_id: str
    run_payload_hash: str | None
    dataset_fingerprint: str | None = None
    candidate_hash: str = ""
    validation_witness: str = ""
    dataset_available_at: datetime | None = None

    def __init__(
        self,
        run: ModelRun,
        dataset_available_at: datetime | None = None,
    ) -> None:
        if not isinstance(run, ModelRun):
            raise TypeError("ValidatedModelRunRef exige uma instância de ModelRun")
        if run.validated_candidate is None or run.violations:
            raise ValueError("referência exige ModelRun validado")
        if run.validated_candidate.candidate != run.candidate:
            raise ValueError("candidato validado diverge do ModelRun")
        self._set_values(
            run_id=run.run_id,
            run_payload_hash=_model_run_payload_hash(run),
            dataset_fingerprint=run.dataset_fingerprint,
            candidate_hash=_content_hash("marko.portfolio_candidate@1", run.candidate),
            validation_witness=_content_hash(
                "marko.validated_model_run@1",
                {
                    "run_id": run.run_id,
                    "validated_candidate": run.validated_candidate,
                },
            ),
            dataset_available_at=dataset_available_at,
        )

    @classmethod
    def from_model_run(
        cls,
        run: ModelRun,
        *,
        dataset_available_at: datetime | None = None,
    ) -> ValidatedModelRunRef:
        return cls(run, dataset_available_at)

    @classmethod
    def _from_persisted(
        cls,
        *,
        run_id: str,
        run_payload_hash: str | None,
        dataset_fingerprint: str | None,
        candidate_hash: str,
        validation_witness: str,
        dataset_available_at: datetime | None,
    ) -> ValidatedModelRunRef:
        reference = object.__new__(cls)
        reference._set_values(
            run_id=run_id,
            run_payload_hash=run_payload_hash,
            dataset_fingerprint=dataset_fingerprint,
            candidate_hash=candidate_hash,
            validation_witness=validation_witness,
            dataset_available_at=dataset_available_at,
        )
        return reference

    @classmethod
    def _from_legacy(
        cls,
        *,
        run_id: str,
        candidate: ValidatedPortfolioCandidate,
        dataset_fingerprint: str | None,
        dataset_available_at: datetime | None,
    ) -> ValidatedModelRunRef:
        return cls._from_persisted(
            run_id=run_id,
            run_payload_hash=None,
            dataset_fingerprint=dataset_fingerprint,
            candidate_hash=_content_hash("marko.portfolio_candidate@1", candidate.candidate),
            validation_witness=_content_hash(
                "marko.validated_model_run@1",
                {"run_id": run_id, "validated_candidate": candidate},
            ),
            dataset_available_at=dataset_available_at,
        )

    def _set_values(
        self,
        *,
        run_id: str,
        run_payload_hash: str | None,
        dataset_fingerprint: str | None,
        candidate_hash: str,
        validation_witness: str,
        dataset_available_at: datetime | None,
    ) -> None:
        if not run_id.strip():
            raise ValueError("run_id é obrigatório")
        if dataset_fingerprint is not None and not dataset_fingerprint.strip():
            raise ValueError("dataset_fingerprint não pode ser vazio")
        if dataset_available_at is not None and dataset_available_at.tzinfo is None:
            raise ValueError("dataset_available_at precisa de timezone")
        for name, value in (
            ("run_payload_hash", run_payload_hash),
            ("candidate_hash", candidate_hash),
            ("validation_witness", validation_witness),
        ):
            if value is not None and not _is_sha256(value):
                raise ValueError(f"{name} precisa ser SHA-256 hexadecimal")
        object.__setattr__(self, "run_id", run_id)
        object.__setattr__(self, "run_payload_hash", run_payload_hash)
        object.__setattr__(self, "dataset_fingerprint", dataset_fingerprint)
        object.__setattr__(self, "candidate_hash", candidate_hash)
        object.__setattr__(self, "validation_witness", validation_witness)
        object.__setattr__(self, "dataset_available_at", dataset_available_at)

    def reconciles_with(self, run: ModelRun) -> bool:
        try:
            expected = type(self).from_model_run(
                run,
                dataset_available_at=self.dataset_available_at,
            )
        except ValueError:
            return False
        return (
            self.run_id == expected.run_id
            and self.candidate_hash == expected.candidate_hash
            and self.validation_witness == expected.validation_witness
            and (
                self.run_payload_hash is None or self.run_payload_hash == expected.run_payload_hash
            )
            and (
                self.dataset_fingerprint is None
                or self.dataset_fingerprint == expected.dataset_fingerprint
            )
        )

    def with_dataset_available_at(self, value: datetime) -> ValidatedModelRunRef:
        return type(self)._from_persisted(
            run_id=self.run_id,
            run_payload_hash=self.run_payload_hash,
            dataset_fingerprint=self.dataset_fingerprint,
            candidate_hash=self.candidate_hash,
            validation_witness=self.validation_witness,
            dataset_available_at=value,
        )


def _content_hash(domain: str, value: object) -> str:
    document = {"domain": domain, "value": _canonical_value(value)}
    canonical = json.dumps(
        document,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _model_run_payload_hash(run: ModelRun) -> str:
    canonical = json.dumps(
        {
            "schema": "marko.model_run",
            "version": 1,
            "payload": _canonical_value(run),
        },
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _canonical_value(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _canonical_value(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return _canonical_value(value.value)
    if isinstance(value, dict):
        return {
            str(key): _canonical_value(item)
            for key, item in cast(dict[object, object], value).items()
        }
    if isinstance(value, (tuple, list)):
        return [_canonical_value(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"valor não serializável para hash: {type(value).__name__}")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


@dataclass(frozen=True, slots=True)
class TradeProposal:
    instrument_id: str
    side: TradeSide
    quantity: Decimal
    notional: Money
    estimated_cost: Money

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or self.quantity <= 0 or self.notional.amount <= 0:
            raise ValueError("trade exige instrumento, quantidade e notional positivos")
        self.notional._check_currency(self.estimated_cost)
        if self.estimated_cost.amount < 0:
            raise ValueError("custo estimado não pode ser negativo")


@dataclass(frozen=True, slots=True)
class DecisionAlternative:
    alternative_id: str
    trades: tuple[TradeProposal, ...]
    projected_weights: tuple[tuple[str, Decimal], ...]
    unallocated_cash: Money
    turnover: Decimal
    feasible: bool
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.alternative_id.strip():
            raise ValueError("alternative_id é obrigatório")
        identifiers = [identifier for identifier, _ in self.projected_weights]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("projected_weights contém IDs duplicados")
        if self.projected_weights:
            total = sum((weight for _, weight in self.projected_weights), Decimal(0))
            if abs(total - Decimal(1)) > Decimal("0.00000001"):
                raise ValueError("projected_weights precisam somar um")
        if not 0 <= self.turnover <= 1:
            raise ValueError("turnover precisa estar entre zero e um")


@dataclass(frozen=True, slots=True)
class DecisionPacket:
    packet_id: str
    created_at: datetime
    policy_id: str
    policy_version: int
    model_runs: tuple[ValidatedModelRunRef, ...]
    evidence_ids: tuple[str, ...]
    alternatives: tuple[DecisionAlternative, ...]
    shadow_request_id: str | None = None
    knowledge_cutoff: datetime | None = None

    def __post_init__(self) -> None:
        if (
            not self.packet_id.strip()
            or not self.policy_id.strip()
            or self.policy_version <= 0
            or self.created_at.tzinfo is None
        ):
            raise ValueError("identidade, política e created_at são obrigatórios")
        model_run_ids = self.model_run_ids
        if len(model_run_ids) != len(set(model_run_ids)):
            raise ValueError("model_run_ids duplicados")
        if len(self.evidence_ids) != len(set(self.evidence_ids)):
            raise ValueError("evidence_ids duplicados")
        if (self.shadow_request_id is None) != (self.knowledge_cutoff is None):
            raise ValueError("shadow_request_id e knowledge_cutoff precisam ser informados juntos")
        if self.shadow_request_id is not None and not self.shadow_request_id.strip():
            raise ValueError("shadow_request_id não pode ser vazio")
        if self.knowledge_cutoff is not None:
            if self.knowledge_cutoff.tzinfo is None:
                raise ValueError("knowledge_cutoff precisa de timezone")
            if self.knowledge_cutoff > self.created_at:
                raise ValueError("knowledge_cutoff não pode suceder created_at")
        identifiers = {alternative.alternative_id for alternative in self.alternatives}
        if "no_action" not in identifiers:
            raise ValueError("DecisionPacket exige a alternativa NO_ACTION")
        if len(identifiers) != len(self.alternatives):
            raise ValueError("alternative_id duplicado")

    @property
    def model_run_ids(self) -> tuple[str, ...]:
        return tuple(run.run_id for run in self.model_runs)


class CashFlowRebalancer:
    def __init__(self, estimated_cost_bps: Decimal = Decimal("0")) -> None:
        self.estimated_cost_bps = decimal_value(estimated_cost_bps)
        if self.estimated_cost_bps < 0:
            raise ValueError("estimated_cost_bps não pode ser negativo")

    def build_packet(
        self,
        *,
        packet_id: str,
        created_at: datetime,
        policy_id: str,
        policy_version: int,
        holdings: tuple[Holding, ...],
        targets: tuple[TargetAllocation, ...],
        cash: Money,
        cash_target: CashTarget,
        contribution: Money,
        model_runs: tuple[ValidatedModelRunRef, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        minimum_cash: Money | None = None,
        maximum_turnover: Decimal | None = None,
        shadow_request_id: str | None = None,
        knowledge_cutoff: datetime | None = None,
    ) -> DecisionPacket:
        if contribution.amount < 0:
            raise ValueError("contribution não pode ser negativa")
        contribution._check_currency(cash)
        holding_ids = [holding.instrument_id for holding in holdings]
        target_ids = [target.instrument_id for target in targets]
        if len(holding_ids) != len(set(holding_ids)):
            raise ValueError("holdings duplicados")
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("targets duplicados")
        holding_map = {holding.instrument_id: holding for holding in holdings}
        target_map = {target.instrument_id: target for target in targets}
        if set(holding_map) != set(target_map):
            raise ValueError("holdings e targets precisam cobrir os mesmos instrumentos")
        if sum((target.target_weight for target in targets), cash_target.target_weight) != Decimal(
            1
        ):
            raise ValueError("target weights precisam somar um")
        for holding in holdings:
            contribution._check_currency(holding.value)
        if minimum_cash is not None:
            contribution._check_currency(minimum_cash)
        if maximum_turnover is not None:
            maximum_turnover = decimal_value(maximum_turnover)
            if not 0 <= maximum_turnover <= 1:
                raise ValueError("maximum_turnover precisa estar entre zero e um")
        total_wealth = (
            sum((holding.value.amount for holding in holdings), cash.amount) + contribution.amount
        )
        if total_wealth <= 0:
            raise ValueError("patrimônio total precisa ser positivo")
        run_ids = tuple(run.run_id for run in model_runs)
        if len(run_ids) != len(set(run_ids)):
            raise ValueError("model runs duplicados")
        no_action = self._no_action(
            holdings, targets, cash, cash_target, contribution, minimum_cash
        )
        rebalance = self._cash_flow_only(
            holdings,
            targets,
            cash,
            cash_target,
            contribution,
            minimum_cash,
            maximum_turnover,
        )
        return DecisionPacket(
            packet_id,
            created_at,
            policy_id,
            policy_version,
            model_runs,
            evidence_ids,
            (no_action, rebalance),
            shadow_request_id,
            knowledge_cutoff,
        )

    def _no_action(
        self,
        holdings: tuple[Holding, ...],
        targets: tuple[TargetAllocation, ...],
        cash: Money,
        cash_target: CashTarget,
        contribution: Money,
        minimum_cash: Money | None,
    ) -> DecisionAlternative:
        values = {holding.instrument_id: holding.value.amount for holding in holdings}
        cash_after = cash + contribution
        total = sum(values.values(), cash_after.amount)
        weights = (
            *sorted((key, value / total) for key, value in values.items()),
            ("cash", cash_after.amount / total),
        )
        weight_map = dict(weights)
        reasons = ["aporte permanece em caixa"]
        feasible = True
        for target in targets:
            if weight_map[target.instrument_id] > target.maximum_weight + Decimal("0.00000001"):
                feasible = False
                reasons.append(f"{target.instrument_id} supera peso máximo")
        if weight_map["cash"] > cash_target.maximum_weight + Decimal("0.00000001"):
            feasible = False
            reasons.append("caixa supera peso máximo")
        if minimum_cash is not None and cash_after.amount < minimum_cash.amount:
            feasible = False
            reasons.append("violação de liquidez mínima")
        return DecisionAlternative(
            "no_action",
            (),
            weights,
            cash_after,
            Decimal(0),
            feasible,
            tuple(reasons),
        )

    def _cash_flow_only(
        self,
        holdings: tuple[Holding, ...],
        targets: tuple[TargetAllocation, ...],
        cash: Money,
        cash_target: CashTarget,
        contribution: Money,
        minimum_cash: Money | None,
        maximum_turnover: Decimal | None,
    ) -> DecisionAlternative:
        values = {holding.instrument_id: holding.value.amount for holding in holdings}
        holding_map = {holding.instrument_id: holding for holding in holdings}
        total = sum(values.values(), cash.amount) + contribution.amount
        cash_available = contribution.amount
        trades: list[TradeProposal] = []
        target_map = {target.instrument_id: target for target in targets}
        deficits = sorted(
            (
                (target.target_weight * total - values[target.instrument_id], target.instrument_id)
                for target in targets
            ),
            reverse=True,
        )
        for deficit, instrument_id in deficits:
            if deficit <= 0 or cash_available <= 0:
                continue
            holding = holding_map[instrument_id]
            target = target_map[instrument_id]
            room = max(target.maximum_weight * total - values[instrument_id], Decimal(0))
            notional = min(deficit, room, cash_available)
            quantity = notional / holding.price.amount
            if holding.whole_shares:
                quantity = quantity.quantize(Decimal(1), rounding=ROUND_DOWN)
                notional = quantity * holding.price.amount
            minimum = (
                holding.minimum_trade.amount if holding.minimum_trade is not None else Decimal(0)
            )
            if notional < minimum or quantity <= 0:
                continue
            cost = (notional * self.estimated_cost_bps / Decimal(10_000)).quantize(Decimal("0.01"))
            if notional + cost > cash_available:
                continue
            trade = TradeProposal(
                instrument_id,
                TradeSide.BUY,
                quantity,
                Money.of(notional, contribution.currency),
                Money.of(cost, contribution.currency),
            )
            trades.append(trade)
            values[instrument_id] += notional
            cash_available -= notional + cost
        unallocated = Money.of(cash.amount + cash_available, contribution.currency)
        denominator = sum(values.values(), unallocated.amount)
        weights = (
            *sorted((key, value / denominator) for key, value in values.items()),
            ("cash", unallocated.amount / denominator),
        )
        turnover_value = sum((trade.notional.amount for trade in trades), Decimal(0))
        turnover_ratio = turnover_value / denominator / Decimal(2)
        reasons = ["nenhuma venda", "aporte direcionado aos maiores déficits"]
        feasible = True
        if minimum_cash is not None and unallocated.amount < minimum_cash.amount:
            feasible = False
            reasons.append("violação de liquidez mínima")
        if maximum_turnover is not None and turnover_ratio > maximum_turnover:
            feasible = False
            reasons.append("violação de turnover máximo")
        weight_map = dict(weights)
        for target in targets:
            if weight_map[target.instrument_id] > target.maximum_weight + Decimal("0.00000001"):
                feasible = False
                reasons.append(f"{target.instrument_id} supera peso máximo")
        if weight_map["cash"] > cash_target.maximum_weight + Decimal("0.00000001"):
            feasible = False
            reasons.append("caixa supera peso máximo")
        return DecisionAlternative(
            "cash_flow_only",
            tuple(trades),
            weights,
            unallocated,
            turnover_ratio,
            feasible,
            tuple(reasons),
        )
