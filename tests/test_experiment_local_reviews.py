import json
from pathlib import Path
from typing import Any

import pytest

from marko.experiment import local_reviews
from marko.experiment.reviews import read_reviews


def record() -> dict[str, Any]:
    return {
        "campaign_id": "local-test",
        "session": "2026-09-11",
        "code_version": "abc123",
        "observed_at": "2026-09-11T22:00:00+00:00",
        "knowledge_cutoff": "2026-09-11T21:00:00+00:00",
        "record_hash": "hash",
        "status": "preflight",
        "metrics": [],
        "actions": [],
        "decisions": [],
        "portfolios": {},
    }


def test_subscription_command_and_environment_do_not_enable_api_or_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "not-authorized")
    monkeypatch.setenv("CODEX_API_KEY", "not-authorized")
    monkeypatch.setenv("MARKO_REVIEW_API_KEY", "not-authorized")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "not-authorized")
    assert not any("API_KEY" in key for key in local_reviews._environment())
    command = local_reviews._command("/usr/bin/codex", tmp_path)
    assert 'forced_login_method="chatgpt"' in command
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command
    assert "--ignore-rules" in command
    assert "--ephemeral" in command
    assert "--dangerously-bypass-approvals-and-sandbox" not in command


def test_local_reviews_are_separate_idempotent_and_loaded_by_reports(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    prompts = []

    def invoke(prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
        prompts.append(prompt)
        return (
            {
                "verdict": "insufficient",
                "summary": "Sem execução prospectiva.",
                "findings": [],
                "limitations": ["Fixture."],
            },
            {"status": "completed", "cli_version": "test", "tools_used": False},
        )

    monkeypatch.setattr(local_reviews, "_invoke", invoke)
    rows = local_reviews.run_local_reviews(record(), [], tmp_path)
    assert len(rows) == len(prompts) == 2
    assert local_reviews.run_local_reviews(record(), [], tmp_path) == rows
    assert len(prompts) == 2
    assert len(list((tmp_path / "reviews/local").glob("*.json"))) == 2
    assert not (tmp_path / "reviews.jsonl").exists()
    assert all(row["backend"] == "codex_subscription" for row in read_reviews(tmp_path))
    assert all(row["api_cost_usd"] == "0" for row in rows)
    assert prompts[0].split("EVIDÊNCIAS:")[1] == prompts[1].split("EVIDÊNCIAS:")[1]
    assert "Sem execução prospectiva" not in prompts[1]


def test_quota_failure_remains_pending_without_retries_same_day(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def invoke(prompt: str) -> tuple[None, dict[str, Any]]:
        calls.append(prompt)
        return None, {"status": "pending_local_quota", "reason": "subscription_limit"}

    monkeypatch.setattr(local_reviews, "_invoke", invoke)
    first = local_reviews.run_local_reviews(record(), [], tmp_path)
    second = local_reviews.run_local_reviews(record(), [], tmp_path)
    assert first == second
    assert len(calls) == 2
    assert all("result" not in row for row in first)
    assert "pending_local_quota" in json.dumps(read_reviews(tmp_path))
