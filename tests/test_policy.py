from datetime import UTC, date, datetime
from decimal import Decimal

import pytest

from marko.money import Money
from marko.policy import (
    Constraint,
    ConstraintKind,
    ConstraintSet,
    InvestmentPolicy,
    Universe,
    UniverseItem,
)


def test_policy_carries_liability_and_real_capital_gate() -> None:
    policy = InvestmentPolicy(
        policy_id="personal-ips",
        version=1,
        effective_from=date(2026, 8, 20),
        approved_at=datetime(2026, 8, 20, tzinfo=UTC),
        base_currency="brl",
        horizon_end=date(2030, 8, 20),
        minimum_liquidity=Money.of("15000", "BRL"),
        maximum_drawdown=Decimal("0.20"),
        liability_ids=("loan-mother",),
    )
    assert policy.base_currency == "BRL"
    assert policy.real_capital_enabled is False


def test_constraint_set_rejects_invalid_or_duplicate_bounds() -> None:
    with pytest.raises(ValueError):
        Constraint("equity", ConstraintKind.WEIGHT, Decimal("0.6"), Decimal("0.4"))
    duplicated = Constraint("equity", ConstraintKind.WEIGHT, Decimal(0), Decimal("0.5"))
    with pytest.raises(ValueError):
        ConstraintSet("ips", 1, (duplicated, duplicated))


def test_universe_filters_temporal_eligibility() -> None:
    universe = Universe(
        universe_id="br-personal",
        version=1,
        as_of=date(2026, 8, 20),
        items=(
            UniverseItem("CDI", date(2020, 1, 1)),
            UniverseItem("OLD", date(2020, 1, 1), date(2025, 12, 31)),
            UniverseItem("FUTURE", date(2027, 1, 1)),
        ),
    )
    assert universe.eligible_instruments() == ("CDI",)


def test_policy_rejects_currency_mismatch() -> None:
    with pytest.raises(ValueError):
        InvestmentPolicy(
            "ips",
            1,
            date(2026, 1, 1),
            datetime(2026, 1, 1, tzinfo=UTC),
            "BRL",
            date(2027, 1, 1),
            Money.of(1, "USD"),
            Decimal("0.1"),
            (),
        )
