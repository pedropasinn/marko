import csv
from pathlib import Path
from typing import Any

import pytest

from marko.experiment.reporting import render_report, write_reports

CAMPAIGN = {
    "campaign_id": "six-month",
    "start_date": "2026-09-14",
    "end_date": "2027-03-14",
    "initial_capital_usd": "10000",
}


def row(session: str, nav: str, status: str = "ok") -> dict[str, Any]:
    return {
        "campaign_id": "six-month",
        "session": session,
        "status": status,
        "record_hash": "hash",
        "metrics": [
            {
                "model_id": "baseline",
                "nav_usd": nav,
                "pnl_usd": str(float(nav) - 10000),
                "return_pct": (float(nav) / 10000 - 1) * 100,
                "drawdown_pct": 2.5,
                "costs_usd": "2.50",
            }
        ],
    }


def test_weekly_return_uses_prior_week_close_not_first_mark() -> None:
    report = render_report(
        [
            row("2026-09-18", "10100"),
            row("2026-09-21", "10300"),
            row("2026-09-25", "10400"),
        ],
        CAMPAIGN,
        [],
    )
    assert "+2.97%" in report
    assert "+4.00%" in report
    assert "2.50%" in report


def test_first_week_uses_initial_capital_and_never_sums_models() -> None:
    record = row("2026-09-18", "10100")
    record["metrics"].append(record["metrics"][0] | {"model_id": "challenger"})
    report = render_report([record], CAMPAIGN, [])
    assert report.count("10,100.00") == 2
    assert "20,200.00" not in report
    assert "+1.00%" in report


def test_preflight_and_blocked_do_not_create_performance() -> None:
    report = render_report(
        [row("2026-09-14", "999999", "preflight"), row("2026-09-15", "999999", "blocked")],
        CAMPAIGN,
        [],
    )
    assert "desempenho" in report.lower()
    assert "não há marca válida" in report
    assert "999,999" not in report


def test_missing_sessions_pending_reviews_and_stale_marks_are_explicit() -> None:
    reviews = [
        {
            "campaign_id": "six-month",
            "session": "2026-09-21",
            "role": "risk",
            "status": "pending_credentials",
            "model": "example",
        }
    ]
    report = render_report(
        [row("2026-09-18", "10100"), row("2026-09-21", "1", "blocked")],
        CAMPAIGN | {"expected_sessions": ["2026-09-18", "2026-09-21"]},
        reviews,
    )
    assert "Sessões esperadas sem execução válida: 2026-09-21" in report
    assert "sem marca na semana" in report
    assert "pendente de credencial" in report
    assert "Pareceres concluídos: 0" in report


def test_writes_separate_daily_weekly_and_csv_artifacts(tmp_path: Path) -> None:
    records = [row("2026-09-18", "10100"), row("2026-09-25", "10400")]
    paths = write_reports(records, CAMPAIGN, [], tmp_path)
    assert {path.name for path in paths} == {
        "current.md",
        "2026-09-18.md",
        "2026-09-25.md",
        "2026-W38.md",
        "2026-W39.md",
        "performance.csv",
    }
    assert "10,400.00" not in (tmp_path / "weekly/2026-W38.md").read_text()
    assert "+2.97%" in (tmp_path / "weekly/2026-W39.md").read_text()
    with (tmp_path / "performance.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == 2


def test_report_rejects_mixed_campaigns() -> None:
    with pytest.raises(ValueError, match="misturar"):
        render_report([row("2026-09-18", "10100") | {"campaign_id": "other"}], CAMPAIGN, [])


def test_report_does_not_count_rules_as_ai() -> None:
    report = render_report(
        [row("2026-09-18", "10100")],
        CAMPAIGN,
        [
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "rules_risk",
                "status": "completed",
                "backend": "deterministic_rules",
            },
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "risk",
                "status": "pending_budget",
            },
        ],
    )
    assert "Pareceres concluídos: 0 por IA" in report
    assert "Verificações por regras concluídas: 1 (não são IA)" in report
    assert "política de custo zero" in report


def test_disabled_api_is_not_missing_review_when_same_record_has_local_result() -> None:
    report = render_report(
        [row("2026-09-18", "10100")],
        CAMPAIGN,
        [
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "risk",
                "record_hash": "hash",
                "status": "completed",
                "backend": "codex_subscription",
            },
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "risk",
                "record_hash": "hash",
                "status": "pending_budget",
            },
        ],
    )
    assert "Pendentes ou falhos: 0" in report
    assert "Revisões por API desativadas: 1" in report
    assert "Pareceres concluídos: 1 por IA" in report


def test_different_record_local_review_does_not_cover_pending_record() -> None:
    report = render_report(
        [row("2026-09-18", "10100")],
        CAMPAIGN,
        [
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "risk",
                "record_hash": "old-hash",
                "status": "completed",
                "backend": "codex_subscription",
            },
            {
                "campaign_id": "six-month",
                "session": "2026-09-18",
                "role": "risk",
                "record_hash": "hash",
                "status": "pending_budget",
            },
        ],
    )
    assert "Pendentes ou falhos: 1" in report


def test_completed_final_session_is_not_missing() -> None:
    report = render_report(
        [row("2026-09-18", "10100", "completed")],
        CAMPAIGN | {"expected_sessions": ["2026-09-18"]},
        [],
    )
    assert "Sessões esperadas sem execução válida: nenhuma" in report


def test_current_shows_missing_sessions_after_latest_mark_but_history_does_not(
    tmp_path: Path,
) -> None:
    write_reports(
        [row("2026-09-18", "10100")],
        CAMPAIGN | {"expected_sessions": ["2026-09-18", "2026-09-21"]},
        [],
        tmp_path,
    )
    current = (tmp_path / "current.md").read_text()
    assert "Avaliação consultada até 2026-09-21" in current
    assert "Sessões esperadas sem execução válida: 2026-09-21" in current
    for name in ("daily/2026-09-18.md", "weekly/2026-W38.md"):
        historical = (tmp_path / name).read_text()
        assert "2026-09-21" not in historical
        assert "Sessões esperadas sem execução válida: nenhuma" in historical
