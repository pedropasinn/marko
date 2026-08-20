from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from itertools import pairwise
from math import isfinite

from marko.activities import ActivityKind
from marko.ledger import Ledger
from marko.money import Money


@dataclass(frozen=True, slots=True)
class PerformancePoint:
    at: datetime
    value: Money
    external_flow: Money

    def __post_init__(self) -> None:
        self.value._check_currency(self.external_flow)
        if self.at.tzinfo is None:
            raise ValueError("at precisa de timezone")


def time_weighted_return(points: tuple[PerformancePoint, ...]) -> Decimal:
    if len(points) < 2:
        raise ValueError("TWR exige ao menos dois pontos")
    ordered = tuple(sorted(points, key=lambda point: point.at))
    growth = Decimal(1)
    for previous, current in pairwise(ordered):
        previous.value._check_currency(current.value)
        previous.value._check_currency(current.external_flow)
        if previous.value.amount == 0:
            raise ValueError("não é possível calcular retorno após patrimônio zero")
        period_growth = (
            current.value.amount - current.external_flow.amount
        ) / previous.value.amount
        growth *= period_growth
    return growth - Decimal(1)


@dataclass(frozen=True, slots=True)
class DatedCashFlow:
    on: date
    amount: Money


def xirr(cashflows: tuple[DatedCashFlow, ...], tolerance: float = 1e-10) -> Decimal:
    if len(cashflows) < 2:
        raise ValueError("XIRR exige ao menos dois fluxos")
    currencies = {cashflow.amount.currency for cashflow in cashflows}
    if len(currencies) != 1:
        raise ValueError("XIRR exige uma única moeda")
    amounts = [float(cashflow.amount.amount) for cashflow in cashflows]
    if not any(amount < 0 for amount in amounts) or not any(amount > 0 for amount in amounts):
        raise ValueError("XIRR exige fluxos positivos e negativos")
    start = min(cashflow.on for cashflow in cashflows)

    def npv(rate: float) -> float:
        return float(
            sum(
                float(cashflow.amount.amount)
                / ((1.0 + rate) ** ((cashflow.on - start).days / 365.0))
                for cashflow in cashflows
            )
        )

    lower = -0.999999
    upper = 1.0
    lower_value = npv(lower)
    upper_value = npv(upper)
    while lower_value * upper_value > 0 and upper < 1_000_000:
        upper *= 2
        upper_value = npv(upper)
    if lower_value * upper_value > 0:
        raise ValueError("os fluxos não possuem uma raiz XIRR isolável")
    for _ in range(256):
        midpoint = (lower + upper) / 2
        value = npv(midpoint)
        if not isfinite(value):
            raise ValueError("XIRR numericamente instável")
        if abs(value) <= tolerance:
            return Decimal(str(midpoint))
        if lower_value * value <= 0:
            upper = midpoint
        else:
            lower = midpoint
            lower_value = value
    return Decimal(str((lower + upper) / 2))


@dataclass(frozen=True, slots=True)
class DrawdownResult:
    maximum_drawdown: Decimal
    peak_at: datetime
    trough_at: datetime
    recovered_at: datetime | None


def maximum_drawdown(points: tuple[tuple[datetime, Money], ...]) -> DrawdownResult:
    if not points:
        raise ValueError("drawdown exige pontos")
    ordered = tuple(sorted(points, key=lambda point: point[0]))
    peak_at, peak_value = ordered[0]
    trough_at = peak_at
    max_drawdown = Decimal(0)
    max_peak_at = peak_at
    recovered_at: datetime | None = None
    active_peak_value = peak_value
    active_peak_at = peak_at
    for at, value in ordered[1:]:
        active_peak_value._check_currency(value)
        if value.amount >= active_peak_value.amount:
            if max_drawdown < 0 and recovered_at is None and active_peak_at == max_peak_at:
                recovered_at = at
            active_peak_value = value
            active_peak_at = at
            continue
        if active_peak_value.amount == 0:
            continue
        drawdown = value.amount / active_peak_value.amount - Decimal(1)
        if drawdown < max_drawdown:
            max_drawdown = drawdown
            max_peak_at = active_peak_at
            trough_at = at
            recovered_at = None
    return DrawdownResult(max_drawdown, max_peak_at, trough_at, recovered_at)


@dataclass(frozen=True, slots=True)
class CashAttribution:
    fees: Money
    taxes: Money
    income: Money


def cash_attribution(ledger: Ledger, currency: str) -> CashAttribution:
    fees = Money.zero(currency)
    taxes = Money.zero(currency)
    income = Money.zero(currency)
    for activity in ledger.activities():
        if activity.fee is not None and activity.fee.currency == currency:
            fees += activity.fee
        if activity.tax is not None and activity.tax.currency == currency:
            taxes += activity.tax
        if activity.gross_amount is None or activity.gross_amount.currency != currency:
            continue
        if activity.kind is ActivityKind.FEE:
            fees += activity.gross_amount
        elif activity.kind is ActivityKind.TAX:
            taxes += activity.gross_amount
        elif activity.kind in {
            ActivityKind.DIVIDEND,
            ActivityKind.INTEREST,
            ActivityKind.AMORTIZATION,
        }:
            income += activity.gross_amount
    return CashAttribution(fees, taxes, income)
