from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from marko.activities import Activity, ActivityKind
from marko.ledger import Ledger
from marko.money import Money
from marko.reconciliation import (
    BrokerStatement,
    StatementCash,
    StatementPosition,
    reconcile,
)
from marko.snapshots import FxQuote, IncompleteValuationError, PriceQuote, build_snapshot
from marko.taxlots import CostBasisMethod, TaxLot, build_tax_lots

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
        (
            PriceQuote(
                "ETF",
                Money.of("65", "BRL"),
                T0 + timedelta(hours=1),
                T0 + timedelta(hours=2),
                "quote-1",
                "provider",
                "vintage-1",
            ),
        ),
    )
    assert snapshot.net_liquidation_value("BRL") == Money.of("1050", "BRL")
    statement = BrokerStatement(
        "statement-1",
        snapshot.as_of,
        (StatementCash("broker", Money.of("400", "BRL")),),
        (StatementPosition("broker", "ETF", Decimal("10")),),
    )
    assert reconcile(snapshot, statement).reconciled


def test_snapshot_fails_closed_when_a_position_has_no_quote() -> None:
    snapshot = build_snapshot(
        Ledger(
            [
                event(
                    "buy",
                    ActivityKind.BUY,
                    gross_amount=Money.of("100", "BRL"),
                    instrument_id="ETF",
                    quantity=Decimal("1"),
                )
            ]
        ),
        "incomplete",
        T0 + timedelta(days=1),
        (("broker", "BRL"),),
        (("broker", "ETF"),),
    )
    result = snapshot.valuation("BRL")
    assert not result.complete
    assert result.missing_quotes == ("ETF",)
    with pytest.raises(IncompleteValuationError):
        snapshot.net_liquidation_value("BRL")


def test_reversals_restore_tax_lots_for_buy_sell_and_amortization() -> None:
    buy = event(
        "buy",
        ActivityKind.BUY,
        gross_amount=Money.of("100", "BRL"),
        instrument_id="ETF",
        quantity=Decimal("10"),
    )
    sell = event(
        "sell",
        ActivityKind.SELL,
        gross_amount=Money.of("60", "BRL"),
        instrument_id="ETF",
        quantity=Decimal("5"),
        sequence=1,
    )
    reverse_sell = event(
        "reverse-sell",
        ActivityKind.SELL,
        gross_amount=sell.gross_amount,
        instrument_id=sell.instrument_id,
        quantity=sell.quantity,
        correction_of=sell.activity_id,
        is_reversal=True,
        sequence=2,
    )
    amortization = event(
        "amortization",
        ActivityKind.AMORTIZATION,
        gross_amount=Money.of("10", "BRL"),
        instrument_id="ETF",
        sequence=3,
    )
    reverse_amortization = event(
        "reverse-amortization",
        ActivityKind.AMORTIZATION,
        gross_amount=amortization.gross_amount,
        instrument_id=amortization.instrument_id,
        correction_of=amortization.activity_id,
        is_reversal=True,
        sequence=4,
    )
    report = build_tax_lots(
        Ledger((buy, sell, reverse_sell, amortization, reverse_amortization)),
        "broker",
        "ETF",
    )
    assert report.disposals == ()
    assert report.open_lots == (TaxLot(T0, Decimal("10"), Money.of("100", "BRL"), "buy"),)


def test_reversal_payload_cannot_diverge_from_original() -> None:
    original = event("deposit", ActivityKind.DEPOSIT, gross_amount=Money.of("100", "BRL"))
    divergent = event(
        "reversal",
        ActivityKind.DEPOSIT,
        gross_amount=Money.of("99", "BRL"),
        correction_of="deposit",
        is_reversal=True,
    )
    with pytest.raises(ValueError, match="payload"):
        Ledger((original, divergent))


