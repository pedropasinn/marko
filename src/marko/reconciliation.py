from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from marko.money import Money, decimal_value
from marko.snapshots import PortfolioSnapshot


@dataclass(frozen=True, slots=True)
class StatementCash:
    account_id: str
    balance: Money


@dataclass(frozen=True, slots=True)
class StatementPosition:
    account_id: str
    instrument_id: str
    quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(self, "quantity", decimal_value(self.quantity))


@dataclass(frozen=True, slots=True)
class BrokerStatement:
    statement_id: str
    as_of: datetime
    cash: tuple[StatementCash, ...]
    positions: tuple[StatementPosition, ...]

    def __post_init__(self) -> None:
        if not self.statement_id.strip() or self.as_of.tzinfo is None:
            raise ValueError("statement_id e as_of com timezone são obrigatórios")


@dataclass(frozen=True, slots=True)
class ReconciliationDifference:
    key: str
    expected: Decimal
    reported: Decimal
    difference: Decimal


@dataclass(frozen=True, slots=True)
class ReconciliationReport:
    statement_id: str
    snapshot_id: str
    differences: tuple[ReconciliationDifference, ...]

    @property
    def reconciled(self) -> bool:
        return not self.differences


def reconcile(
    snapshot: PortfolioSnapshot,
    statement: BrokerStatement,
    cash_tolerance: Decimal = Decimal("0.01"),
    quantity_tolerance: Decimal = Decimal("0.00000001"),
) -> ReconciliationReport:
    if snapshot.as_of != statement.as_of:
        raise ValueError("snapshot e statement precisam usar o mesmo as_of")
    differences: list[ReconciliationDifference] = []
    expected_cash = {
        (item.account_id, item.balance.currency): item.balance.amount for item in snapshot.cash
    }
    reported_cash = {
        (item.account_id, item.balance.currency): item.balance.amount for item in statement.cash
    }
    for key in sorted(expected_cash.keys() | reported_cash.keys()):
        expected = expected_cash.get(key, Decimal(0))
        reported = reported_cash.get(key, Decimal(0))
        difference = reported - expected
        if abs(difference) > cash_tolerance:
            differences.append(
                ReconciliationDifference(f"cash:{key[0]}:{key[1]}", expected, reported, difference)
            )

    expected_positions = {
        (item.account_id, item.instrument_id): item.quantity for item in snapshot.positions
    }
    reported_positions = {
        (item.account_id, item.instrument_id): item.quantity for item in statement.positions
    }
    for key in sorted(expected_positions.keys() | reported_positions.keys()):
        expected = expected_positions.get(key, Decimal(0))
        reported = reported_positions.get(key, Decimal(0))
        difference = reported - expected
        if abs(difference) > quantity_tolerance:
            differences.append(
                ReconciliationDifference(
                    f"position:{key[0]}:{key[1]}", expected, reported, difference
                )
            )
    return ReconciliationReport(statement.statement_id, snapshot.snapshot_id, tuple(differences))
