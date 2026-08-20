from decimal import Decimal

import pytest

from marko.money import CurrencyMismatchError, Money


def test_money_quantizes_brl_with_bankers_rounding() -> None:
    assert Money.of("10.125", "brl").amount == Decimal("10.12")
    assert Money.of("10.135", "BRL").amount == Decimal("10.14")


def test_money_arithmetic_preserves_currency() -> None:
    total = Money.of("10.10", "BRL") + Money.of("2.35", "BRL")
    assert total == Money.of("12.45", "BRL")
    assert total - Money.of("0.45", "BRL") == Money.of("12.00", "BRL")


def test_money_rejects_cross_currency_arithmetic() -> None:
    with pytest.raises(CurrencyMismatchError):
        _ = Money.of(1, "BRL") + Money.of(1, "USD")


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity"])
def test_money_rejects_non_finite_values(value: str) -> None:
    with pytest.raises(ValueError):
        Money.of(value, "BRL")


def test_money_rejects_unregistered_currency_and_respects_three_decimals() -> None:
    with pytest.raises(ValueError, match="não cadastrada"):
        Money.of("1", "XYZ")
    assert Money.of("1.2345", "KWD").amount == Decimal("1.234")