def test_all_tax_lot_mutations_have_reversible_golden_cases() -> None:
    buy = event(
        "buy-reversed",
        ActivityKind.BUY,
        gross_amount=Money.of("100", "BRL"),
        instrument_id="BUY",
        quantity=Decimal("10"),
    )
    delivery_in = event(
        "delivery-in-reversed",
        ActivityKind.DELIVERY_IN,
        instrument_id="DELIVERY_IN",
        quantity=Decimal("10"),
        cost_basis=Money.of("100", "BRL"),
    )
    spinoff = event(
        "spinoff-reversed",
        ActivityKind.SPINOFF,
        instrument_id="SPINOFF",
        related_instrument_id="PARENT",
        quantity=Decimal("10"),
        cost_basis=Money.of("100", "BRL"),
    )
    base_delivery = replace(buy, activity_id="base-delivery", instrument_id="DELIVERY_OUT")
    delivery_out = event(
        "delivery-out-reversed",
        ActivityKind.DELIVERY_OUT,
        instrument_id="DELIVERY_OUT",
        quantity=Decimal("5"),
    )
    base_split = replace(buy, activity_id="base-split", instrument_id="SPLIT")
    split = event(
        "split-reversed",
        ActivityKind.SPLIT,
        instrument_id="SPLIT",
        ratio=Decimal("2"),
    )
    base_transfer = replace(buy, activity_id="base-transfer", instrument_id="TRANSFER_OUT")
    transfer_out = event(
        "transfer-out-reversed",
        ActivityKind.POSITION_TRANSFER_OUT,
        instrument_id="TRANSFER_OUT",
        quantity=Decimal("5"),
        related_account_id="bank",
        related_activity_id="transfer-in-pair",
    )
    transfer_in = Activity(
        "transfer-in-pair",
        ActivityKind.POSITION_TRANSFER_IN,
        "bank",
        T0,
        T0 + timedelta(minutes=1),
        instrument_id="TRANSFER_OUT",
        quantity=Decimal("5"),
        cost_basis=Money.of("50", "BRL"),
        related_account_id="broker",
        related_activity_id=transfer_out.activity_id,
    )
    originals = (buy, delivery_in, spinoff, delivery_out, split, transfer_out)
    reversals = tuple(
        replace(
            original,
            activity_id=f"reverse-{original.activity_id}",
            correction_of=original.activity_id,
            is_reversal=True,
            sequence=index + 1,
        )
        for index, original in enumerate(originals)
    )
    reverse_transfer_in = replace(
        transfer_in,
        activity_id="reverse-transfer-in-pair",
        correction_of=transfer_in.activity_id,
        is_reversal=True,
        sequence=7,
    )
    ledger = Ledger(
        (
            buy,
            reversals[0],
            delivery_in,
            reversals[1],
            spinoff,
            reversals[2],
            base_delivery,
            delivery_out,
            reversals[3],
            base_split,
            split,
            reversals[4],
            base_transfer,
            transfer_out,
            transfer_in,
            reversals[5],
            reverse_transfer_in,
        )
    )
    for instrument in ("BUY", "DELIVERY_IN", "SPINOFF"):
        assert build_tax_lots(ledger, "broker", instrument).open_lots == ()
    for instrument in ("DELIVERY_OUT", "SPLIT", "TRANSFER_OUT"):
        report = build_tax_lots(ledger, "broker", instrument)
        assert report.open_lots[0].quantity == Decimal("10")
        assert report.open_lots[0].total_cost == Money.of("100", "BRL")


def test_multicurrency_valuation_uses_point_in_time_fx_and_evidence() -> None:
    ledger = Ledger(
        (
            event("usd", ActivityKind.DEPOSIT, gross_amount=Money.of("100", "USD")),
            event(
                "position",
                ActivityKind.DELIVERY_IN,
                instrument_id="ETF_US",
                quantity=Decimal("2"),
                cost_basis=Money.of("20", "USD"),
            ),
        )
    )
    snapshot = build_snapshot(
        ledger,
        "fx-snapshot",
        T0 + timedelta(days=1),
        (("broker", "USD"),),
        (("broker", "ETF_US"),),
        (
            PriceQuote(
                "ETF_US",
                Money.of("10", "USD"),
                T0,
                T0,
                "price-observation",
                "provider",
                "price-vintage",
            ),
        ),
    )
    fx = FxQuote(
        "USD",
        "BRL",
        Decimal("5"),
        T0,
        T0,
        "fx-observation",
        "provider",
        "fx-vintage",
    )
    result = snapshot.valuation("BRL", fx_quotes=(fx,))
    assert result.complete
    assert result.value == Money.of("600", "BRL")
    assert result.evidence_ids == ("fx-observation", "price-observation")


