from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AccountKind(StrEnum):
    BROKERAGE = "brokerage"
    BANK = "bank"
    CASH = "cash"
    LIABILITY = "liability"


@dataclass(frozen=True, slots=True)
class Account:
    account_id: str
    name: str
    kind: AccountKind
    base_currency: str
    institution: str | None = None

    def __post_init__(self) -> None:
        if not self.account_id.strip() or not self.name.strip():
            raise ValueError("account_id e name são obrigatórios")
        currency = self.base_currency.upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("base_currency inválida")
        object.__setattr__(self, "base_currency", currency)
