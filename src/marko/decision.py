from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

from marko.money import Money, decimal_value
from marko.portfolio_lab import ValidatedPortfolioCandidate


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


@dataclass(frozen=True, slots=True)
class ValidatedModelRunRef:
    run_id: str
    candidate: ValidatedPortfolioCandidate

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id é obrigatório")


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
