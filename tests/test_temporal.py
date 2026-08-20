from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from marko.temporal import DataVintage, Observation, TimeCoordinates

T0 = datetime(2026, 8, 20, 10, tzinfo=UTC)


def test_four_times_and_observation_are_point_in_time_explicit() -> None:
    times = TimeCoordinates(
        T0, T0 + timedelta(minutes=1), T0 + timedelta(minutes=2), T0 + timedelta(minutes=3)
    )
    observation = Observation(
        "obs-1", "BCB/SELIC", Decimal("0.14"), "ratio/year", "BCB", times, "v1"
    )
    assert observation.value == Decimal("0.14")


def test_time_travel_is_rejected() -> None:
    with pytest.raises(ValueError):
        TimeCoordinates(
            T0, T0 + timedelta(hours=2), T0 + timedelta(hours=1), T0 + timedelta(hours=3)
        )


def test_vintage_rejects_duplicate_observations() -> None:
    with pytest.raises(ValueError):
        DataVintage("v1", T0, "sha256:abc", ("obs", "obs"))
