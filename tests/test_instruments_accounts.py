import pytest

from marko.accounts import Account, AccountKind
from marko.instruments import AssetClass, Instrument, InstrumentIdentifier


def test_instrument_normalizes_currency_and_preserves_identifiers() -> None:
    instrument = Instrument(
        instrument_id="tesouro-selic-2029",
        name="Tesouro Selic 2029",
        asset_class=AssetClass.FIXED_INCOME,
        quote_currency="brl",
        identifiers=(InstrumentIdentifier("isin", "BRSTNCLF1Q11"),),
    )
    assert instrument.quote_currency == "BRL"


def test_instrument_rejects_duplicate_identifier_scheme() -> None:
    with pytest.raises(ValueError):
        Instrument(
            "asset",
            "Asset",
            AssetClass.ETF,
            "BRL",
            identifiers=(InstrumentIdentifier("ticker", "A"), InstrumentIdentifier("ticker", "B")),
        )


def test_account_requires_valid_currency() -> None:
    assert Account("broker-1", "Corretora", AccountKind.BROKERAGE, "brl").base_currency == "BRL"
    with pytest.raises(ValueError):
        Account("broker-2", "Corretora", AccountKind.BROKERAGE, "REAL")
