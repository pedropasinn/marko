from datetime import UTC, datetime
from decimal import Decimal

import pytest

from marko.decision import (
    CashFlowRebalancer,
    DecisionAlternative,
    DecisionPacket,
    Holding,
    TargetAllocation,
)
from marko.money import Money


def holdings() -> tuple[Holding, ...]:
    return (
        Holding("BR", Money.of("8500", "BRL"), Money.of("50", "BRL"), True),
        Holding("GLOBAL", Money.of("10500", "BRL"), Money.of("100", "BRL"), True),
        Holding("IPCA", Money.of("7000", "BRL"), Money.of("10", "BRL")),
        Holding("CASH", Money.of("24000", "BRL"), Money.of("1", "BRL")),
    )


def targets() -> tuple[TargetAllocation, ...]:
    return (
        TargetAllocation("BR", Decimal("0.15"), Decimal("0.20")),
        TargetAllocation("GLOBAL", Decimal("0.25"), Decimal("0.30")),
        TargetAllocation("IPCA", Decimal("0.15"), Decimal("0.20")),
        TargetAllocation("CASH", Decimal("0.45"), Decimal("0.60")),
    )


def test_cash_flow_rebalancing_uses_contribution_without_sales() -> None:
    packet = CashFlowRebalancer().build_packet(
        packet_id="decision-1",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        policy_id="ips",
        policy_version=1,
        holdings=holdings(),
        targets=targets(),
        contribution=Money.of("2000", "BRL"),
    )
    no_action, rebalance = packet.alternatives
    assert no_action.alternative_id == "no_action"
    assert rebalance.alternative_id == "cash_flow_only"
    assert all(trade.side.value == "buy" for trade in rebalance.trades)
    assert sum((trade.notional.amount for trade in rebalance.trades), Decimal(0)) == Decimal(
        "2000.00"
    )
    assert rebalance.trades[0].instrument_id == "GLOBAL"


def test_decision_packet_rejects_missing_no_action() -> None:
    alternative = DecisionAlternative(
        "trade",
        (),
        (),
        Money.zero("BRL"),
        Decimal(0),
        True,
        (),
    )
    with pytest.raises(ValueError, match="NO_ACTION"):
        DecisionPacket(
            "packet",
            datetime(2026, 8, 20, tzinfo=UTC),
            "ips",
            1,
            (),
            (),
            (alternative,),
        )


def test_ips_liquidity_can_block_a_draft_without_hiding_it() -> None:
    packet = CashFlowRebalancer().build_packet(
        packet_id="decision-2",
        created_at=datetime(2026, 8, 20, tzinfo=UTC),
        policy_id="ips",
        policy_version=1,
        holdings=holdings(),
        targets=targets(),
        contribution=Money.of("2000", "BRL"),
        minimum_cash=Money.of("25000", "BRL"),
    )
    draft = packet.alternatives[1]
    assert not draft.feasible
    assert "violação de liquidez mínima" in draft.reasons
