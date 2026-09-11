import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import URLError

import pytest

from marko.experiment import reviews


def record() -> dict[str, Any]:
    return {
        "campaign_id": "six-month",
        "session": "2026-09-14",
        "code_version": "abc123",
        "observed_at": "2026-09-14T22:00:00+00:00",
        "knowledge_cutoff": "2026-09-14T21:00:00+00:00",
        "record_hash": "hash",
        "status": "ok",
        "metrics": [],
        "actions": [],
        "decisions": [],
        "portfolios": {},
    }


def response() -> dict[str, Any]:
    return {
        "status": "completed",
        "usage": {"input_tokens": 200, "output_tokens": 100},
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": json.dumps(
                            {
                                "verdict": "insufficient",
                                "summary": "Faltam marcas de carteira.",
                                "findings": [],
                                "limitations": ["Sem dados de mercado no pacote."],
                            }
                        ),
                    }
                ],
            }
        ],
    }


@pytest.fixture(autouse=True)
def clear_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("MARKO_REVIEW_API_KEY", raising=False)


def test_missing_credentials_are_pending_and_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rows = reviews.run_reviews(record(), [], tmp_path, 1)
    assert [row["status"] for row in rows] == ["pending_credentials"] * 2
    assert not (tmp_path / "review-budget.jsonl").exists()
    monkeypatch.setenv("MARKO_REVIEW_API_KEY", "test-private-key")
    monkeypatch.setattr(reviews, "_request", lambda payload, key: response())
    done = reviews.run_reviews(record(), [], tmp_path, 1)
    assert all(row["status"] == "completed" for row in done)
    assert all(row["status"] == "completed" for row in reviews.read_reviews(tmp_path))
    assert "test-private-key" not in (tmp_path / "reviews.jsonl").read_text()


def test_calls_are_independent_strict_bounded_and_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def transport(payload: dict[str, Any], key: str) -> dict[str, Any]:
        calls.append(payload)
        assert key == "private"
        return response()

    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", transport)
    results = reviews.run_reviews(record(), [], tmp_path, 1)
    repeated = reviews.run_reviews(record(), [], tmp_path, 1)
    assert repeated == results
    assert len(calls) == 2
    assert calls[0]["input"] == calls[1]["input"]
    assert calls[0]["instructions"] != calls[1]["instructions"]
    assert "Faltam marcas" not in calls[1]["input"]
    for call in calls:
        assert call["store"] is False
        assert "tools" not in call
        assert call["text"]["format"]["strict"] is True
        assert call["max_output_tokens"] == reviews.MAX_OUTPUT_TOKENS
    assert all(row["authority"] == "advisory_only" for row in results)
    assert all("estimated_cost_usd" in row for row in results)


