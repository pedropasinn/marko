from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from marko.activities import ActivityKind
from marko.ledger import Ledger
from marko.money import Money


class CostBasisMethod(StrEnum):
    FIFO = "fifo"
    AVERAGE = "average"


class UnknownCostBasisError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class TaxLot:
    acquired_at: datetime
    quantity: Decimal
    total_cost: Money
    source_activity_id: str

    @property
    def unit_cost(self) -> Decimal:
        return self.total_cost.amount / self.quantity


@dataclass(frozen=True, slots=True)
class RealizedDisposal:
    activity_id: str
    disposed_at: datetime
    quantity: Decimal
    proceeds: Money
    allocated_cost: Money

    @property
    def realized_gain(self) -> Money:
        return self.proceeds - self.allocated_cost


@dataclass(frozen=True, slots=True)
class TaxLotReport:
    method: CostBasisMethod
    open_lots: tuple[TaxLot, ...]
    disposals: tuple[RealizedDisposal, ...]


def build_tax_lots(
    ledger: Ledger,
    account_id: str,
    instrument_id: str,
    method: CostBasisMethod = CostBasisMethod.FIFO,
    as_of: datetime | None = None,
) -> TaxLotReport:
    lots: list[TaxLot] = []
    disposals: list[RealizedDisposal] = []
    activities = ledger.activities(as_of)
    reversed_ids = {
        activity.correction_of
        for activity in activities
        if activity.is_reversal and activity.correction_of is not None
    }
    for activity in activities:
        if activity.is_reversal or activity.activity_id in reversed_ids:
            continue
        if activity.account_id != account_id or activity.instrument_id != instrument_id:
            continue
        if activity.kind is ActivityKind.SPLIT:
            assert activity.ratio is not None
            factor = activity.ratio
            lots = [
                TaxLot(
                    lot.acquired_at, lot.quantity * factor, lot.total_cost, lot.source_activity_id
                )
                for lot in lots
            ]
            continue
        if activity.kind is ActivityKind.BUY:
            assert activity.quantity is not None and activity.gross_amount is not None
            fee = activity.fee or Money.zero(activity.gross_amount.currency)
            tax = activity.tax or Money.zero(activity.gross_amount.currency)
            cost = activity.gross_amount + fee + tax
            lots.append(
                TaxLot(activity.effective_at, activity.quantity, cost, activity.activity_id)
            )
            if method is CostBasisMethod.AVERAGE:
                lots = [_merge_lots(lots)]
            continue
        if activity.kind in {
            ActivityKind.DELIVERY_IN,
            ActivityKind.POSITION_TRANSFER_IN,
            ActivityKind.SPINOFF,
        }:
            if activity.cost_basis is None or activity.quantity is None:
                raise UnknownCostBasisError(f"base desconhecida em {activity.activity_id}")
            lots.append(
                TaxLot(
                    activity.effective_at,
                    activity.quantity,
                    activity.cost_basis,
                    activity.activity_id,
                )
            )
            if method is CostBasisMethod.AVERAGE:
                lots = [_merge_lots(lots)]
            continue
        if activity.kind is ActivityKind.SELL:
            assert activity.quantity is not None and activity.gross_amount is not None
            fee = activity.fee or Money.zero(activity.gross_amount.currency)
            tax = activity.tax or Money.zero(activity.gross_amount.currency)
            proceeds = activity.gross_amount - fee - tax
            allocated, lots = _consume(lots, activity.quantity, activity.gross_amount.currency)
            disposals.append(
                RealizedDisposal(
                    activity.activity_id,
                    activity.effective_at,
                    activity.quantity,
                    proceeds,
                    allocated,
                )
            )
            continue
        if activity.kind is ActivityKind.AMORTIZATION:
            assert activity.gross_amount is not None
            lots = _reduce_basis(lots, activity.gross_amount)
            continue
        if activity.kind in {
            ActivityKind.DELIVERY_OUT,
            ActivityKind.POSITION_TRANSFER_OUT,
        }:
            assert activity.quantity is not None
            currency = lots[0].total_cost.currency if lots else "BRL"
            _, lots = _consume(lots, activity.quantity, currency)
    return TaxLotReport(method, tuple(lots), tuple(disposals))


def _merge_lots(lots: list[TaxLot]) -> TaxLot:
    first = lots[0]
    quantity = sum((lot.quantity for lot in lots), Decimal(0))
    total = Money.zero(first.total_cost.currency)
    for lot in lots:
        total += lot.total_cost
    return TaxLot(first.acquired_at, quantity, total, first.source_activity_id)


def _consume(lots: list[TaxLot], quantity: Decimal, currency: str) -> tuple[Money, list[TaxLot]]:
    remaining = quantity
    allocated = Money.zero(currency)
    open_lots: list[TaxLot] = []
    for lot in lots:
        if remaining <= 0:
            open_lots.append(lot)
            continue
        consumed = min(remaining, lot.quantity)
        lot.total_cost._check_currency(allocated)
        cost = Money.of(lot.unit_cost * consumed, currency)
        allocated += cost
        leftover = lot.quantity - consumed
        if leftover > 0:
            open_lots.append(
                TaxLot(
                    lot.acquired_at,
                    leftover,
                    lot.total_cost - cost,
                    lot.source_activity_id,
                )
            )
        remaining -= consumed
    if remaining > 0:
        raise UnknownCostBasisError("venda supera a quantidade com base de custo conhecida")
    return allocated, open_lots


def _reduce_basis(lots: list[TaxLot], amount: Money) -> list[TaxLot]:
    total = Money.zero(amount.currency)
    for lot in lots:
        total += lot.total_cost
    if amount.amount > total.amount:
        raise UnknownCostBasisError("amortização supera a base de custo aberta")
    remaining = amount
    reduced: list[TaxLot] = []
    for index, lot in enumerate(lots):
        if index == len(lots) - 1:
            reduction = remaining
        else:
            reduction = Money.of(
                amount.amount * lot.total_cost.amount / total.amount,
                amount.currency,
            )
            remaining -= reduction
        reduced.append(
            TaxLot(
                lot.acquired_at,
                lot.quantity,
                lot.total_cost - reduction,
                lot.source_activity_id,
            )
        )
    return reduced
