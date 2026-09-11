import copy
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from marko.experiment.config import digest
from marko.experiment.engine import execute_target, model_weights, nav, process_session
from marko.experiment.market import training_returns
from marko.experiment.store import append_record, read_records, verify_artifacts, write_json
from marko.persistence.codec import SerializationEnvelope, decode_model_run

D = Decimal
DAYS = (
    "2026-09-08",
    "2026-09-09",
    "2026-09-10",
    "2026-09-11",
    "2026-09-14",
    "2026-09-15",
    "2026-09-16",
)
SESSIONS = {
    day: {"open": day + "T13:30:00+00:00", "close": day + "T20:00:00+00:00"} for day in DAYS
}


def config() -> dict[str, Any]:
    return {
        "campaign_id": "test-campaign",
        "initial_capital_usd": "10000",
        "symbols": ["SPY", "IEF"],
        "models": [],
        "benchmarks": ["cash", "spy_buy_hold", "sixty_forty"],
        "start_date": "2026-09-11",
        "end_date": "2026-09-16",
        "training_sessions": 2,
        "maximum_weight": 0.6,
        "transaction_cost_bps": "5",
    }


def snapshot(on: str, **changes: Any) -> dict[str, Any]:
    payload = {
        "provider": "test",
        "session": on,
        "observed_at": on + "T22:00:00+00:00",
        "bars": {
            symbol: {
                day: {
                    "open": "100",
                    "close": "100",
                    "adjusted_close": str(100 + i),
                    "dividend": "0",
                    "split": "0",
                }
                for i, day in enumerate(DAYS)
                if day <= on
            }
            for symbol in ("SPY", "IEF")
        },
    }
    payload.update(changes)
    payload["data_hash"] = digest(payload)
    return payload


def process(
    root: Path,
    on: str,
    data: dict[str, Any],
    previous: dict[str, Any] | None = None,
    campaign: dict[str, Any] | None = None,
) -> dict[str, Any]:
    write_json(root / "snapshots" / f"{data['data_hash']}.json", data, immutable=True)
    record = process_session(
        campaign or config(),
        data,
        SESSIONS,
        previous,
        on,
        datetime.fromisoformat(data["observed_at"]),
        "test",
        root,
    )
    return append_record(root, record)


def test_model_run_uses_canonical_envelope_and_can_be_reloaded(tmp_path: Path) -> None:
    data = snapshot("2026-09-10")
    weights, run_id = model_weights(
        "equal_weight", config(), data, datetime(2026, 9, 10, 22, tzinfo=UTC), "test", tmp_path
    )
    raw = (tmp_path / "model-runs" / f"{run_id}.json").read_text()
    run = decode_model_run(SerializationEnvelope.from_json(raw))
    assert run.candidate.weight_map() == weights
    assert run.dataset_fingerprint == data["data_hash"]


def test_sizing_preserves_targets_after_cost_and_does_not_spend_receivables() -> None:
    wallet = {"cash": "0", "receivables": "10", "units": {"SPY": "1", "IEF": "0"}, "costs": "0"}
    prices = {"SPY": "100", "IEF": "100"}
    trades = execute_target(wallet, {"SPY": 0.6, "IEF": 0.4}, prices, "100", "2026-09-11")
    liquid_nav = nav(wallet, prices) - D(10)
    assert float(D(wallet["units"]["SPY"]) * 100 / liquid_nav) == pytest.approx(0.6, abs=1e-8)
    assert float(D(wallet["units"]["IEF"]) * 100 / liquid_nav) == pytest.approx(0.4, abs=1e-8)
    assert nav(wallet, prices) == D(110) - sum((D(t["cost_usd"]) for t in trades), D(0))
    assert wallet["receivables"] == "10"
    assert D(wallet["cash"]) >= 0


def test_missed_initial_decision_retries_each_wallet_at_next_prospective_window(
    tmp_path: Path,
) -> None:
    data = snapshot("2026-09-11")
    missed = process(tmp_path, "2026-09-10", data)
    assert all(d["reason"] == "missed_decision_window" for d in missed["decisions"])
    retry = process(tmp_path, "2026-09-11", data, missed)
    assert all(d["action"] == "SCHEDULED" for d in retry["decisions"])
    assert all(d["execute_session"] == "2026-09-14" for d in retry["decisions"])
    assert retry["actions"] == []
    executed = process(tmp_path, "2026-09-14", snapshot("2026-09-14"), retry)
    assert all(w["initialized"] for w in executed["portfolios"].values())
    assert D(executed["portfolios"]["spy_buy_hold"]["units"]["SPY"]) > 0
    assert executed["portfolios"]["cash"]["cash"] == "10000"
    verify_artifacts(tmp_path)


