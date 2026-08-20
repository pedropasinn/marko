from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AssetClass(StrEnum):
    CASH = "cash"
    FIXED_INCOME = "fixed_income"
    EQUITY = "equity"
    FUND = "fund"
    ETF = "etf"
    FX = "fx"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class InstrumentIdentifier:
    scheme: str
    value: str

    def __post_init__(self) -> None:
        if not self.scheme.strip() or not self.value.strip():
            raise ValueError("scheme e value do identificador são obrigatórios")


@dataclass(frozen=True, slots=True)
class Instrument:
    instrument_id: str
    name: str
    asset_class: AssetClass
    quote_currency: str
    quantity_precision: int = 8
    identifiers: tuple[InstrumentIdentifier, ...] = ()

    def __post_init__(self) -> None:
        if not self.instrument_id.strip() or not self.name.strip():
            raise ValueError("instrument_id e name são obrigatórios")
        currency = self.quote_currency.upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("quote_currency inválida")
        if not 0 <= self.quantity_precision <= 18:
            raise ValueError("quantity_precision deve estar entre 0 e 18")
        schemes = [identifier.scheme for identifier in self.identifiers]
        if len(schemes) != len(set(schemes)):
            raise ValueError("um instrumento não pode repetir o scheme de identificador")
        object.__setattr__(self, "quote_currency", currency)
