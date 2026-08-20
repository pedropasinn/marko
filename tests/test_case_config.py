from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from marko.case_config import PersonalCase, load_case
from marko.money import Money


def test_repository_case_preserves_known_facts_and_blocks_unknowns() -> None:
    case = load_case(Path("config/personal-case.toml"))
    assert case.principal == Money.of("50000", "BRL")
    assert case.monthly_contribution == Money.of("2000", "BRL")
    assert "campo ausente: maturity_date" in case.readiness_issues()
    with pytest.raises(ValueError, match="caso incompleto"):
        case.to_liability()


def test_complete_fixed_rate_case_builds_compounded_liability() -> None:
    case = PersonalCase(
        "BRL",
        Money.of("50000", "BRL"),
        "Mãe",
        Money.of("2000", "BRL"),
        date(2026, 1, 1),
        date(2027, 1, 1),
        "fixed:0.10",
        False,
        Money.of("10000", "BRL"),
        Decimal("0.20"),
        ("broker",),
        ("CDI",),
        "BR",
    )
    assert case.readiness_issues() == ()
    assert case.to_liability().cashflows[0].amount == Money.of("55000", "BRL")
    policy = case.to_policy(datetime(2026, 1, 1, tzinfo=UTC))
    assert policy.liability_ids == ("family-loan",)
    assert case.to_universe(date(2026, 1, 1)).eligible_instruments() == ("CDI",)
