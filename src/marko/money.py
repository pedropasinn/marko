from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Self

_MINOR_UNITS = {
    "BRL": 2,
    "USD": 2,
    "EUR": 2,
    "GBP": 2,
    "CHF": 2,
    "CAD": 2,
    "AUD": 2,
    "CNY": 2,
    "JPY": 0,
    "KRW": 0,
    "CLP": 0,
    "KWD": 3,
    "BHD": 3,
    "JOD": 3,
}


class CurrencyMismatchError(ValueError):
    pass


def decimal_value(value: Decimal | int | str) -> Decimal:
    try:
        result = value if isinstance(value, Decimal) else Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"valor decimal inválido: {value!r}") from error
    if not result.is_finite():
        raise ValueError("o valor precisa ser finito")
    return result


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str

    def __post_init__(self) -> None:
        currency = self.currency.upper()
        if currency not in _MINOR_UNITS:
            raise ValueError(f"moeda não cadastrada: {currency}")
        digits = _MINOR_UNITS[currency]
        quantum = Decimal(1).scaleb(-digits)
        amount = decimal_value(self.amount).quantize(quantum, rounding=ROUND_HALF_EVEN)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "amount", amount)

    @classmethod
    def of(cls, amount: Decimal | int | str, currency: str) -> Self:
        return cls(decimal_value(amount), currency)

    @classmethod
    def zero(cls, currency: str) -> Self:
        return cls(Decimal(0), currency)

    def _check_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise CurrencyMismatchError(f"moedas incompatíveis: {self.currency} e {other.currency}")

    def __add__(self, other: Money) -> Self:
        self._check_currency(other)
        return type(self)(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Self:
        self._check_currency(other)
        return type(self)(self.amount - other.amount, self.currency)

    def __neg__(self) -> Self:
        return type(self)(-self.amount, self.currency)

    def __mul__(self, multiplier: Decimal | int | str) -> Self:
        return type(self)(self.amount * decimal_value(multiplier), self.currency)

    def __truediv__(self, divisor: Decimal | int | str) -> Self:
        value = decimal_value(divisor)
        if value == 0:
            raise ZeroDivisionError("divisão monetária por zero")
        return type(self)(self.amount / value, self.currency)

    def is_negative(self) -> bool:
        return self.amount < 0
