from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum

from marko.money import Money, decimal_value


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
        target = decimal_value(self.target_weight)
        maximum = decimal_value(self.maximum_weight)
        if not 0 <= target <= maximum <= 1:
            raise ValueError("pesos-alvo inválidos")
        object.__setattr__(self, "target_weight", target)
        object.__setattr__(self, "maximum_weight", maximum)


@dataclass(frozen=True, slots=True)
class TradeProposal:
    instrument_id: str
    side: TradeSide
    quantity: Decimal
    notional: Money
    estimated_cost: Money


@dataclass(frozen=True, slots=True)
class DecisionAlternative:
    alternative_id: str
    trades: tuple[TradeProposal, ...]
    projected_weights: tuple[tuple[str, Decimal], ...]
    unallocated_cash: Money
    turnover: Decimal
    feasible: bool
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DecisionPacket:
    packet_id: str
    created_at: datetime
    policy_id: str
    policy_version: int
    model_run_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    alternatives: tuple[DecisionAlternative, ...]

    def __post_init__(self) -> None:
        if self.created_at.tzinfo is None:
            raise ValueError("created_at precisa de timezone")
        identifiers = {alternative.alternative_id for alternative in self.alternatives}
        if "no_action" not in identifiers:
            raise ValueError("DecisionPacket exige a alternativa NO_ACTION")
        if len(identifiers) != len(self.alternatives):
            raise ValueError("alternative_id duplicado")


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
        contribution: Money,
        model_run_ids: tuple[str, ...] = (),
        evidence_ids: tuple[str, ...] = (),
        minimum_cash: Money | None = None,
        maximum_turnover: Decimal | None = None,
    ) -> DecisionPacket:
        if contribution.amount < 0:
            raise ValueError("contribution não pode ser negativa")
        holding_map = {holding.instrument_id: holding for holding in holdings}
        target_map = {target.instrument_id: target for target in targets}
        if set(holding_map) != set(target_map):
            raise ValueError("holdings e targets precisam cobrir os mesmos instrumentos")
        if sum((target.target_weight for target in targets), Decimal(0)) != Decimal(1):
            raise ValueError("target weights precisam somar um")
        for holding in holdings:
            contribution._check_currency(holding.value)
        if minimum_cash is not None:
            contribution._check_currency(minimum_cash)
        if maximum_turnover is not None:
            maximum_turnover = decimal_value(maximum_turnover)
            if not 0 <= maximum_turnover <= 1:
                raise ValueError("maximum_turnover precisa estar entre zero e um")
        no_action = self._no_action(holdings, targets, contribution, minimum_cash)
        rebalance = self._cash_flow_only(
            holdings,
            targets,
            contribution,
            minimum_cash,
            maximum_turnover,
        )
        return DecisionPacket(
            packet_id,
            created_at,
            policy_id,
            policy_version,
            model_run_ids,
            evidence_ids,
            (no_action, rebalance),
        )

    def _no_action(
        self,
        holdings: tuple[Holding, ...],
        targets: tuple[TargetAllocation, ...],
        contribution: Money,
        minimum_cash: Money | None,
    ) -> DecisionAlternative:
        values = {holding.instrument_id: holding.value.amount for holding in holdings}
        cash_id = "CASH" if "CASH" in values else None
        if cash_id is not None:
            values[cash_id] += contribution.amount
            unallocated = Money.zero(contribution.currency)
        else:
            unallocated = contribution
        total = sum(values.values(), Decimal(0)) + unallocated.amount
        weights = tuple(sorted((key, value / total) for key, value in values.items()))
        weight_map = dict(weights)
        reasons = ["aporte permanece em caixa"]
        feasible = True
        for target in targets:
            if weight_map[target.instrument_id] > target.maximum_weight + Decimal("0.00000001"):
                feasible = False
                reasons.append(f"{target.instrument_id} supera peso máximo")
        cash_after = values.get("CASH", Decimal(0)) + unallocated.amount
        if minimum_cash is not None and cash_after < minimum_cash.amount:
            feasible = False
            reasons.append("violação de liquidez mínima")
        return DecisionAlternative(
            "no_action",
            (),
            weights,
            unallocated,
            Decimal(0),
            feasible,
            tuple(reasons),
        )

    def _cash_flow_only(
        self,
        holdings: tuple[Holding, ...],
        targets: tuple[TargetAllocation, ...],
        contribution: Money,
        minimum_cash: Money | None,
        maximum_turnover: Decimal | None,
    ) -> DecisionAlternative:
        values = {holding.instrument_id: holding.value.amount for holding in holdings}
        holding_map = {holding.instrument_id: holding for holding in holdings}
        total = sum(values.values(), Decimal(0)) + contribution.amount
        cash_available = contribution.amount
        trades: list[TradeProposal] = []
        target_map = {target.instrument_id: target for target in targets}
        deficits = sorted(
            (
                (target.target_weight * total - values[target.instrument_id], target.instrument_id)
                for target in targets
                if target.instrument_id != "CASH"
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
        if "CASH" in values:
            values["CASH"] += cash_available
            unallocated = Money.zero(contribution.currency)
        else:
            unallocated = Money.of(cash_available, contribution.currency)
        denominator = sum(values.values(), Decimal(0)) + unallocated.amount
        weights = tuple(sorted((key, value / denominator) for key, value in values.items()))
        turnover_value = sum((trade.notional.amount for trade in trades), Decimal(0))
        turnover_ratio = turnover_value / denominator / Decimal(2)
        reasons = ["nenhuma venda", "aporte direcionado aos maiores déficits"]
        feasible = True
        cash_after = values.get("CASH", Decimal(0)) + unallocated.amount
        if minimum_cash is not None and cash_after < minimum_cash.amount:
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
        return DecisionAlternative(
            "cash_flow_only",
            tuple(trades),
            weights,
            unallocated,
            turnover_ratio,
            feasible,
            tuple(reasons),
        )
