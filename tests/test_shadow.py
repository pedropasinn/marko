from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from test_persistence import samples

from marko.__main__ import main
from marko.decision import DecisionPacket, ValidatedModelRunRef
from marko.research_registry import ModelRun
from marko.shadow import MonthlyShadowSchedule, ShadowRunRequest, reconcile_shadow_packet


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
    earlier_cutoff = ShadowRunRequest.create(
        "monthly",
        requests[0].scheduled_for,
        requests[0].knowledge_cutoff - timedelta(minutes=1),
    )
    assert earlier_cutoff.request_id != requests[0].request_id


def test_shadow_reconciliation_requires_pit_evidence_and_exact_model_run() -> None:
    _, observation, run, packet = samples()
    request, packet = _bind_to_request(packet, run)
    ready = reconcile_shadow_packet(
        packet,
        request=request,
        model_runs=(run,),
        observations=(observation,),
        checked_at=packet.created_at + timedelta(minutes=5),
    )
    assert ready.ready

    future_available_at = request.knowledge_cutoff + timedelta(seconds=30)
    assert future_available_at < packet.created_at
    future_observation = replace(
        observation,
        times=replace(
            observation.times,
            available_at=future_available_at,
            ingested_at=future_available_at + timedelta(seconds=1),
        ),
    )
    incomplete = reconcile_shadow_packet(
        packet,
        request=request,
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
        schedule.due_between(datetime(2026, 8, 21, tzinfo=UTC), datetime(2026, 8, 20, tzinfo=UTC))
    _, observation, run, packet = samples()
    request, packet = _bind_to_request(packet, run)
    with pytest.raises(ValueError, match="run_id duplicado"):
        reconcile_shadow_packet(
            packet,
            request=request,
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


def test_reconciliation_rejects_unlinked_or_different_request() -> None:
    _, observation, run, packet = samples()
    unlinked_request = ShadowRunRequest.create("test", packet.created_at)
    with pytest.raises(ValueError, match="não está ligado"):
        reconcile_shadow_packet(
            packet,
            request=unlinked_request,
            model_runs=(run,),
            observations=(observation,),
            checked_at=packet.created_at,
        )
    request, packet = _bind_to_request(packet, run)
    other = ShadowRunRequest.create("other", request.scheduled_for)
    with pytest.raises(ValueError, match="não corresponde"):
        reconcile_shadow_packet(
            packet,
            request=other,
            model_runs=(run,),
            observations=(observation,),
            checked_at=packet.created_at,
        )


def test_model_run_and_dataset_availability_use_request_cutoff_not_packet_time() -> None:
    _, observation, run, packet = samples()
    request, packet = _bind_to_request(packet, run)
    after_cutoff = request.knowledge_cutoff + timedelta(seconds=30)
    assert after_cutoff < packet.created_at
    future_run = replace(run, created_at=after_cutoff)
    future_dataset_packet = replace(
        packet,
        model_runs=tuple(
            reference.with_dataset_available_at(after_cutoff) for reference in packet.model_runs
        ),
    )

    result = reconcile_shadow_packet(
        future_dataset_packet,
        request=request,
        model_runs=(future_run,),
        observations=(observation,),
        checked_at=packet.created_at,
    )

    assert result.future_model_run_ids == (run.run_id,)
    assert result.future_dataset_run_ids == (run.run_id,)
    assert not result.ready


def _bind_to_request(
    packet: DecisionPacket, run: ModelRun
) -> tuple[ShadowRunRequest, DecisionPacket]:
    request = ShadowRunRequest.create("test", packet.created_at - timedelta(minutes=1))
    references = tuple(
        ValidatedModelRunRef.from_model_run(run, dataset_available_at=run.created_at)
        for _reference in packet.model_runs
    )
    return request, replace(
        packet,
        model_runs=references,
        shadow_request_id=request.request_id,
        knowledge_cutoff=request.knowledge_cutoff,
    )
