from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from test_persistence import samples

from marko.analytics import PerformancePoint
from marko.decision import ValidatedModelRunRef
from marko.money import Money
from marko.shadow import ShadowReconciliation, ShadowRunRequest, reconcile_shadow_packet
from marko.shadow_operation import (
    BenchmarkKind,
    BenchmarkSeries,
    ReturnPoint,
    ShadowCycleJournal,
    ShadowCycleRecord,
    ShadowCycleRegistry,
    ShadowCycleState,
    ShadowIdentityConflictError,
    build_shadow_benchmark_report,
)
from marko.snapshots import PortfolioSnapshot
from marko.temporal import DataVintage

T0 = datetime(2026, 8, 20, 12, tzinfo=UTC)


def test_shadow_cycle_journal_is_append_only_and_enforces_transitions() -> None:
    journal = ShadowCycleJournal().record(
        cycle_id="cycle-1", state=ShadowCycleState.SCHEDULED, occurred_at=T0
    )
    draft = journal.record(
        cycle_id="cycle-1",
        state=ShadowCycleState.DRAFT,
        occurred_at=T0 + timedelta(minutes=1),
        details=(("packet_id", "packet-1"),),
    )
    reviewed = draft.record(
        cycle_id="cycle-1",
        state=ShadowCycleState.REVIEWED,
        occurred_at=T0 + timedelta(minutes=2),
        details=(("review", "completed"),),
    )

    assert journal.state is ShadowCycleState.SCHEDULED
    assert reviewed.state is ShadowCycleState.REVIEWED
    assert reviewed.events[1].previous_hash == reviewed.events[0].content_hash
    with pytest.raises(ValueError, match="reviewed -> draft"):
        reviewed.record(
            cycle_id="cycle-1",
            state=ShadowCycleState.DRAFT,
            occurred_at=T0 + timedelta(minutes=3),
        )


def test_event_and_record_reexecution_are_idempotent_and_conflicts_are_explicit() -> None:
    journal = ShadowCycleJournal().record(
        cycle_id="cycle-1", state=ShadowCycleState.SCHEDULED, occurred_at=T0
    )
    same_event = replace(journal.events[0])
    assert journal.append(same_event) is journal
    conflicting_event = replace(
        journal.events[0], details=(("reason", "changed"),), content_hash=""
    )
    with pytest.raises(ShadowIdentityConflictError):
        journal.append(conflicting_event)

    record = _cycle_record()
    registry = ShadowCycleRegistry().append(record)
    assert registry.append(replace(record)) is registry
    conflicting_record = replace(
        record,
        snapshot=replace(record.snapshot, last_activity_id="different"),
        content_hash="",
    )
    with pytest.raises(ShadowIdentityConflictError):
        registry.append(conflicting_record)


def test_cycle_record_links_pit_inputs_without_turning_review_into_execution() -> None:
    record = _cycle_record()

    assert record.journal.state is ShadowCycleState.RECONCILED
    assert record.reconciliation.ready
    assert record.decision_packet.packet_id == record.reconciliation.packet_id
    assert {run.run_id for run in record.model_runs} == set(record.decision_packet.model_run_ids)
    assert not hasattr(record, "approved")
    assert not hasattr(record, "executed")

    future_vintage = replace(
        record.vintages[0], created_at=record.request.knowledge_cutoff + timedelta(seconds=1)
    )
    with pytest.raises(ValueError, match="posteriores ao knowledge_cutoff"):
        replace(record, vintages=(future_vintage,), content_hash="")


def test_synthetic_shadow_report_chains_twr_drawdown_and_drift() -> None:
    instants = tuple(T0 + timedelta(days=day) for day in range(3))
    observed = BenchmarkSeries(
        BenchmarkKind.OBSERVED,
        performance_points=(
            PerformancePoint(instants[0], Money.of("100", "BRL"), Money.zero("BRL")),
            PerformancePoint(instants[1], Money.of("120", "BRL"), Money.of("10", "BRL")),
            PerformancePoint(instants[2], Money.of("99", "BRL"), Money.zero("BRL")),
        ),
        expected_at=instants,
    )
    cdi = BenchmarkSeries(
        BenchmarkKind.CDI,
        returns=(
            ReturnPoint(instants[0], Decimal("0.01")),
            ReturnPoint(instants[1], Decimal("0.01")),
            ReturnPoint(instants[2], Decimal("0.01")),
        ),
        expected_at=instants,
    )
    equal_weight = BenchmarkSeries(
        BenchmarkKind.EQUAL_WEIGHT,
        returns=(
            ReturnPoint(instants[0], Decimal("0.02")),
            ReturnPoint(instants[1], Decimal("-0.10")),
            ReturnPoint(instants[2], Decimal("0.05")),
        ),
        expected_at=instants,
    )

    report = build_shadow_benchmark_report(observed=observed, cdi=cdi, equal_weight=equal_weight)

    assert report.complete
    assert report.observed.twr == Decimal("-0.0925")
    assert report.observed.maximum_drawdown == Decimal("-0.175")
    assert report.cdi.twr == Decimal("0.030301")
    assert report.cdi.return_drift_from_observed == Decimal("0.122801")
    assert report.equal_weight.maximum_drawdown == Decimal("-0.10")
    assert report == build_shadow_benchmark_report(
        observed=observed, cdi=cdi, equal_weight=equal_weight
    )


