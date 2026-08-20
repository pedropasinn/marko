from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from marko.__main__ import main
from marko.case_config import PersonalCase, load_case
from marko.liabilities import (
    Compounding,
    DayCountConvention,
    InterestRounding,
    InterestTerms,
    PaymentFrequency,
)
from marko.money import Money


def test_repository_case_preserves_known_facts_and_blocks_unknowns() -> None:
    case = load_case(Path("config/personal-case.example.toml"))
    assert case.principal == Money.of("25000", "BRL")
    assert case.monthly_contribution == Money.of("1000", "BRL")
    assert "campo ausente: maturity_date" in case.readiness_issues()
    with pytest.raises(ValueError, match="caso incompleto"):
        case.to_liability()


def test_complete_fixed_rate_case_builds_compounded_liability() -> None:
    case = PersonalCase(
        "BRL",
        Money.of("25000", "BRL"),
        "Credor sintético",
        Money.of("1000", "BRL"),
        date(2026, 1, 1),
        date(2027, 1, 1),
        InterestTerms(
            Decimal("0.10"),
            Compounding.ANNUAL,
            DayCountConvention.ACTUAL_365,
            PaymentFrequency.AT_MATURITY,
            InterestRounding.HALF_EVEN,
        ),
        False,
        Money.of("10000", "BRL"),
        Decimal("0.20"),
        ("broker",),
        ("CDI",),
        "BR",
    )
    assert case.readiness_issues() == ()
    assert case.to_liability().cashflows[0].amount == Money.of("27500", "BRL")
    policy = case.to_policy(datetime(2026, 1, 1, tzinfo=UTC))
    assert policy.liability_ids == ("family-loan",)
    assert case.to_universe(date(2026, 1, 1)).eligible_instruments() == ("CDI",)


def test_cli_status_uses_environment_case_path(tmp_path: Path, monkeypatch, capsys) -> None:
    case_path = tmp_path / "case.toml"
    case_path.write_text(Path("config/personal-case.example.toml").read_text())
    monkeypatch.setenv("MARKO_CASE_PATH", str(case_path))
    assert main(["status"]) == 0
    output = capsys.readouterr().out
    assert str(case_path) in output
    assert '"ready": false' in output


def test_cli_status_returns_json_error_for_missing_file(tmp_path: Path, capsys) -> None:
    assert main(["status", "--case", str(tmp_path / "missing.toml")]) == 2
    assert '"error"' in capsys.readouterr().err
