from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from marko.activities import Activity
from marko.money import Money


class DuplicateActivityError(ValueError):
    pass


class Ledger:
    def __init__(self, activities: Iterable[Activity] = ()) -> None:
        self._activities: list[Activity] = []
        self._ids: set[str] = set()
        for activity in activities:
            self.append(activity)

    def append(self, activity: Activity) -> None:
        if activity.activity_id in self._ids:
            raise DuplicateActivityError(f"activity duplicada: {activity.activity_id}")
        if activity.correction_of is not None and activity.correction_of not in self._ids:
            raise ValueError(f"activity corrigida não encontrada: {activity.correction_of}")
        self._activities.append(activity)
        self._ids.add(activity.activity_id)

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        selected = (
            activity
            for activity in self._activities
            if as_of is None or activity.effective_at <= as_of
        )
        return tuple(
            sorted(
                selected,
                key=lambda item: (
                    item.effective_at,
                    item.recorded_at,
                    item.sequence,
                    item.activity_id,
                ),
            )
        )

    def cash_balance(self, account_id: str, currency: str, as_of: datetime | None = None) -> Money:
        balance = Money.zero(currency)
        for activity in self.activities(as_of):
            if activity.account_id != account_id:
                continue
            for effect in activity.cash_effects():
                if effect.currency == balance.currency:
                    balance += effect
        return balance

    def position(
        self, account_id: str, instrument_id: str, as_of: datetime | None = None
    ) -> Decimal:
        quantity = Decimal(0)
        for activity in self.activities(as_of):
            if activity.account_id == account_id and activity.instrument_id == instrument_id:
                if activity.kind.value == "split":
                    assert activity.ratio is not None
                    quantity = (
                        quantity / activity.ratio
                        if activity.is_reversal
                        else quantity * activity.ratio
                    )
                else:
                    quantity += activity.position_effect()
        return quantity

    def by_external_id(self, external_id: str) -> tuple[Activity, ...]:
        return tuple(
            activity for activity in self.activities() if activity.external_id == external_id
        )

    def last_activity_id(self) -> str | None:
        ordered = self.activities()
        return ordered[-1].activity_id if ordered else None

    def __len__(self) -> int:
        return len(self._activities)
