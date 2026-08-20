from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_EVEN, Decimal
from enum import StrEnum

from marko.money import CurrencyMismatchError, Money


class Compounding(StrEnum):
    NONE = "none"
    SIMPLE = "simple"
    ANNUAL = "annual"


class DayCountConvention(StrEnum):
    ACTUAL_365 = "actual/365"


class PaymentFrequency(StrEnum):
    AT_MATURITY = "at_maturity"


class InterestRounding(StrEnum):
    HALF_EVEN = "half_even"


@dataclass(frozen=True, slots=True)
class InterestTerms:
    annual_rate: Decimal
    compounding: Compounding
    day_count_convention: DayCountConvention
    payment_frequency: PaymentFrequency
    rounding_rule: InterestRounding

    def __post_init__(self) -> None:
        rate = Decimal(str(self.annual_rate))
        if not rate.is_finite() or rate <= Decimal(-1):
            raise ValueError("annual_rate inválida")
        if self.compounding is Compounding.NONE and rate != 0:
            raise ValueError("compounding none exige taxa zero")
        object.__setattr__(self, "annual_rate", rate)

    def amount_due(self, principal: Money, originated_on: date, maturity_date: date) -> Money:
        days = Decimal((maturity_date - originated_on).days)
        years = days / Decimal(365)
        if self.compounding is Compounding.NONE:
            factor = Decimal(1)
        elif self.compounding is Compounding.SIMPLE:
            factor = Decimal(1) + self.annual_rate * years
        else:
            factor = (Decimal(1) + self.annual_rate) ** years
        amount = (principal.amount * factor).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
        return Money.of(amount, principal.currency)


@dataclass(frozen=True, slots=True)
class LiabilityCashflow:
    cashflow_id: str
    due_on: date
    amount: Money
    description: str
    settled_on: date | None = None

    def __post_init__(self) -> None:
        if not self.cashflow_id.strip() or not self.description.strip():
            raise ValueError("cashflow_id e description são obrigatórios")
        if self.amount.amount <= 0:
            raise ValueError("o fluxo do passivo precisa ser positivo")


@dataclass(frozen=True, slots=True)
class Liability:
    liability_id: str
    creditor: str
    initial_principal: Money
    originated_on: date
    maturity_date: date
    cashflows: tuple[LiabilityCashflow, ...]
    callable_early: bool = False

    def __post_init__(self) -> None:
        if not self.liability_id.strip() or not self.creditor.strip():
            raise ValueError("liability_id e creditor são obrigatórios")
        if self.initial_principal.amount <= 0:
            raise ValueError("initial_principal precisa ser positivo")
        if self.maturity_date < self.originated_on:
            raise ValueError("maturity_date não pode preceder originated_on")
        identifiers = [cashflow.cashflow_id for cashflow in self.cashflows]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("cashflows duplicados")
        for cashflow in self.cashflows:
            self.initial_principal._check_currency(cashflow.amount)
            if cashflow.due_on < self.originated_on:
                raise ValueError("cashflow não pode preceder a origem")

    def outstanding_on(self, as_of: date) -> Money:
        outstanding = Money.zero(self.initial_principal.currency)
        for cashflow in self.cashflows:
            if cashflow.settled_on is None or cashflow.settled_on > as_of:
                outstanding += cashflow.amount
        return outstanding


def funding_ratio(assets: Money, obligation: Money) -> Decimal | None:
    assets._check_currency(obligation)
    if obligation.amount == 0:
        return None
    return assets.amount / obligation.amount


def shortfall(assets: Money, obligation: Money) -> Money:
    assets._check_currency(obligation)
    gap = obligation.amount - assets.amount
    return Money.of(max(gap, Decimal(0)), obligation.currency)


__all__ = [
    "Compounding",
    "CurrencyMismatchError",
    "DayCountConvention",
    "InterestRounding",
    "InterestTerms",
    "Liability",
    "LiabilityCashflow",
    "PaymentFrequency",
    "funding_ratio",
    "shortfall",
]
