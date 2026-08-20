from datetime import UTC, datetime, timedelta
from decimal import Decimal

from marko.activities import Activity, ActivityKind
from marko.ledger import Ledger
from marko.money import Money
from marko.reconciliation import (
    BrokerStatement,
    StatementCash,
    StatementPosition,
    reconcile,
)
from marko.snapshots import PriceQuote, build_snapshot
from marko.taxlots import CostBasisMethod, build_tax_lots

T0 = datetime(2026, 8, 20, 12, tzinfo=UTC)


def event(identifier: str, kind: ActivityKind, **kwargs: object) -> Activity:
    return Activity(identifier, kind, "broker", T0, T0 + timedelta(minutes=1), **kwargs)


def test_fx_conversion_preserves_two_currency_legs() -> None:
    ledger = Ledger(
        [
            event("deposit", ActivityKind.DEPOSIT, gross_amount=Money.of("1000", "BRL")),
            event(
                "fx",
                ActivityKind.FX_CONVERSION,
                gross_amount=Money.of("550", "BRL"),
                counter_amount=Money.of("100", "USD"),
                ratio=Decimal("0.1818181818"),
            ),
        ]
    )
    assert ledger.cash_balance("broker", "BRL") == Money.of("450", "BRL")
    assert ledger.cash_balance("broker", "USD") == Money.of("100", "USD")


def test_linked_transfers_preserve_total_cash_and_position() -> None:
    source_cash = event(
        "cash-out",
        ActivityKind.CASH_TRANSFER_OUT,
        gross_amount=Money.of("100", "BRL"),
        related_account_id="bank",
        related_activity_id="cash-in",
    )
    destination_cash = Activity(
        "cash-in",
        ActivityKind.CASH_TRANSFER_IN,
        "bank",
        T0,
        T0 + timedelta(minutes=1),
        Money.of("100", "BRL"),
        related_account_id="broker",
        related_activity_id="cash-out",
    )
    source_position = event(
        "position-out",
        ActivityKind.POSITION_TRANSFER_OUT,
        instrument_id="ETF",
        quantity=Decimal("3"),
        related_account_id="bank",
        related_activity_id="position-in",
    )
    destination_position = Activity(
        "position-in",
        ActivityKind.POSITION_TRANSFER_IN,
        "bank",
        T0,
        T0 + timedelta(minutes=1),
        instrument_id="ETF",
        quantity=Decimal("3"),
        related_account_id="broker",
        related_activity_id="position-out",
        cost_basis=Money.of("150", "BRL"),
    )
    ledger = Ledger([source_cash, destination_cash, source_position, destination_position])
    assert ledger.cash_balance("broker", "BRL") + ledger.cash_balance("bank", "BRL") == Money.zero(
        "BRL"
    )
    assert ledger.position("broker", "ETF") + ledger.position("bank", "ETF") == 0


def test_reversal_corrects_without_mutating_original() -> None:
    original = event("deposit", ActivityKind.DEPOSIT, gross_amount=Money.of("100", "BRL"))
    reversal = event(
        "deposit-reversal",
        ActivityKind.DEPOSIT,
        gross_amount=Money.of("100", "BRL"),
        correction_of="deposit",
        is_reversal=True,
        sequence=1,
    )
    ledger = Ledger([original, reversal])
    assert len(ledger) == 2
    assert ledger.cash_balance("broker", "BRL") == Money.zero("BRL")


def test_spinoff_and_amortization_keep_position_and_cash_explicit() -> None:
    ledger = Ledger(
        [
            event(
                "spinoff",
                ActivityKind.SPINOFF,
                instrument_id="CHILD",
                related_instrument_id="PARENT",
                quantity=Decimal("4"),
                cost_basis=Money.of("80", "BRL"),
            ),
            event(
                "amortization",
                ActivityKind.AMORTIZATION,
                instrument_id="CHILD",
                gross_amount=Money.of("12", "BRL"),
                sequence=1,
            ),
            event(
                "grouping",
                ActivityKind.SPLIT,
                instrument_id="CHILD",
                ratio=Decimal("0.5"),
                sequence=2,
            ),
        ]
    )
    assert ledger.position("broker", "CHILD") == Decimal("2.0")
    assert ledger.cash_balance("broker", "BRL") == Money.of("12", "BRL")
    assert build_tax_lots(ledger, "broker", "CHILD").open_lots[0].total_cost == Money.of(
        "68", "BRL"
    )


def test_split_changes_quantity_without_changing_fifo_cost() -> None:
    ledger = Ledger(
        [
            event(
                "buy",
                ActivityKind.BUY,
                gross_amount=Money.of("1000", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
            ),
            event(
                "split",
                ActivityKind.SPLIT,
                instrument_id="ETF",
                ratio=Decimal("2"),
                sequence=1,
            ),
            event(
                "sell",
                ActivityKind.SELL,
                gross_amount=Money.of("600", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
                sequence=2,
            ),
        ]
    )
    assert ledger.position("broker", "ETF") == Decimal("10")
    report = build_tax_lots(ledger, "broker", "ETF", CostBasisMethod.FIFO)
    assert report.disposals[0].allocated_cost == Money.of("500", "BRL")
    assert report.disposals[0].realized_gain == Money.of("100", "BRL")
    assert report.open_lots[0].total_cost == Money.of("500", "BRL")


def test_average_cost_allocates_proportionally() -> None:
    ledger = Ledger(
        [
            event(
                "b1",
                ActivityKind.BUY,
                gross_amount=Money.of("100", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
            ),
            event(
                "b2",
                ActivityKind.BUY,
                gross_amount=Money.of("300", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
            ),
            event(
                "s1",
                ActivityKind.SELL,
                gross_amount=Money.of("250", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
            ),
        ]
    )
    report = build_tax_lots(ledger, "broker", "ETF", CostBasisMethod.AVERAGE)
    assert report.disposals[0].allocated_cost == Money.of("200", "BRL")
    assert report.open_lots[0].total_cost == Money.of("200", "BRL")


def test_snapshot_reconciles_and_exposes_market_value() -> None:
    ledger = Ledger(
        [
            event("deposit", ActivityKind.DEPOSIT, gross_amount=Money.of("1000", "BRL")),
            event(
                "buy",
                ActivityKind.BUY,
                gross_amount=Money.of("600", "BRL"),
                instrument_id="ETF",
                quantity=Decimal("10"),
            ),
        ]
    )
    snapshot = build_snapshot(
        ledger,
        "snapshot-1",
        T0 + timedelta(days=1),
        (("broker", "BRL"),),
        (("broker", "ETF"),),
        (PriceQuote("ETF", Money.of("65", "BRL"), T0 + timedelta(hours=1)),),
    )
    assert snapshot.net_liquidation_value("BRL") == Money.of("1050", "BRL")
    statement = BrokerStatement(
        "statement-1",
        snapshot.as_of,
        (StatementCash("broker", Money.of("400", "BRL")),),
        (StatementPosition("broker", "ETF", Decimal("10")),),
    )
    assert reconcile(snapshot, statement).reconciled


def test_reconciliation_reports_material_difference() -> None:
    snapshot = build_snapshot(
        Ledger(),
        "empty",
        T0,
        (("broker", "BRL"),),
        (("broker", "ETF"),),
    )
    statement = BrokerStatement(
        "statement",
        T0,
        (StatementCash("broker", Money.of("1", "BRL")),),
        (StatementPosition("broker", "ETF", Decimal("2")),),
    )
    report = reconcile(snapshot, statement)
    assert not report.reconciled
    assert {difference.key for difference in report.differences} == {
        "cash:broker:BRL",
        "position:broker:ETF",
    }