def test_zero_and_exhausted_monthly_budget_make_no_network_calls(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def transport(payload: dict[str, Any], key: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return response()

    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", transport)
    assert all(
        row["status"] == "pending_budget" for row in reviews.run_reviews(record(), [], tmp_path)
    )
    assert calls == 0
    first = reviews.run_reviews(record(), [], tmp_path, "0.0045")
    assert calls == 1
    assert {row["status"] for row in first} == {"completed", "pending_budget"}
    reviews.run_reviews(record() | {"session": "2026-09-15"}, [], tmp_path, "0.0045")
    assert calls == 1


def test_failed_requests_are_sanitized_reserved_and_not_retried(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fail(payload: dict[str, Any], key: str) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise URLError("private-secret-in-server-response")

    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", fail)
    result = reviews.run_reviews(record(), [], tmp_path, 1)
    reviews.run_reviews(record(), [], tmp_path, 1)
    assert calls == 2
    assert all(row["status"] == "error" for row in result)
    assert "private-secret" not in (tmp_path / "reviews.jsonl").read_text()
    assert len((tmp_path / "review-budget.jsonl").read_text().splitlines()) == 2


def test_budget_uses_current_billing_month_not_market_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", lambda payload, key: response())
    reviews.run_reviews(record(), [], tmp_path, 1, now=datetime(2026, 10, 1, tzinfo=UTC))
    assert all(
        json.loads(line)["month"] == "2026-10"
        for line in (tmp_path / "review-budget.jsonl").read_text().splitlines()
    )


@pytest.mark.parametrize(
    "bad",
    [
        {"status": "approved"},
        {"observed_at": "2026-09-14T22:00:00"},
        {"portfolios": {"api_key": "private"}},
        {"metrics": [{"nav_usd": float("nan")}]},
        {"decisions": ["x" * reviews.MAX_INPUT_BYTES]},
    ],
)
def test_rejects_invalid_payload_before_writes(tmp_path: Path, bad: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        reviews.run_reviews(record() | bad, [], tmp_path)
    assert not list(tmp_path.iterdir())


def test_rejects_future_history_unpriced_models_and_private_sources(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="posterior"):
        reviews.run_reviews(record(), [record() | {"session": "2026-09-15"}], tmp_path)
    with pytest.raises(ValueError, match="preço"):
        reviews.run_reviews(record(), [], tmp_path, models={"risk": "unknown-model"})
    with pytest.raises(ValueError, match="escopo"):
        reviews.run_reviews(record(), [], tmp_path, code_sources={".env": "secret"})


def test_code_review_receives_only_explicit_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict[str, Any]] = []

    def transport(payload: dict[str, Any], key: str) -> dict[str, Any]:
        calls.append(payload)
        return response()

    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", transport)
    results = reviews.run_reviews(
        record(), [], tmp_path, 1, {"src/marko/example.py": "raise RuntimeError('not executed')"}
    )
    assert len(results) == len(calls) == 3
    assert all("code_sources" not in json.loads(call["input"]) for call in calls[:2])
    assert "code_sources" in json.loads(calls[2]["input"])
    assert results[-1]["role"] == "code"


def test_invalid_structured_response_is_not_a_completed_review(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad = response()
    bad["output"][0]["content"][0]["text"] = '{"verdict":"pass","execute":"buy"}'
    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setattr(reviews, "_request", lambda payload, key: bad)
    assert all(row["status"] == "error" for row in reviews.run_reviews(record(), [], tmp_path, 1))


def test_rules_are_free_independent_and_do_not_mutate_record(tmp_path: Path) -> None:
    source = record() | {"previous_hash": None}
    source["record_hash"] = reviews.record_digest(
        {key: value for key, value in source.items() if key != "record_hash"}
    )
    before = json.dumps(source)
    result = reviews.run_rule_reviews(source, [], tmp_path)
    assert len(result) == 3
    assert all(row["status"] == "completed" for row in result)
    assert all(row["backend"] == "deterministic_rules" for row in result)
    assert all(row["estimated_cost_usd"] == "0" for row in result)
    assert {row["role"] for row in result} == {"rules_risk", "rules_methodology", "rules_integrity"}
    assert reviews.run_rule_reviews(source, [], tmp_path) == result
    assert len((tmp_path / "reviews.jsonl").read_text().splitlines()) == 3
    assert json.dumps(source) == before
    assert not (tmp_path / "review-budget.jsonl").exists()


def test_rules_find_cash_temporal_and_hash_errors_independently(tmp_path: Path) -> None:
    source = record() | {
        "portfolios": {"cash": {"cash": "-1", "units": {}}},
        "knowledge_cutoff": "2026-09-15T00:00:00+00:00",
    }
    result = reviews.run_rule_reviews(source, [], tmp_path)
    assert all(row["result"]["verdict"] == "fail" for row in result)
    by_role = {row["role"]: json.dumps(row["result"], ensure_ascii=False) for row in result}
    assert "saldo cash negativo" in by_role["rules_risk"]
    assert "Corte de conhecimento posterior" in by_role["rules_methodology"]
    assert "hash do registro não confere" in by_role["rules_integrity"]


def test_zero_cost_mode_never_calls_api_even_with_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(payload: dict[str, Any], key: str) -> dict[str, Any]:
        pytest.fail("Política zero custo não pode chamar API")

    monkeypatch.setattr(reviews, "_request", forbidden)
    monkeypatch.setenv("OPENAI_API_KEY", "existing-but-not-authorized")
    result = reviews.run_reviews(record(), [], tmp_path)
    assert all(row["status"] == "pending_budget" for row in result)
    assert all(row["reason"] == "zero_api_cost_policy" for row in result)
    assert not (tmp_path / "review-budget.jsonl").exists()
