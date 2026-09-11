import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from marko.experiment import local_runner
from marko.experiment.store import write_json


class Friday(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return datetime(2026, 9, 11, 22, tzinfo=UTC)


class Monday(datetime):
    @classmethod
    def now(cls, tz: Any = None) -> datetime:
        return datetime(2026, 9, 14, 22, tzinfo=UTC)


def test_missing_observation_does_not_call_subscription(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(local_runner, "verify_campaign", lambda root: [])
    monkeypatch.setattr(local_runner, "run_local_reviews", lambda *a, **kw: pytest.fail("no data"))
    assert local_runner.review_latest(tmp_path)["status"] == "pending_observation"


@pytest.mark.parametrize("clock,with_code", [(Friday, True), (Monday, False)])
def test_reviews_use_verified_records_and_weekly_explicit_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    clock: type[datetime],
    with_code: bool,
) -> None:
    record = {"session": "2026-09-11", "record_hash": "frozen-hash"}
    write_json(tmp_path / "manifest.json", {"campaign": {"end_date": "2027-03-14"}})
    monkeypatch.setattr(local_runner, "datetime", clock)
    monkeypatch.setattr(local_runner, "verify_campaign", lambda root: [record])

    def review(
        current: dict[str, Any], history: list[Any], root: Path, *, code_sources: Any
    ) -> Any:
        assert current is record and history == [record] and root == tmp_path
        assert bool(code_sources) == with_code
        if with_code:
            assert set(code_sources) == {
                "src/marko/experiment/engine.py",
                "src/marko/experiment/market.py",
            }
            assert all(isinstance(source, str) and source for source in code_sources.values())
        return [
            {"role": "risk", "status": "completed"},
            {"role": "methodology", "status": "completed"},
        ]

    monkeypatch.setattr(local_runner, "run_local_reviews", review)
    result = local_runner.review_latest(tmp_path)
    assert result["status"] == "completed"
    assert result["api_cost_usd"] == 0
    assert result["decisions_modified"] is False
    assert record == {"session": "2026-09-11", "record_hash": "frozen-hash"}


def test_campaign_after_grace_period_does_not_call_subscription(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_json(tmp_path / "manifest.json", {"campaign": {"end_date": "2026-09-01"}})
    monkeypatch.setattr(local_runner, "datetime", Friday)
    monkeypatch.setattr(local_runner, "verify_campaign", lambda root: [{"session": "2026-09-01"}])
    monkeypatch.setattr(local_runner, "run_local_reviews", lambda *a, **kw: pytest.fail("closed"))
    assert local_runner.review_latest(tmp_path)["status"] == "campaign_closed"


def test_cli_failure_writes_sanitized_health_and_failure_exit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail(root: Path) -> list[Any]:
        raise ValueError("private-data-must-not-leak")

    monkeypatch.setattr(local_runner, "verify_campaign", fail)
    monkeypatch.setattr(sys, "argv", ["local_runner", "--state-dir", str(tmp_path)])
    assert local_runner.main() == 1
    health = json.loads((tmp_path / "local-health.json").read_text())
    assert health["status"] == "pending" and health["error_type"] == "ValueError"
    assert "private-data" not in capsys.readouterr().out
