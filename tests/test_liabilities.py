from datetime import date
from decimal import Decimal

import pytest

from marko.liabilities import Liability, LiabilityCashflow, funding_ratio, shortfall
from marko.money import CurrencyMismatchError, Money


def loan() -> Liability:
    return Liability(
        liability_id="loan-synthetic",
        creditor="Credor sintético",
        initial_principal=Money.of("25000", "BRL"),
        originated_on=date(2026, 8, 20),
        maturity_date=date(2030, 8, 20),
        cashflows=(
            LiabilityCashflow(
                "principal", date(2030, 8, 20), Money.of("25000", "BRL"), "Principal"
            ),
        ),
        callable_early=True,
    )


def test_liability_remains_outstanding_until_settlement() -> None:
    assert loan().outstanding_on(date(2031, 1, 1)) == Money.of("25000", "BRL")


def test_funding_ratio_and_shortfall() -> None:
    assets = Money.of("21000", "BRL")
    obligation = loan().outstanding_on(date(2028, 1, 1))
    assert funding_ratio(assets, obligation) == Decimal("0.84")
    assert shortfall(assets, obligation) == Money.of("4000", "BRL")
    assert shortfall(Money.of("30000", "BRL"), obligation) == Money.zero("BRL")


def test_liability_metrics_reject_cross_currency() -> None:
    with pytest.raises(CurrencyMismatchError):
        funding_ratio(Money.of(1, "USD"), Money.of(1, "BRL"))