def test_tax_lot_reversal_is_applied_only_from_its_effective_time() -> None:
    buy = event(
        "timed-buy",
        ActivityKind.BUY,
        gross_amount=Money.of("100", "BRL"),
        instrument_id="ETF",
        quantity=Decimal("10"),
    )
    reversed_at = T0 + timedelta(days=1)
    reversal = replace(
        buy,
        activity_id="timed-reversal",
        effective_at=reversed_at,
        recorded_at=reversed_at + timedelta(minutes=1),
        correction_of=buy.activity_id,
        is_reversal=True,
    )
    ledger = Ledger((buy, reversal))
    before = build_tax_lots(ledger, "broker", "ETF", as_of=T0 + timedelta(hours=1))
    after = build_tax_lots(ledger, "broker", "ETF", as_of=reversed_at)
    assert before.open_lots[0].quantity == Decimal("10")
    assert after.open_lots == ()


def test_cash_effects_have_golden_reversals_for_every_cash_kind() -> None:
    cases = (
        event("deposit-case", ActivityKind.DEPOSIT, gross_amount=Money.of("10", "BRL")),
        event(
            "withdrawal-case",
            ActivityKind.WITHDRAWAL,
            gross_amount=Money.of("10", "BRL"),
            fee=Money.of("1", "BRL"),
        ),
        event(
            "buy-case",
            ActivityKind.BUY,
            gross_amount=Money.of("10", "BRL"),
            instrument_id="ETF",
            quantity=Decimal("1"),
        ),
        event(
            "sell-case",
            ActivityKind.SELL,
            gross_amount=Money.of("10", "BRL"),
            instrument_id="ETF",
            quantity=Decimal("1"),
        ),
        event(
            "dividend-case",
            ActivityKind.DIVIDEND,
            gross_amount=Money.of("10", "BRL"),
            instrument_id="ETF",
        ),
        event("interest-case", ActivityKind.INTEREST, gross_amount=Money.of("10", "BRL")),
        event("fee-case", ActivityKind.FEE, gross_amount=Money.of("10", "BRL")),
        event("tax-case", ActivityKind.TAX, gross_amount=Money.of("10", "BRL")),
        event(
            "fx-case",
            ActivityKind.FX_CONVERSION,
            gross_amount=Money.of("50", "BRL"),
            counter_amount=Money.of("10", "USD"),
            ratio=Decimal("0.2"),
            fee=Money.of("1", "BRL"),
        ),
        event(
            "amortization-case",
            ActivityKind.AMORTIZATION,
            gross_amount=Money.of("10", "BRL"),
            instrument_id="ETF",
        ),
    )
    for original in cases:
        reversal = replace(
            original,
            activity_id=f"reverse-{original.activity_id}",
            correction_of=original.activity_id,
            is_reversal=True,
            sequence=1,
        )
        ledger = Ledger((original, reversal))
        assert ledger.cash_balance("broker", "BRL") == Money.zero("BRL")
        if original.kind is ActivityKind.FX_CONVERSION:
            assert ledger.cash_balance("broker", "USD") == Money.zero("USD")


def test_transfer_reversal_requires_and_cancels_both_legs() -> None:
    cash_out = event(
        "paired-cash-out",
        ActivityKind.CASH_TRANSFER_OUT,
        gross_amount=Money.of("100", "BRL"),
        related_account_id="bank",
        related_activity_id="paired-cash-in",
    )
    cash_in = Activity(
        "paired-cash-in",
        ActivityKind.CASH_TRANSFER_IN,
        "bank",
        T0,
        T0 + timedelta(minutes=1),
        Money.of("100", "BRL"),
        related_account_id="broker",
        related_activity_id=cash_out.activity_id,
    )
    reverse_out = replace(
        cash_out,
        activity_id="reverse-paired-cash-out",
        correction_of=cash_out.activity_id,
        is_reversal=True,
        sequence=1,
    )
    reverse_in = replace(
        cash_in,
        activity_id="reverse-paired-cash-in",
        correction_of=cash_in.activity_id,
        is_reversal=True,
        sequence=1,
    )
    with pytest.raises(ValueError, match="duas pernas"):
        Ledger((cash_out, cash_in, reverse_out)).cash_balance("broker", "BRL")
    ledger = Ledger((cash_out, cash_in, reverse_out, reverse_in))
    assert ledger.cash_balance("broker", "BRL") == Money.zero("BRL")
    assert ledger.cash_balance("bank", "BRL") == Money.zero("BRL")


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
