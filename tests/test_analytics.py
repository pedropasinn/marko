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
from marko.snapshots import FxQuote, PriceQuote, build_snapshot

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


def test_twr_golden_case_chains_contributions_at_different_instants() -> None:
    points = (
        PerformancePoint(T0, Money.of("100", "BRL"), Money.zero("BRL")),
        PerformancePoint(
            T0 + timedelta(days=1), Money.of("160", "BRL"), Money.of("50", "BRL")
        ),
        PerformancePoint(
            T0 + timedelta(days=2), Money.of("200", "BRL"), Money.of("24", "BRL")
        ),
    )
    assert time_weighted_return(points) == Decimal("0.21")


def test_internal_transfer_is_not_external_flow_or_artificial_return() -> None:
    transfer_out = Activity(
        "transfer-out",
        ActivityKind.CASH_TRANSFER_OUT,
        "broker",
        T0 + timedelta(days=1),
        T0 + timedelta(days=1, minutes=1),
        Money.of("40", "BRL"),
        related_account_id="bank",
        related_activity_id="transfer-in",
    )
    transfer_in = Activity(
        "transfer-in",
        ActivityKind.CASH_TRANSFER_IN,
        "bank",
        T0 + timedelta(days=1),
        T0 + timedelta(days=1, minutes=1),
        Money.of("40", "BRL"),
        related_account_id="broker",
        related_activity_id="transfer-out",
    )
    ledger = Ledger(
        (
            Activity(
                "deposit",
                ActivityKind.DEPOSIT,
                "broker",
                T0,
                T0,
                Money.of("100", "BRL"),
            ),
            transfer_out,
            transfer_in,
        )
    )
    before = build_snapshot(
        ledger,
        "before-transfer",
        T0,
        (("broker", "BRL"), ("bank", "BRL")),
        (),
    )
    after = build_snapshot(
        ledger,
        "after-transfer",
        T0 + timedelta(days=1, minutes=2),
        (("broker", "BRL"), ("bank", "BRL")),
        (),
    )
    points = (
        PerformancePoint(before.as_of, before.net_liquidation_value("BRL"), Money.zero("BRL")),
        PerformancePoint(after.as_of, after.net_liquidation_value("BRL"), Money.zero("BRL")),
    )
    assert time_weighted_return(points) == 0


def test_multicurrency_twr_includes_fx_effect_in_reporting_currency() -> None:
    ledger = Ledger(
        (
            Activity(
                "brl-deposit",
                ActivityKind.DEPOSIT,
                "broker",
                T0,
                T0,
                Money.of("550", "BRL"),
            ),
            Activity(
                "usd-deposit",
                ActivityKind.DEPOSIT,
                "broker",
                T0,
                T0,
                Money.of("100", "USD"),
            ),
        )
    )
    first_at = T0 + timedelta(hours=1)
    second_at = T0 + timedelta(days=1)
    first = build_snapshot(
        ledger,
        "fx-first",
        first_at,
        (("broker", "BRL"), ("broker", "USD")),
        (),
    )
    second = build_snapshot(
        ledger,
        "fx-second",
        second_at,
        (("broker", "BRL"), ("broker", "USD")),
        (),
    )
    first_value = first.net_liquidation_value(
        "BRL", fx_quotes=(_fx("5.50", first_at, "fx-1"),)
    )
    second_value = second.net_liquidation_value(
        "BRL", fx_quotes=(_fx("6.00", second_at, "fx-2"),)
    )
    result = time_weighted_return(
        (
            PerformancePoint(first_at, first_value, Money.zero("BRL")),
            PerformancePoint(second_at, second_value, Money.zero("BRL")),
        )
    )
    assert first_value == Money.of("1100", "BRL")
    assert second_value == Money.of("1150", "BRL")
    assert result.quantize(Decimal("0.000001")) == Decimal("0.045455")


def test_corporate_actions_preserve_value_when_quotes_adjust() -> None:
    events = (
        Activity(
            "parent-in",
            ActivityKind.DELIVERY_IN,
            "broker",
            T0,
            T0,
            instrument_id="PARENT",
            quantity=Decimal("10"),
            cost_basis=Money.of("1000", "BRL"),
        ),
        Activity(
            "split",
            ActivityKind.SPLIT,
            "broker",
            T0 + timedelta(days=1),
            T0 + timedelta(days=1),
            instrument_id="PARENT",
            ratio=Decimal("2"),
        ),
        Activity(
            "spinoff",
            ActivityKind.SPINOFF,
            "broker",
            T0 + timedelta(days=2),
            T0 + timedelta(days=2),
            instrument_id="CHILD",
            related_instrument_id="PARENT",
            quantity=Decimal("5"),
            cost_basis=Money.of("100", "BRL"),
        ),
        Activity(
            "amortization",
            ActivityKind.AMORTIZATION,
            "broker",
            T0 + timedelta(days=3),
            T0 + timedelta(days=3),
            Money.of("50", "BRL"),
            instrument_id="CHILD",
        ),
    )
    ledger = Ledger(events)
    snapshots = (
        build_snapshot(
            ledger,
            "corporate-0",
            T0,
            (("broker", "BRL"),),
            (("broker", "PARENT"), ("broker", "CHILD")),
            (_price("PARENT", "100", T0, "parent-0"),),
        ),
        build_snapshot(
            ledger,
            "corporate-1",
            T0 + timedelta(days=1),
            (("broker", "BRL"),),
            (("broker", "PARENT"), ("broker", "CHILD")),
            (_price("PARENT", "50", T0 + timedelta(days=1), "parent-1"),),
        ),
        build_snapshot(
            ledger,
            "corporate-2",
            T0 + timedelta(days=2),
            (("broker", "BRL"),),
            (("broker", "PARENT"), ("broker", "CHILD")),
            (
                _price("PARENT", "45", T0 + timedelta(days=2), "parent-2"),
                _price("CHILD", "20", T0 + timedelta(days=2), "child-2"),
            ),
        ),
        build_snapshot(
            ledger,
            "corporate-3",
            T0 + timedelta(days=3),
            (("broker", "BRL"),),
            (("broker", "PARENT"), ("broker", "CHILD")),
            (
                _price("PARENT", "45", T0 + timedelta(days=3), "parent-3"),
                _price("CHILD", "10", T0 + timedelta(days=3), "child-3"),
            ),
        ),
    )
    values = tuple(snapshot.net_liquidation_value("BRL") for snapshot in snapshots)
    assert values == (Money.of("1000", "BRL"),) * 4
    points = tuple(
        PerformancePoint(snapshot.as_of, value, Money.zero("BRL"))
        for snapshot, value in zip(snapshots, values, strict=True)
    )
    assert time_weighted_return(points) == 0


def _price(instrument: str, amount: str, at: datetime, identifier: str) -> PriceQuote:
    return PriceQuote(
        instrument,
        Money.of(amount, "BRL"),
        at,
        at,
        identifier,
        "golden",
        "golden-v1",
    )


def _fx(rate: str, at: datetime, identifier: str) -> FxQuote:
    return FxQuote(
        "USD",
        "BRL",
        Decimal(rate),
        at,
        at,
        identifier,
        "golden",
        "golden-v1",
    )
