from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from marko.activities import Activity, ActivityKind
from marko.ledger import DuplicateActivityError, Ledger
from marko.money import Money

T0 = datetime(2026, 8, 20, 12, tzinfo=UTC)


def activity(activity_id: str, kind: ActivityKind, **kwargs: object) -> Activity:
    return Activity(
        activity_id=activity_id,
        kind=kind,
        account_id="broker",
        effective_at=kwargs.pop("effective_at", T0),
        recorded_at=kwargs.pop("recorded_at", T0 + timedelta(minutes=1)),
        **kwargs,
    )


def test_trade_and_cash_activities_close_exactly() -> None:
    ledger = Ledger()
    ledger.append(activity("deposit", ActivityKind.DEPOSIT, gross_amount=Money.of("1000", "BRL")))
    ledger.append(
        activity(
            "buy",
            ActivityKind.BUY,
            gross_amount=Money.of("600", "BRL"),
            fee=Money.of("2.50", "BRL"),
            tax=Money.of("0.50", "BRL"),
            instrument_id="ETF",
            quantity=Decimal("10"),
        )
    )
    ledger.append(
        activity(
            "sell",
            ActivityKind.SELL,
            gross_amount=Money.of("130", "BRL"),
            fee=Money.of("1", "BRL"),
            tax=Money.of("2", "BRL"),
            instrument_id="ETF",
            quantity=Decimal("2"),
        )
    )
    ledger.append(activity("dividend", ActivityKind.DIVIDEND, gross_amount=Money.of("8", "BRL")))
    assert ledger.cash_balance("broker", "BRL") == Money.of("532", "BRL")
    assert ledger.position("broker", "ETF") == Decimal("8")


def test_duplicate_is_rejected_without_mutation() -> None:
    event = activity("same", ActivityKind.DEPOSIT, gross_amount=Money.of(1, "BRL"))
    ledger = Ledger([event])
    with pytest.raises(DuplicateActivityError):
        ledger.append(event)
    assert len(ledger) == 1


def test_ledger_has_stable_effective_order() -> None:
    later = activity(
        "b",
        ActivityKind.DEPOSIT,
        gross_amount=Money.of(1, "BRL"),
        effective_at=T0 + timedelta(days=1),
        recorded_at=T0 + timedelta(days=1, minutes=1),
    )
    earlier = activity("a", ActivityKind.DEPOSIT, gross_amount=Money.of(1, "BRL"))
    ledger = Ledger([later, earlier])
    assert [event.activity_id for event in ledger.activities()] == ["a", "b"]


def test_delivery_moves_position_without_cash() -> None:
    event = activity(
        "delivery",
        ActivityKind.DELIVERY_IN,
        instrument_id="BOND",
        quantity=Decimal("1.234"),
    )
    ledger = Ledger([event])
    assert ledger.position("broker", "BOND") == Decimal("1.234")
    assert ledger.cash_balance("broker", "BRL") == Money.zero("BRL")


def test_activity_requires_timezone_and_positive_amount() -> None:
    with pytest.raises(ValueError):
        Activity(
            "bad",
            ActivityKind.DEPOSIT,
            "broker",
            datetime(2026, 1, 1),
            datetime(2026, 1, 1),
            Money.of(1, "BRL"),
        )
    with pytest.raises(ValueError):
        activity("bad-amount", ActivityKind.FEE, gross_amount=Money.of(0, "BRL"))
