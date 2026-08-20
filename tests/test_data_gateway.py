from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from marko.data_gateway import (
    AnbimaProvider,
    BcbSgsProvider,
    BusinessCalendar,
    JsonTransport,
    ObservationStore,
    SeriesQuery,
    SidraProvider,
    TreasuryDirectProvider,
)

NOW = datetime(2026, 8, 20, 15, tzinfo=UTC)


class FakeTransport(JsonTransport):
    def __init__(self, payload: list[dict[str, Any]] | dict[str, Any]) -> None:
        self.payload = payload
        self.url = ""

    def get_json(self, url: str, headers=None):  # type: ignore[no-untyped-def]
        self.url = url
        return self.payload


def test_bcb_provider_normalizes_value_and_four_times() -> None:
    transport = FakeTransport([{"data": "19/08/2026", "valor": "13,90"}])
    observations = BcbSgsProvider(transport).fetch(
        SeriesQuery("1178", date(2026, 8, 19), date(2026, 8, 19), (("unit", "% a.a."),)),
        NOW,
    )
    assert observations[0].value.as_tuple().exponent == -2
    assert observations[0].value == Decimal("13.90")
    assert observations[0].times.available_at == NOW
    assert "dataInicial=19%2F08%2F2026" in transport.url


def test_sidra_provider_discards_metadata_row_and_preserves_dimensions() -> None:
    payload = [
        {"MN": "Número-índice", "V": "Valor"},
        {
            "V": "7657.73",
            "D1C": "1",
            "D1N": "Brasil",
            "D2C": "2266",
            "D2N": "IPCA",
            "D3C": "202607",
            "D3N": "julho 2026",
            "MN": "Número-índice",
        },
    ]
    observations = SidraProvider(FakeTransport(payload)).fetch(
        SeriesQuery("IPCA", parameters=(("table", "1737"), ("variable", "2266"))), NOW
    )
    assert len(observations) == 1
    assert observations[0].times.effective_at == datetime(2026, 7, 31, tzinfo=UTC)
    assert observations[0].unit == "Número-índice"
    assert ("D1N", "Brasil") in observations[0].dimensions


def test_sidra_latest_preserves_multiple_dimensions_in_the_same_period() -> None:
    payload = [
        {"MN": "Número-índice", "V": "Valor"},
        {"V": "100", "D1C": "1", "D1N": "Brasil", "D3C": "202607"},
        {"V": "110", "D1C": "35", "D1N": "São Paulo", "D3C": "202607"},
    ]
    observations = SidraProvider(FakeTransport(payload)).fetch(
        SeriesQuery("IPCA", parameters=(("table", "1737"), ("variable", "2266"))), NOW
    )
    store = ObservationStore()
    store.append(observations)
    latest = store.latest_as_known_at("IPCA", NOW)
    assert len(latest) == 2
    assert {dict(item.dimensions)["D1C"] for item in latest} == {"1", "35"}
    vintage = store.vintage(observations[0].vintage_id, NOW)
    assert len(vintage.source_hash) == 64
    assert vintage.source_hash not in {item.observation_id for item in observations}


def test_store_is_idempotent_and_point_in_time() -> None:
    observation = BcbSgsProvider(FakeTransport([{"data": "19/08/2026", "valor": "13.90"}])).fetch(
        SeriesQuery("1178"), NOW
    )[0]
    store = ObservationStore()
    store.append((observation,))
    store.append((observation,))
    assert store.as_known_at("1178", datetime(2026, 8, 20, 14, tzinfo=UTC)) == ()
    assert store.as_known_at("1178", NOW) == (observation,)
    assert store.vintage(observation.vintage_id, NOW).observation_ids == (
        observation.observation_id,
    )


def test_business_calendar_skips_weekend_and_holiday() -> None:
    calendar = BusinessCalendar("B3", frozenset({date(2026, 8, 21)}))
    assert not calendar.is_business_day(date(2026, 8, 22))
    assert calendar.previous_business_day(date(2026, 8, 23)) == date(2026, 8, 20)


def test_treasury_adapter_handles_nested_records_without_fixed_endpoint() -> None:
    payload = {
        "response": {
            "items": [{"name": "Tesouro Selic", "maturity": "2029-03-01", "buy_rate": "0.12"}]
        }
    }
    observations = TreasuryDirectProvider(
        "https://example.invalid/tesouro", FakeTransport(payload)
    ).fetch(SeriesQuery("buy_rate", parameters=(("unit", "ratio/year"),)), NOW)
    assert observations[0].value == Decimal("0.12")
    assert ("instrument", "Tesouro Selic") in observations[0].dimensions


def test_authenticated_provider_normalizes_iso_timestamp() -> None:
    provider = AnbimaProvider(
        "https://example.invalid/anbima",
        "token",
        "value",
        "date",
        FakeTransport([{"value": "10.25", "date": "2026-08-19T12:00:00-03:00"}]),
    )
    observation = provider.fetch(SeriesQuery("IMA-B"), NOW)[0]
    assert observation.value == Decimal("10.25")
    assert observation.times.effective_at == datetime(2026, 8, 19, 15, tzinfo=UTC)