def test_incomplete_benchmark_is_visible_and_does_not_invent_data() -> None:
    point = ReturnPoint(T0, Decimal("0.001"))
    report = build_shadow_benchmark_report(
        observed=BenchmarkSeries(
            BenchmarkKind.OBSERVED,
            returns=(point,),
            expected_at=(T0, T0 + timedelta(days=1)),
        ),
        cdi=None,
        equal_weight=BenchmarkSeries(
            BenchmarkKind.EQUAL_WEIGHT,
            returns=(point,),
            failures=("fonte 1/N indisponível no segundo ponto",),
        ),
    )

    assert not report.complete
    assert report.cdi.twr is None
    assert "cdi: série não fornecida" in report.failures
    assert any("pontos esperados ausentes" in failure for failure in report.failures)
    assert any("fonte 1/N indisponível" in failure for failure in report.failures)


def _cycle_record() -> ShadowCycleRecord:
    _, observation, run, packet = samples()
    request = ShadowRunRequest.create("monthly", packet.created_at - timedelta(minutes=1))
    packet = replace(
        packet,
        model_runs=tuple(
            ValidatedModelRunRef.from_model_run(run, dataset_available_at=run.created_at)
            for _reference in packet.model_runs
        ),
        shadow_request_id=request.request_id,
        knowledge_cutoff=request.knowledge_cutoff,
    )
    snapshot = PortfolioSnapshot(
        "snapshot-1",
        request.knowledge_cutoff,
        None,
        (),
        (),
    )
    vintage = DataVintage(
        observation.vintage_id,
        observation.times.available_at,
        observation.raw_payload_hash,
        (observation.observation_id,),
    )
    reconciliation = reconcile_shadow_packet(
        packet,
        request=request,
        model_runs=(run,),
        observations=(observation,),
        checked_at=packet.created_at + timedelta(minutes=1),
    )
    journal = ShadowCycleJournal()
    for index, state in enumerate(
        (
            ShadowCycleState.SCHEDULED,
            ShadowCycleState.DRAFT,
            ShadowCycleState.REVIEWED,
            ShadowCycleState.RECONCILED,
        )
    ):
        journal = journal.record(
            cycle_id=request.request_id,
            state=state,
            occurred_at=request.scheduled_for + timedelta(minutes=index),
        )
    return ShadowCycleRecord(
        request,
        snapshot,
        (vintage,),
        (run,),
        packet,
        reconciliation,
        journal,
    )


def test_reconciled_state_rejects_incomplete_reconciliation() -> None:
    record = _cycle_record()
    incomplete = ShadowReconciliation(
        packet_id=record.decision_packet.packet_id,
        checked_at=record.reconciliation.checked_at,
        missing_model_run_ids=(),
        mismatched_model_run_ids=(),
        future_model_run_ids=(),
        missing_evidence_ids=("missing-observation",),
        future_evidence_ids=(),
        request_id=record.request.request_id,
        knowledge_cutoff=record.request.knowledge_cutoff,
    )
    with pytest.raises(ValueError, match="não pode ser marcado"):
        replace(record, reconciliation=incomplete, content_hash="")

    blocked_journal = ShadowCycleJournal().record(
        cycle_id=record.request_id,
        state=ShadowCycleState.SCHEDULED,
        occurred_at=record.request.scheduled_for,
    )
    blocked_journal = blocked_journal.record(
        cycle_id=record.request_id,
        state=ShadowCycleState.BLOCKED,
        occurred_at=record.request.scheduled_for + timedelta(minutes=1),
    )
    blocked = replace(
        record,
        reconciliation=incomplete,
        journal=blocked_journal,
        content_hash="",
    )
    assert blocked.reconciliation == incomplete
    assert blocked.knowledge_cutoff == record.request.knowledge_cutoff

    missing_run = reconcile_shadow_packet(
        record.decision_packet,
        request=record.request,
        model_runs=(),
        observations=(),
        checked_at=record.reconciliation.checked_at,
    )
    blocked_missing_run = replace(
        record,
        model_runs=(),
        reconciliation=missing_run,
        journal=blocked_journal,
        content_hash="",
    )
    assert blocked_missing_run.reconciliation.missing_model_run_ids == (
        record.model_runs[0].run_id,
    )