def test_recovery_executes_only_preexisting_decisions_at_the_planned_open(tmp_path: Path) -> None:
    initial = process(tmp_path, "2026-09-10", snapshot("2026-09-10"))
    later = snapshot("2026-09-14")
    recovered = process(tmp_path, "2026-09-11", later, initial)
    assert recovered["actions"]
    assert all(action["session"] == "2026-09-11" for action in recovered["actions"])
    assert all(d["action"] == "NO_ACTION" for d in recovered["decisions"])
    assert all(w["pending"] is None for w in recovered["portfolios"].values())


def test_dividend_goes_to_pretrade_holder_and_remains_uninvested(tmp_path: Path) -> None:
    initial = process(tmp_path, "2026-09-10", snapshot("2026-09-10"))
    invested = process(tmp_path, "2026-09-11", snapshot("2026-09-11"), initial)
    data = snapshot("2026-09-14")
    data["bars"]["SPY"]["2026-09-14"].update(open="98", close="98", dividend="2")
    data["data_hash"] = digest({k: v for k, v in data.items() if k != "data_hash"})
    after = process(tmp_path, "2026-09-14", data, invested)
    old = invested["portfolios"]["spy_buy_hold"]
    new = after["portfolios"]["spy_buy_hold"]
    assert new["cash"] == old["cash"]
    assert D(new["receivables"]) == 2 * D(old["units"]["SPY"])
    assert nav(new, {"SPY": "98", "IEF": "100"}) == nav(old, {"SPY": "100", "IEF": "100"})


@pytest.mark.parametrize(
    "data",
    [
        snapshot("2026-09-10", observed_at="2026-09-10T19:59:00+00:00"),
        snapshot("2026-09-11", observed_at="2026-09-10T22:00:00+00:00"),
    ],
)
def test_snapshot_is_not_available_before_its_session_close(
    data: dict[str, Any], tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="futuro"):
        process_session(
            config(),
            data,
            SESSIONS,
            None,
            "2026-09-10",
            datetime(2026, 9, 11, 23, tzinfo=UTC),
            "test",
            tmp_path,
        )


def test_recovery_cannot_skip_sessions_or_cross_unreconciled_split(tmp_path: Path) -> None:
    initial = process(tmp_path, "2026-09-10", snapshot("2026-09-10"))
    data = snapshot("2026-09-14")
    with pytest.raises(ValueError, match="omitida"):
        process(tmp_path, "2026-09-14", data, initial)
    data["bars"]["SPY"]["2026-09-14"]["split"] = "2"
    data["data_hash"] = digest({k: v for k, v in data.items() if k != "data_hash"})
    with pytest.raises(ValueError, match="split"):
        process(tmp_path, "2026-09-11", data, initial)


def test_historical_model_run_tampering_and_missing_snapshot_fail_verification(
    tmp_path: Path,
) -> None:
    campaign = config() | {"models": ["equal_weight"]}
    initial = process(tmp_path, "2026-09-10", snapshot("2026-09-10"), campaign=campaign)
    verify_artifacts(tmp_path)
    decision = initial["decisions"][0]
    path = tmp_path / "model-runs" / f"{decision['model_run_id']}.json"
    document = json.loads(path.read_text())
    document["payload"]["code_version"] = "changed"
    write_json(path, document)
    with pytest.raises(ValueError, match="ModelRun histórico corrompido"):
        verify_artifacts(tmp_path)


def test_immutable_store_publishes_atomically_and_preserves_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "immutable.json"
    write_json(path, {"value": 1}, immutable=True)
    write_json(path, {"value": 1}, immutable=True)
    with pytest.raises(ValueError, match="append-only"):
        write_json(path, {"value": 2}, immutable=True)
    assert json.loads(path.read_text()) == {"value": 1}

    def fail_publish(*args: Any) -> None:
        raise OSError("simulated crash before publication")

    monkeypatch.setattr("marko.experiment.store.os.link", fail_publish)
    with pytest.raises(OSError, match="simulated crash"):
        write_json(tmp_path / "unpublished.json", {"value": 3}, immutable=True)
    assert not (tmp_path / "unpublished.json").exists()
    assert list(tmp_path.glob(".pending-*")) == []


def test_training_rejects_missing_trading_session_and_record_hash_detects_mutation(
    tmp_path: Path,
) -> None:
    data = snapshot("2026-09-11")
    del data["bars"]["SPY"]["2026-09-10"]
    with pytest.raises(ValueError, match="sessões ausentes"):
        training_returns(data, ["SPY", "IEF"], 2)
    original = process(tmp_path, "2026-09-10", snapshot("2026-09-10"))
    changed = copy.deepcopy(original)
    changed["portfolios"]["cash"]["cash"] = "20000"
    write_json(tmp_path / "records" / "2026-09-10.json", changed)
    with pytest.raises(ValueError, match="cadeia histórica"):
        read_records(tmp_path)
