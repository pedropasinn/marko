import json
import socket
import subprocess
import sys
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from marko.experiment import runner
from marko.experiment.config import digest, load_campaign
from marko.experiment.market import schedule
from marko.experiment.reviews import read_reviews
from marko.experiment.store import read_records, write_json

IDENTITY = {"code_version": "a" * 40, "lock_hash": "b" * 64}
CONFIG = """campaign_id = "runner-test"
start_date = "2026-09-14"
end_date = "2026-09-18"
initial_capital_usd = "10000"
currency = "USD"
real_capital = false
symbols = ["SPY", "IEF"]
models = ["equal_weight"]
benchmarks = ["cash", "spy_buy_hold", "sixty_forty"]
maximum_weight = 0.6
training_sessions = 30
transaction_cost_bps = "5"
calendar = "NYSE"
rebalance = "month_end"
dividend_policy = "receivable_not_reinvested"
"""


@pytest.fixture
def campaign(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    config_path = tmp_path / "campaign.toml"
    config_path.write_text(CONFIG)
    clock = {"now": datetime(2026, 9, 11, 22, tzinfo=UTC)}
    calls: list[date] = []
    api_calls: list[Any] = []

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:
            return clock["now"].astimezone(tz or UTC)

    def forbidden_api(*args: Any, **kwargs: Any) -> None:
        api_calls.append((args, kwargs))
        raise AssertionError("APIs e rede são proibidas neste teste")

    def download(config: dict[str, Any], session: date, root: Path) -> dict[str, Any]:
        calls.append(session)
        days = list(schedule(date(2026, 7, 1), session))
        snapshot = {
            "provider": "fixture-only",
            "session": session.isoformat(),
            "observed_at": clock["now"].isoformat(),
            "bars": {
                symbol: {
                    day: {
                        "open": str(100 + i / 10),
                        "close": str(100 + i / 10),
                        "adjusted_close": str(100 + i / 10),
                        "dividend": "0",
                        "split": "0",
                    }
                    for i, day in enumerate(days)
                }
                for symbol in config["symbols"]
            },
        }
        snapshot["data_hash"] = digest(snapshot)
        write_json(root / "snapshots" / f"{snapshot['data_hash']}.json", snapshot, immutable=True)
        return snapshot

    monkeypatch.setattr(runner, "datetime", Clock)
    monkeypatch.setattr(runner, "source_identity", lambda: IDENTITY.copy())
    monkeypatch.setattr(runner, "fetch_snapshot", download)
    monkeypatch.setattr("marko.experiment.reviews._request", forbidden_api)
    monkeypatch.setattr(socket.socket, "connect", forbidden_api)
    monkeypatch.setenv("MARKO_REVIEW_API_KEY", "test-key-must-never-be-used")
    yield {
        "path": config_path,
        "root": tmp_path / "state",
        "clock": clock,
        "downloads": calls,
        "api_calls": api_calls,
        "download": download,
    }
    assert api_calls == []


def test_real_campaign_preflight_recovery_and_completion_are_idempotent(
    campaign: dict[str, Any],
) -> None:
    root, path = campaign["root"], campaign["path"]
    first = runner.run_campaign(path, root, code_review=True)
    assert first["status"] == "ok"
    assert first["last_session"] == "2026-09-11"
    preflight = read_records(root)[0]
    assert preflight["status"] == "preflight"
    assert all(d["execute_session"] == "2026-09-14" for d in preflight["decisions"])
    assert all(d["action"] == "SCHEDULED" for d in preflight["decisions"])
    original = (root / "records/2026-09-11.json").read_bytes()
    repeated = runner.run_campaign(path, root)
    assert repeated["records"] == 1
    assert len(campaign["downloads"]) == 1
    assert (root / "records/2026-09-11.json").read_bytes() == original

    campaign["clock"]["now"] = datetime(2026, 9, 15, 22, tzinfo=UTC)
    recovered = runner.run_campaign(path, root)
    assert recovered["status"] == "ok"
    records = runner.verify_campaign(root)
    assert [r["session"] for r in records] == ["2026-09-11", "2026-09-14", "2026-09-15"]
    assert records[1]["actions"]
    assert all(a["session"] == "2026-09-14" for a in records[1]["actions"])
    assert all(d["action"] == "NO_ACTION" for r in records[1:] for d in r["decisions"])
    assert records[1]["warnings"]

    campaign["clock"]["now"] = datetime(2026, 9, 18, 22, tzinfo=UTC)
    finished = runner.run_campaign(path, root)
    assert finished["completed"]
    assert finished["status"] == "ok"
    assert finished["records"] == 6
    assert (root / "reports/performance.csv").is_file()
    assert list((root / "reports/weekly").glob("*.md"))
    assert all(r.get("status") != "started" for r in read_reviews(root))
    assert any(r["status"] == "pending_budget" for r in read_reviews(root))
    assert finished["api_budget_usd"] == 0


def test_campaign_consumes_real_market_adapter_with_only_provider_download_mocked(
    campaign: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pandas as pd
    import yfinance as yf

    from marko.experiment import market

    days = list(schedule(date(2026, 7, 1), date(2026, 9, 11)))
    frame = pd.concat(
        {
            symbol: pd.DataFrame(
                {
                    "Open": [100.0 + i / 10 for i in range(len(days))],
                    "Close": [100.0 + i / 10 for i in range(len(days))],
                    "Adj Close": [100.0 + i / 10 for i in range(len(days))],
                    "Dividends": [0.0] * len(days),
                    "Stock Splits": [0.0] * len(days),
                },
                index=pd.to_datetime(days),
            )
            for symbol in ("SPY", "IEF")
        },
        axis=1,
    )
    downloads: list[dict[str, Any]] = []

    def download(*args: Any, **kwargs: Any) -> Any:
        downloads.append(kwargs)
        return frame

    monkeypatch.setattr(yf, "download", download)
    monkeypatch.setattr(market, "datetime", runner.datetime)
    monkeypatch.setattr(runner, "fetch_snapshot", market.fetch_snapshot)
    result = runner.run_campaign(campaign["path"], campaign["root"])
    assert result["status"] == "ok"
    assert len(downloads) == 1
    records = runner.verify_campaign(campaign["root"])
    snapshot = json.loads(
        (campaign["root"] / "snapshots" / f"{records[0]['data_hash']}.json").read_text()
    )
    assert snapshot["bars"]["SPY"][days[-1]]["close"] == str(100.0 + (len(days) - 1) / 10)
    assert all(
        decision["data_hash"] == snapshot["data_hash"] for decision in records[0]["decisions"]
    )


def test_late_registration_marks_gaps_and_never_fills_past_opens(campaign: dict[str, Any]) -> None:
    campaign["clock"]["now"] = datetime(2026, 9, 16, 22, tzinfo=UTC)
    result = runner.run_campaign(campaign["path"], campaign["root"])
    assert result["status"] == "degraded"
    assert result["missing_sessions"] == ["2026-09-14", "2026-09-15"]
    record = read_records(campaign["root"])[0]
    assert record["session"] == "2026-09-16"
    assert record["actions"] == []
    assert all(d["execute_session"] == "2026-09-17" for d in record["decisions"])


def test_registration_after_end_and_post_close_publication_window_block(
    campaign: dict[str, Any],
) -> None:
    campaign["clock"]["now"] = datetime(2026, 9, 21, 22, tzinfo=UTC)
    with pytest.raises(ValueError, match="encerrada antes"):
        runner.run_campaign(campaign["path"], campaign["root"])
    assert not (campaign["root"] / "manifest.json").exists()
    campaign["clock"]["now"] = datetime(2026, 9, 14, 20, 20, tzinfo=UTC)
    with pytest.raises(ValueError, match="45 minutos"):
        runner.run_campaign(campaign["path"], campaign["root"])
    assert campaign["downloads"] == []


def test_manifest_freezes_code_lock_and_config_and_checks_record_dependencies(
    campaign: dict[str, Any],
) -> None:
    root, path = campaign["root"], campaign["path"]
    runner.run_campaign(path, root)
    config = load_campaign(path)
    for identity in (IDENTITY | {"code_version": "c" * 40}, IDENTITY | {"lock_hash": "d" * 64}):
        with pytest.raises(ValueError, match="congelada"):
            runner.ensure_manifest(root, config, identity, campaign["clock"]["now"])
    with pytest.raises(ValueError, match="congelada"):
        runner.ensure_manifest(
            root, config | {"maximum_weight": 0.7}, IDENTITY, campaign["clock"]["now"]
        )
    with pytest.raises(ValueError, match="configuração solicitada"):
        runner.generate_reports(
            root, config | {"maximum_weight": 0.7}, {}, campaign["clock"]["now"]
        )
    record = read_records(root)[0]
    model = next(d for d in record["decisions"] if d["model_run_id"])
    model_path = root / "model-runs" / f"{model['model_run_id']}.json"
    model_path.rename(model_path.with_suffix(".unavailable"))
    with pytest.raises(FileNotFoundError):
        runner.verify_campaign(root)


def test_model_failure_degrades_health_and_successful_retry_clears_it(
    campaign: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    import marko.experiment.engine as engine

    original = engine.model_weights

    def fail_model(model_id: str, *args: Any) -> Any:
        if model_id == "equal_weight":
            raise ValueError("fixture solver failure")
        return original(model_id, *args)

    monkeypatch.setattr(engine, "model_weights", fail_model)
    first = runner.run_campaign(campaign["path"], campaign["root"])
    assert first["status"] == "degraded"
    assert first["model_failures"] == ["equal_weight"]
    campaign["clock"]["now"] = datetime(2026, 9, 14, 22, tzinfo=UTC)
    monkeypatch.setattr(engine, "model_weights", original)
    second = runner.run_campaign(campaign["path"], campaign["root"])
    assert second["model_failures"] == []
    assert second["status"] == "ok"
    wallet = read_records(campaign["root"])[-1]["portfolios"]["equal_weight"]
    assert not wallet["initialized"]
    assert wallet["pending"]["execute_session"] == "2026-09-15"


def test_window_crossed_during_computation_is_not_committed(
    campaign: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    original = runner.process_session

    def crosses_open(*args: Any, **kwargs: Any) -> Any:
        result = original(*args, **kwargs)
        campaign["clock"]["now"] = datetime(2026, 9, 14, 13, 30, tzinfo=UTC)
        return result

    monkeypatch.setattr(runner, "process_session", crosses_open)
    with pytest.raises(ValueError, match="janela prospectiva"):
        runner.run_campaign(campaign["path"], campaign["root"])
    assert read_records(campaign["root"]) == []


@pytest.mark.parametrize("command", ["run", "verify", "report"])
def test_cli_commands_and_sanitized_provider_failure(
    campaign: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
) -> None:
    path, root = campaign["path"], campaign["root"]
    runner.run_campaign(path, root)
    monkeypatch.setattr(
        sys, "argv", ["marko-experiment", command, "--config", str(path), "--state-dir", str(root)]
    )
    assert runner.main() == 0
    assert json.loads(capsys.readouterr().out)["status"] in {"ok", "verified"}
    if command == "run":
        campaign["clock"]["now"] = datetime(2026, 9, 14, 22, tzinfo=UTC)

        def failed_provider(*args: Any) -> None:
            raise RuntimeError("https://private.invalid/?token=DO_NOT_PERSIST")

        monkeypatch.setattr(runner, "fetch_snapshot", failed_provider)
        assert runner.main() == 1
        output = capsys.readouterr().out
        assert "DO_NOT_PERSIST" not in output
        assert "private.invalid" not in (root / "health.json").read_text()
        assert json.loads(output)["error_code"] == "operation_failed"


def test_pending_sessions_empty_and_error_codes_are_explicit() -> None:
    assert runner.pending_sessions({"end_date": "2026-09-18"}, [], []) == []
    assert (
        runner.operational_error_code(FileNotFoundError("/private/path"))
        == "required_artifact_missing"
    )
    assert (
        runner.operational_error_code(ValueError("campanha congelada")) == "frozen_contract_changed"
    )
    assert (
        runner.operational_error_code(subprocess.CalledProcessError(1, ["git"]))
        == "source_checkout_unavailable"
    )


def test_source_identity_uses_real_clean_git_tree_and_lock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "checkout"
    module = source / "src/marko/experiment/runner.py"
    module.parent.mkdir(parents=True)
    module.write_text("# fixture\n")
    (source / "uv.lock").write_text("version = 1\n")
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "add", "."], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-qm",
            "fixture",
        ],
        check=True,
    )
    monkeypatch.setattr(runner, "__file__", str(module))
    identity = runner.source_identity()
    assert len(identity["code_version"]) == 40
    assert len(identity["lock_hash"]) == 64
    module.write_text("# changed\n")
    with pytest.raises(ValueError, match="checkout limpo"):
        runner.source_identity()
