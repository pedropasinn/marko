from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from marko.money import Money, decimal_value


class ConstraintKind(StrEnum):
    WEIGHT = "weight"
    GROUP_WEIGHT = "group_weight"
    TURNOVER = "turnover"
    CASH = "cash"
    LIQUIDITY = "liquidity"


@dataclass(frozen=True, slots=True)
class Constraint:
    key: str
    kind: ConstraintKind
    lower: Decimal | None = None
    upper: Decimal | None = None

    def __post_init__(self) -> None:
        if not self.key.strip():
            raise ValueError("a constraint precisa de key")
        lower = decimal_value(self.lower) if self.lower is not None else None
        upper = decimal_value(self.upper) if self.upper is not None else None
        if lower is None and upper is None:
            raise ValueError("a constraint precisa de ao menos um limite")
        if lower is not None and upper is not None and lower > upper:
            raise ValueError("o limite inferior não pode superar o superior")
        if self.kind in {
            ConstraintKind.WEIGHT,
            ConstraintKind.GROUP_WEIGHT,
            ConstraintKind.TURNOVER,
        }:
            for value in (lower, upper):
                if value is not None and not 0 <= value <= 1:
                    raise ValueError("limites proporcionais precisam estar entre zero e um")
        object.__setattr__(self, "lower", lower)
        object.__setattr__(self, "upper", upper)


@dataclass(frozen=True, slots=True)
class ConstraintSet:
    policy_id: str
    policy_version: int
    constraints: tuple[Constraint, ...]

    def __post_init__(self) -> None:
        if self.policy_version < 1:
            raise ValueError("policy_version precisa ser positiva")
        keys = [constraint.key for constraint in self.constraints]
        if len(keys) != len(set(keys)):
            raise ValueError("constraint keys precisam ser únicas")


@dataclass(frozen=True, slots=True)
class InvestmentPolicy:
    policy_id: str
    version: int
    effective_from: date
    approved_at: datetime
    base_currency: str
    horizon_end: date
    minimum_liquidity: Money
    maximum_drawdown: Decimal
    liability_ids: tuple[str, ...]
    real_capital_enabled: bool = False

    def __post_init__(self) -> None:
        if not self.policy_id.strip() or self.version < 1:
            raise ValueError("policy_id e versão positiva são obrigatórios")
        if self.approved_at.tzinfo is None:
            raise ValueError("approved_at precisa de timezone")
        currency = self.base_currency.upper()
        if self.minimum_liquidity.currency != currency:
            raise ValueError("minimum_liquidity precisa usar a moeda-base")
        if self.horizon_end <= self.effective_from:
            raise ValueError("horizon_end precisa suceder effective_from")
        maximum_drawdown = decimal_value(self.maximum_drawdown)
        if not 0 <= maximum_drawdown <= 1:
            raise ValueError("maximum_drawdown precisa estar entre zero e um")
        if len(self.liability_ids) != len(set(self.liability_ids)):
            raise ValueError("liability_ids duplicados")
        object.__setattr__(self, "base_currency", currency)
        object.__setattr__(self, "maximum_drawdown", maximum_drawdown)


@dataclass(frozen=True, slots=True)
class UniverseItem:
    instrument_id: str
    eligible_from: date
    eligible_until: date | None = None
    maximum_weight: Decimal = Decimal(1)

    def __post_init__(self) -> None:
        if not self.instrument_id.strip():
            raise ValueError("instrument_id é obrigatório")
        if self.eligible_until is not None and self.eligible_until < self.eligible_from:
            raise ValueError("eligible_until não pode preceder eligible_from")
        maximum_weight = decimal_value(self.maximum_weight)
        if not 0 <= maximum_weight <= 1:
            raise ValueError("maximum_weight precisa estar entre zero e um")
        object.__setattr__(self, "maximum_weight", maximum_weight)

    def is_eligible(self, on: date) -> bool:
        return self.eligible_from <= on and (
            self.eligible_until is None or on <= self.eligible_until
        )


@dataclass(frozen=True, slots=True)
class Universe:
    universe_id: str
    version: int
    as_of: date
    items: tuple[UniverseItem, ...]

    def __post_init__(self) -> None:
        if not self.universe_id.strip() or self.version < 1:
            raise ValueError("universe_id e versão positiva são obrigatórios")
        identifiers = [item.instrument_id for item in self.items]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("instrumentos duplicados no universo")

    def eligible_instruments(self) -> tuple[str, ...]:
        return tuple(item.instrument_id for item in self.items if item.is_eligible(self.as_of))
