from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from marko.ledger import Ledger
from marko.money import Money


@dataclass(frozen=True, slots=True)
class PriceQuote:
    instrument_id: str
    price: Money
    as_of: datetime
    available_at: datetime
    observation_id: str
    source: str
    vintage_id: str

    def __post_init__(self) -> None:
        if (
            not self.instrument_id.strip()
            or not self.observation_id.strip()
            or not self.source.strip()
            or not self.vintage_id.strip()
            or self.price.amount < 0
        ):
            raise ValueError("cotação exige instrumento e preço não negativo")
        if self.as_of.tzinfo is None or self.available_at.tzinfo is None:
            raise ValueError("timestamps da cotação precisam de timezone")
        if self.available_at < self.as_of:
            raise ValueError("available_at não pode preceder as_of")


@dataclass(frozen=True, slots=True)
class FxQuote:
    base_currency: str
    quote_currency: str
    rate: Decimal
    as_of: datetime
    available_at: datetime
    observation_id: str
    source: str
    vintage_id: str

    def __post_init__(self) -> None:
        rate = Decimal(str(self.rate))
        base = self.base_currency.upper()
        quote = self.quote_currency.upper()
        if (
            base == quote
            or rate <= 0
            or not rate.is_finite()
            or not self.observation_id.strip()
            or not self.source.strip()
            or not self.vintage_id.strip()
        ):
            raise ValueError("cotação FX inválida")
        if self.as_of.tzinfo is None or self.available_at.tzinfo is None:
            raise ValueError("timestamps da cotação FX precisam de timezone")
        if self.available_at < self.as_of:
            raise ValueError("available_at não pode preceder as_of")
        Money.zero(base)
        Money.zero(quote)
        object.__setattr__(self, "base_currency", base)
        object.__setattr__(self, "quote_currency", quote)
        object.__setattr__(self, "rate", rate)


class IncompleteValuationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValuationResult:
    value: Money
    complete: bool
    missing_quotes: tuple[str, ...]
    missing_fx: tuple[tuple[str, str], ...]
    stale_quotes: tuple[str, ...]
    evidence_ids: tuple[str, ...]


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

    def valuation(
        self,
        currency: str,
        *,
        fx_quotes: tuple[FxQuote, ...] = (),
        maximum_quote_age: timedelta | None = None,
    ) -> ValuationResult:
        if maximum_quote_age is not None and maximum_quote_age < timedelta(0):
            raise ValueError("maximum_quote_age não pode ser negativo")
        total = Money.zero(currency)
        missing_quotes: set[str] = set()
        missing_fx: set[tuple[str, str]] = set()
        stale_quotes: set[str] = set()
        evidence_ids: set[str] = set()
        for cash in self.cash:
            if cash.balance.amount == 0:
                continue
            converted, fx_quote = _convert(cash.balance, total.currency, fx_quotes, self.as_of)
            if converted is None:
                missing_fx.add((cash.balance.currency, total.currency))
            else:
                total += converted
                if fx_quote is not None:
                    evidence_ids.add(fx_quote.observation_id)
                    if (
                        maximum_quote_age is not None
                        and self.as_of - fx_quote.as_of > maximum_quote_age
                    ):
                        stale_quotes.add(f"FX:{fx_quote.base_currency}/{fx_quote.quote_currency}")
        for position in self.positions:
            if position.quantity == 0:
                continue
            value = position.market_value
            if value is None:
                missing_quotes.add(position.instrument_id)
                continue
            assert position.quote is not None
            evidence_ids.add(position.quote.observation_id)
            if (
                maximum_quote_age is not None
                and self.as_of - position.quote.as_of > maximum_quote_age
            ):
                stale_quotes.add(position.instrument_id)
            converted, fx_quote = _convert(value, total.currency, fx_quotes, self.as_of)
            if converted is None:
                missing_fx.add((value.currency, total.currency))
            else:
                total += converted
                if fx_quote is not None:
                    evidence_ids.add(fx_quote.observation_id)
                    if (
                        maximum_quote_age is not None
                        and self.as_of - fx_quote.as_of > maximum_quote_age
                    ):
                        stale_quotes.add(f"FX:{fx_quote.base_currency}/{fx_quote.quote_currency}")
        complete = not missing_quotes and not missing_fx and not stale_quotes
        return ValuationResult(
            total,
            complete,
            tuple(sorted(missing_quotes)),
            tuple(sorted(missing_fx)),
            tuple(sorted(stale_quotes)),
            tuple(sorted(evidence_ids)),
        )

    def net_liquidation_value(
        self,
        currency: str,
        *,
        fx_quotes: tuple[FxQuote, ...] = (),
        maximum_quote_age: timedelta | None = None,
    ) -> Money:
        result = self.valuation(
            currency,
            fx_quotes=fx_quotes,
            maximum_quote_age=maximum_quote_age,
        )
        if not result.complete:
            raise IncompleteValuationError(
                "valuation incompleta: "
                f"missing_quotes={result.missing_quotes}, missing_fx={result.missing_fx}, "
                f"stale_quotes={result.stale_quotes}"
            )
        return result.value


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
        if quote.as_of > as_of or quote.available_at > as_of:
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


def _convert(
    amount: Money,
    target_currency: str,
    fx_quotes: tuple[FxQuote, ...],
    as_of: datetime,
) -> tuple[Money | None, FxQuote | None]:
    target = target_currency.upper()
    if amount.currency == target:
        return amount, None
    eligible = tuple(
        quote
        for quote in fx_quotes
        if quote.as_of <= as_of
        and quote.available_at <= as_of
        and {quote.base_currency, quote.quote_currency} == {amount.currency, target}
    )
    if not eligible:
        return None, None
    quote = max(eligible, key=lambda item: (item.as_of, item.available_at, item.observation_id))
    if quote.base_currency == amount.currency:
        converted = Money.of(amount.amount * quote.rate, target)
    else:
        converted = Money.of(amount.amount / quote.rate, target)
    return converted, quote
