from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_persistence import samples

from marko.__main__ import main
from marko.shadow import MonthlyShadowSchedule, reconcile_shadow_packet


def test_monthly_schedule_is_deterministic_and_clamps_month_end() -> None:
    schedule = MonthlyShadowSchedule("monthly", 31, 9, 30, "America/Sao_Paulo")
    requests = schedule.due_between(
        datetime(2026, 1, 31, 13, tzinfo=UTC),
        datetime(2026, 3, 31, 13, tzinfo=UTC),
    )
    assert [request.scheduled_for for request in requests] == [
        datetime(2026, 2, 28, 12, 30, tzinfo=UTC),
        datetime(2026, 3, 31, 12, 30, tzinfo=UTC),
    ]
    assert requests == schedule.due_between(
        datetime(2026, 1, 31, 13, tzinfo=UTC),
        datetime(2026, 3, 31, 13, tzinfo=UTC),
    )


def test_shadow_reconciliation_requires_pit_evidence_and_exact_model_run() -> None:
    _, observation, run, packet = samples()
    ready = reconcile_shadow_packet(
        packet,
        model_runs=(run,),
        observations=(observation,),
        checked_at=packet.created_at + timedelta(minutes=5),
    )
    assert ready.ready

    future_observation = replace(
        observation,
        times=replace(
            observation.times,
            available_at=packet.created_at + timedelta(minutes=1),
            ingested_at=packet.created_at + timedelta(minutes=2),
        ),
    )
    incomplete = reconcile_shadow_packet(
        packet,
        model_runs=(),
        observations=(future_observation,),
        checked_at=packet.created_at + timedelta(minutes=5),
    )
    assert not incomplete.ready
    assert incomplete.missing_model_run_ids == (run.run_id,)
    assert incomplete.future_evidence_ids == (observation.observation_id,)


def test_schedule_and_reconciliation_reject_invalid_time_or_duplicate_inputs() -> None:
    schedule = MonthlyShadowSchedule("monthly", 20, 9, 0, "UTC")
    with pytest.raises(ValueError, match="until"):
        schedule.due_between(
            datetime(2026, 8, 21, tzinfo=UTC), datetime(2026, 8, 20, tzinfo=UTC)
        )
    _, observation, run, packet = samples()
    with pytest.raises(ValueError, match="run_id duplicado"):
        reconcile_shadow_packet(
            packet,
            model_runs=(run, run),
            observations=(observation,),
            checked_at=packet.created_at,
        )


def test_cli_lists_due_shadow_cycles_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert (
        main(
            [
                "shadow-due",
                "--day",
                "20",
                "--after",
                "2026-07-20T13:00:00+00:00",
                "--until",
                "2026-08-20T13:00:00+00:00",
            ]
        )
        == 0
    )
    payload = capsys.readouterr().out
    assert '"schedule_id": "monthly"' in payload
    assert '"scheduled_for": "2026-08-20T12:00:00+00:00"' in payload
