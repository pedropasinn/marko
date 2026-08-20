from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from marko.liabilities import (
    Compounding,
    DayCountConvention,
    InterestRounding,
    InterestTerms,
    Liability,
    LiabilityCashflow,
    PaymentFrequency,
)
from marko.money import Money, decimal_value
from marko.policy import InvestmentPolicy, Universe, UniverseItem


@dataclass(frozen=True, slots=True)
class PersonalCase:
    base_currency: str
    principal: Money
    creditor: str
    monthly_contribution: Money
    originated_on: date | None
    maturity_date: date | None
    interest_terms: InterestTerms | None
    callable_early: bool | None
    minimum_liquidity: Money | None
    maximum_drawdown: Decimal | None
    brokers: tuple[str, ...]
    available_instruments: tuple[str, ...]
    tax_residency: str | None

    def __post_init__(self) -> None:
        currency = self.base_currency.upper()
        if self.principal.currency != currency or self.monthly_contribution.currency != currency:
            raise ValueError("principal e aporte precisam usar a moeda-base")
        if self.principal.amount <= 0 or self.monthly_contribution.amount < 0:
            raise ValueError("principal precisa ser positivo e aporte não negativo")
        if self.minimum_liquidity is not None and self.minimum_liquidity.currency != currency:
            raise ValueError("minimum_liquidity precisa usar a moeda-base")
        if self.maximum_drawdown is not None and not 0 <= self.maximum_drawdown <= 1:
            raise ValueError("maximum_drawdown precisa estar entre zero e um")
        object.__setattr__(self, "base_currency", currency)

    def readiness_issues(self) -> tuple[str, ...]:
        issues: list[str] = []
        required = {
            "originated_on": self.originated_on,
            "maturity_date": self.maturity_date,
            "interest_terms": self.interest_terms,
            "callable_early": self.callable_early,
            "minimum_liquidity": self.minimum_liquidity,
            "maximum_drawdown": self.maximum_drawdown,
            "tax_residency": self.tax_residency,
        }
        issues.extend(f"campo ausente: {name}" for name, value in required.items() if value is None)
        if not self.brokers:
            issues.append("campo ausente: brokers")
        if not self.available_instruments:
            issues.append("campo ausente: available_instruments")
        if (
            self.originated_on is not None
            and self.maturity_date is not None
            and self.maturity_date <= self.originated_on
        ):
            issues.append("maturity_date precisa suceder originated_on")
        return tuple(issues)

    def to_liability(self) -> Liability:
        issues = self.readiness_issues()
        if issues:
            raise ValueError("caso incompleto: " + "; ".join(issues))
        assert self.originated_on is not None
        assert self.maturity_date is not None
        assert self.callable_early is not None
        amount_due = self._amount_due()
        return Liability(
            liability_id="family-loan",
            creditor=self.creditor,
            initial_principal=self.principal,
            originated_on=self.originated_on,
            maturity_date=self.maturity_date,
            cashflows=(
                LiabilityCashflow(
                    "family-loan-principal",
                    self.maturity_date,
                    amount_due,
                    "Principal e juros conforme InterestTerms",
                ),
            ),
            callable_early=self.callable_early,
        )

    def to_policy(self, approved_at: datetime, version: int = 1) -> InvestmentPolicy:
        issues = self.readiness_issues()
        if issues:
            raise ValueError("caso incompleto: " + "; ".join(issues))
        assert self.originated_on is not None
        assert self.maturity_date is not None
        assert self.minimum_liquidity is not None
        assert self.maximum_drawdown is not None
        return InvestmentPolicy(
            "personal-ips",
            version,
            self.originated_on,
            approved_at,
            self.base_currency,
            self.maturity_date,
            self.minimum_liquidity,
            self.maximum_drawdown,
            ("family-loan",),
            False,
        )

    def to_universe(self, as_of: date, version: int = 1) -> Universe:
        issues = self.readiness_issues()
        if issues:
            raise ValueError("caso incompleto: " + "; ".join(issues))
        return Universe(
            "personal-universe",
            version,
            as_of,
            tuple(UniverseItem(instrument, as_of) for instrument in self.available_instruments),
        )

    def _amount_due(self) -> Money:
        assert self.originated_on is not None
        assert self.maturity_date is not None
        assert self.interest_terms is not None
        return self.interest_terms.amount_due(
            self.principal, self.originated_on, self.maturity_date
        )


def load_case(path: str | Path) -> PersonalCase:
    with Path(path).open("rb") as source:
        document = tomllib.load(source)
    case = _mapping(document, "case")
    liability = _mapping(document, "liability")
    interest = _optional_mapping(liability, "interest")
    policy = _mapping(document, "policy")
    access = _mapping(document, "access")
    currency = str(case.get("base_currency", "BRL"))
    return PersonalCase(
        base_currency=currency,
        principal=Money.of(str(liability["principal"]), currency),
        creditor=str(liability["creditor"]),
        monthly_contribution=Money.of(str(case["monthly_contribution"]), currency),
        originated_on=_optional_date(liability.get("originated_on")),
        maturity_date=_optional_date(liability.get("maturity_date")),
        interest_terms=_optional_interest_terms(interest),
        callable_early=_optional_bool(liability.get("callable_early")),
        minimum_liquidity=_optional_money(policy.get("minimum_liquidity"), currency),
        maximum_drawdown=_optional_decimal(policy.get("maximum_drawdown")),
        brokers=tuple(str(value) for value in access.get("brokers", [])),
        available_instruments=tuple(
            str(value) for value in access.get("available_instruments", [])
        ),
        tax_residency=_optional_text(case.get("tax_residency")),
    )


def _mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"seção TOML ausente: {key}")
    return value


def _optional_text(value: object) -> str | None:
    text = str(value).strip() if value is not None else ""
    return text or None


def _optional_date(value: object) -> date | None:
    text = _optional_text(value)
    return date.fromisoformat(text) if text else None


def _optional_bool(value: object) -> bool | None:
    if value in (True, False):
        return bool(value)
    text = _optional_text(value)
    if text is None:
        return None
    if text.lower() in {"true", "yes", "sim"}:
        return True
    if text.lower() in {"false", "no", "não", "nao"}:
        return False
    raise ValueError(f"booleano inválido: {value}")


def _optional_money(value: object, currency: str) -> Money | None:
    text = _optional_text(value)
    return Money.of(text, currency) if text else None


def _optional_decimal(value: object) -> Decimal | None:
    text = _optional_text(value)
    return decimal_value(text) if text else None


def _optional_mapping(document: dict[str, Any], key: str) -> dict[str, Any] | None:
    value = document.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"seção TOML inválida: {key}")
    return value


def _optional_interest_terms(document: dict[str, Any] | None) -> InterestTerms | None:
    if document is None or not any(_optional_text(value) for value in document.values()):
        return None
    required = (
        "annual_rate",
        "compounding",
        "day_count_convention",
        "payment_frequency",
        "rounding_rule",
    )
    missing = [key for key in required if not _optional_text(document.get(key))]
    if missing:
        raise ValueError("termos de juros incompletos: " + ", ".join(missing))
    return InterestTerms(
        decimal_value(str(document["annual_rate"])),
        Compounding(str(document["compounding"])),
        DayCountConvention(str(document["day_count_convention"])),
        PaymentFrequency(str(document["payment_frequency"])),
        InterestRounding(str(document["rounding_rule"])),
    )
