from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from decimal import Decimal

from marko.activities import Activity, ActivityKind
from marko.money import Money


class DuplicateActivityError(ValueError):
    pass


class Ledger:
    def __init__(self, activities: Iterable[Activity] = ()) -> None:
        self._activities: list[Activity] = []
        self._ids: set[str] = set()
        self._by_id: dict[str, Activity] = {}
        self._reversed: set[str] = set()
        self._integrity_checked = False
        for activity in activities:
            self.append(activity)

    def append(self, activity: Activity) -> None:
        if activity.activity_id in self._ids:
            raise DuplicateActivityError(f"activity duplicada: {activity.activity_id}")
        if activity.correction_of is not None:
            original = self._by_id.get(activity.correction_of)
            if original is None:
                raise ValueError(f"activity corrigida não encontrada: {activity.correction_of}")
            if original.is_reversal:
                raise ValueError("não é permitido reverter uma reversão")
            if original.activity_id in self._reversed:
                raise ValueError(f"activity já revertida: {original.activity_id}")
            if activity.reversal_payload() != original.reversal_payload():
                raise ValueError("payload da reversão diverge da activity original")
            self._reversed.add(original.activity_id)
        self._activities.append(activity)
        self._ids.add(activity.activity_id)
        self._by_id[activity.activity_id] = activity
        self._integrity_checked = False

    def activities(self, as_of: datetime | None = None) -> tuple[Activity, ...]:
        self.validate_integrity()
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

    def validate_integrity(self) -> None:
        if self._integrity_checked:
            return
        pairs = {
            ActivityKind.CASH_TRANSFER_IN: ActivityKind.CASH_TRANSFER_OUT,
            ActivityKind.CASH_TRANSFER_OUT: ActivityKind.CASH_TRANSFER_IN,
            ActivityKind.POSITION_TRANSFER_IN: ActivityKind.POSITION_TRANSFER_OUT,
            ActivityKind.POSITION_TRANSFER_OUT: ActivityKind.POSITION_TRANSFER_IN,
        }
        for activity in self._activities:
            if activity.is_reversal:
                continue
            expected = pairs.get(activity.kind)
            if expected is None:
                continue
            assert activity.related_activity_id is not None
            related = self._by_id.get(activity.related_activity_id)
            if related is None:
                raise ValueError(f"transferência sem par: {activity.activity_id}")
            if (
                related.kind is not expected
                or related.related_activity_id != activity.activity_id
                or related.account_id != activity.related_account_id
                or related.related_account_id != activity.account_id
            ):
                raise ValueError(f"par de transferência inconsistente: {activity.activity_id}")
            if (activity.activity_id in self._reversed) != (
                related.activity_id in self._reversed
            ):
                raise ValueError("reversão de transferência exige as duas pernas")
            if activity.kind in {ActivityKind.CASH_TRANSFER_IN, ActivityKind.CASH_TRANSFER_OUT}:
                if activity.gross_amount != related.gross_amount:
                    raise ValueError(f"valores da transferência divergem: {activity.activity_id}")
            elif (
                activity.instrument_id != related.instrument_id
                or activity.quantity != related.quantity
            ):
                raise ValueError(f"posições da transferência divergem: {activity.activity_id}")
        self._integrity_checked = True

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
