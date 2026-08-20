from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from marko.activities import Activity, ActivityKind
from marko.analytics import (
    DatedCashFlow,
    PerformancePoint,
    cash_attribution,
    maximum_drawdown,
    time_weighted_return,
    xirr,
)
from marko.ledger import Ledger
from marko.money import Money

T0 = datetime(2026, 1, 1, tzinfo=UTC)


def test_twr_removes_external_contribution() -> None:
    points = (
        PerformancePoint(T0, Money.of("100", "BRL"), Money.zero("BRL")),
        PerformancePoint(T0 + timedelta(days=1), Money.of("120", "BRL"), Money.of("10", "BRL")),
        PerformancePoint(T0 + timedelta(days=2), Money.of("121", "BRL"), Money.zero("BRL")),
    )
    assert time_weighted_return(points).quantize(Decimal("0.0001")) == Decimal("0.1092")


def test_xirr_for_one_year_doubles() -> None:
    result = xirr(
        (
            DatedCashFlow(date(2025, 1, 1), Money.of("-100", "BRL")),
            DatedCashFlow(date(2026, 1, 1), Money.of("200", "BRL")),
        )
    )
    assert abs(result - Decimal(1)) < Decimal("0.0000001")


def test_xirr_matches_portfolio_performance_excel_golden_cases() -> None:
    simple = xirr(
        (
            DatedCashFlow(date(2010, 1, 1), Money.of("-200", "BRL")),
            DatedCashFlow(date(2010, 12, 31), Money.of("210", "BRL")),
        )
    )
    assert abs(simple - Decimal("0.050140747")) < Decimal("0.00000001")
    dates = (
        date(2002, 11, 30),
        date(2007, 6, 11),
        date(2008, 5, 11),
        date(2009, 5, 1),
        date(2010, 6, 1),
        date(2011, 5, 2),
        date(2012, 4, 30),
        date(2012, 12, 6),
    )
    amounts = ("-4398", "200", "270", "280", "280", "300", "330", "14508")
    complex_result = xirr(
        tuple(
            DatedCashFlow(on, Money.of(amount, "BRL"))
            for on, amount in zip(dates, amounts, strict=True)
        )
    )
    assert abs(complex_result - Decimal("0.1444629967")) < Decimal("0.0001")


def test_maximum_drawdown_finds_peak_trough_and_recovery() -> None:
    values = (100, 120, 90, 125)
    points = tuple(
        (T0 + timedelta(days=index), Money.of(value, "BRL")) for index, value in enumerate(values)
    )
    result = maximum_drawdown(points)
    assert result.maximum_drawdown == Decimal("-0.25")
    assert result.recovered_at == T0 + timedelta(days=3)


def test_cash_attribution_separates_fee_tax_and_income() -> None:
    trade = Activity(
        "buy",
        ActivityKind.BUY,
        "broker",
        T0,
        T0,
        Money.of("100", "BRL"),
        instrument_id="ETF",
        quantity=Decimal(1),
        fee=Money.of("1", "BRL"),
        tax=Money.of("2", "BRL"),
    )
    dividend = Activity(
        "dividend",
        ActivityKind.DIVIDEND,
        "broker",
        T0,
        T0,
        Money.of("5", "BRL"),
        instrument_id="ETF",
    )
    result = cash_attribution(Ledger([trade, dividend]), "BRL")
    assert result.fees == Money.of("1", "BRL")
    assert result.taxes == Money.of("2", "BRL")
    assert result.income == Money.of("5", "BRL")


def test_cash_attribution_separates_return_of_capital_and_reversals() -> None:
    amortization = Activity(
        "amortization",
        ActivityKind.AMORTIZATION,
        "broker",
        T0,
        T0,
        Money.of("10", "BRL"),
        instrument_id="ETF",
    )
    reversal = Activity(
        "amortization-reversal",
        ActivityKind.AMORTIZATION,
        "broker",
        T0,
        T0,
        Money.of("10", "BRL"),
        instrument_id="ETF",
        correction_of="amortization",
        is_reversal=True,
    )
    result = cash_attribution(Ledger((amortization, reversal)), "BRL")
    assert result.return_of_capital == Money.zero("BRL")
    assert result.income == Money.zero("BRL")
