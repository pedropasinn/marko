from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from marko.money import CurrencyMismatchError, Money


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
    "CurrencyMismatchError",
    "Liability",
    "LiabilityCashflow",
    "funding_ratio",
    "shortfall",
]
