from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from marko.ledger import Ledger
from marko.money import Money


@dataclass(frozen=True, slots=True)
class PriceQuote:
    instrument_id: str
    price: Money
    as_of: datetime

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or self.price.amount < 0:
            raise ValueError("cotação exige instrumento e preço não negativo")
        if self.as_of.tzinfo is None:
            raise ValueError("as_of precisa de timezone")


@dataclass(frozen=True, slots=True)
class CashBalance:
    account_id: str
    balance: Money


@dataclass(frozen=True, slots=True)
class PositionBalance:
    account_id: str
    instrument_id: str
    quantity: Decimal
    quote: PriceQuote | None = None

    @property
    def market_value(self) -> Money | None:
        return self.quote.price * self.quantity if self.quote is not None else None


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    snapshot_id: str
    as_of: datetime
    last_activity_id: str | None
    cash: tuple[CashBalance, ...]
    positions: tuple[PositionBalance, ...]

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or self.as_of.tzinfo is None:
            raise ValueError("snapshot_id e as_of com timezone são obrigatórios")

    def net_liquidation_value(self, currency: str) -> Money:
        total = Money.zero(currency)
        for cash in self.cash:
            if cash.balance.currency == total.currency:
                total += cash.balance
        for position in self.positions:
            value = position.market_value
            if value is not None and value.currency == total.currency:
                total += value
        return total


def build_snapshot(
    ledger: Ledger,
    snapshot_id: str,
    as_of: datetime,
    account_currencies: tuple[tuple[str, str], ...],
    account_instruments: tuple[tuple[str, str], ...],
    quotes: tuple[PriceQuote, ...] = (),
) -> PortfolioSnapshot:
    quote_map: dict[str, PriceQuote] = {}
    for quote in quotes:
        if quote.as_of > as_of:
            continue
        previous = quote_map.get(quote.instrument_id)
        if previous is None or quote.as_of > previous.as_of:
            quote_map[quote.instrument_id] = quote
    cash = tuple(
        CashBalance(account_id, ledger.cash_balance(account_id, currency, as_of))
        for account_id, currency in account_currencies
    )
    positions = tuple(
        PositionBalance(
            account_id,
            instrument_id,
            ledger.position(account_id, instrument_id, as_of),
            quote_map.get(instrument_id),
        )
        for account_id, instrument_id in account_instruments
    )
    included = ledger.activities(as_of)
    return PortfolioSnapshot(
        snapshot_id=snapshot_id,
        as_of=as_of,
        last_activity_id=included[-1].activity_id if included else None,
        cash=cash,
        positions=positions,
    )
