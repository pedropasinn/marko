from __future__ import annotations

import csv
import hashlib
import json
from calendar import monthrange
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from io import StringIO
from typing import Any, ClassVar, Protocol
from urllib.error import URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from marko.temporal import DataVintage, Observation, TimeCoordinates


@dataclass(frozen=True, slots=True)
class SeriesQuery:
    series_id: str
    start: date | None = None
    end: date | None = None
    parameters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not self.series_id.strip():
            raise ValueError("series_id é obrigatório")
        if self.start is not None and self.end is not None and self.start > self.end:
            raise ValueError("start não pode suceder end")
        keys = [key for key, _ in self.parameters]
        if len(keys) != len(set(keys)):
            raise ValueError("parâmetros duplicados")
        object.__setattr__(self, "parameters", tuple(sorted(self.parameters)))

    def parameter(self, key: str, default: str | None = None) -> str | None:
        return dict(self.parameters).get(key, default)


class JsonTransport(Protocol):
    def get_json(
        self, url: str, headers: Mapping[str, str] | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]: ...


class TextTransport(Protocol):
    def get_text(self, url: str, headers: Mapping[str, str] | None = None) -> str: ...


class UrlLibJsonTransport:
    def __init__(self, timeout: int = 15, attempts: int = 3) -> None:
        if timeout <= 0 or attempts <= 0:
            raise ValueError("timeout e attempts precisam ser positivos")
        self._timeout = timeout
        self._attempts = attempts

    def get_json(
        self, url: str, headers: Mapping[str, str] | None = None
    ) -> list[dict[str, Any]] | dict[str, Any]:
        request_headers = {"User-Agent": "Marko/0.3.0"}
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers)
        last_error: TimeoutError | URLError | None = None
        for _ in range(self._attempts):
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    payload: object = json.load(response)
                if not isinstance(payload, (list, dict)):
                    raise ValueError("o provider não retornou um documento JSON")
                return payload
            except (TimeoutError, URLError) as error:
                last_error = error
        raise RuntimeError(
            f"provider indisponível após {self._attempts} tentativas"
        ) from last_error


class UrlLibTextTransport:
    def __init__(self, timeout: int = 30, attempts: int = 3) -> None:
        if timeout <= 0 or attempts <= 0:
            raise ValueError("timeout e attempts precisam ser positivos")
        self._timeout = timeout
        self._attempts = attempts

    def get_text(
        self, url: str, headers: Mapping[str, str] | None = None
    ) -> str:
        request_headers = {"User-Agent": "Marko/0.4.0"}
        request_headers.update(headers or {})
        request = Request(url, headers=request_headers)
        last_error: TimeoutError | URLError | None = None
        for _ in range(self._attempts):
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    return str(response.read().decode("utf-8-sig"))
            except (TimeoutError, URLError) as error:
                last_error = error
        raise RuntimeError(
            f"provider indisponível após {self._attempts} tentativas"
        ) from last_error


class MarketDataProvider(Protocol):
    provider_id: str

    def fetch(self, query: SeriesQuery, retrieved_at: datetime) -> tuple[Observation, ...]: ...


class BcbSgsProvider:
    provider_id = "BCB/SGS"
    base_url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados"

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self._transport = transport or UrlLibJsonTransport()

    def fetch(self, query: SeriesQuery, retrieved_at: datetime) -> tuple[Observation, ...]:
        if retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at precisa de timezone")
        parameters = {"formato": "json"}
        if query.start is not None:
            parameters["dataInicial"] = query.start.strftime("%d/%m/%Y")
        if query.end is not None:
            parameters["dataFinal"] = query.end.strftime("%d/%m/%Y")
        url = self.base_url.format(code=query.series_id) + "?" + urlencode(parameters)
        payload = self._transport.get_json(url)
        if not isinstance(payload, list):
            raise ValueError("resposta SGS inválida")
        vintage_id = _vintage_id(self.provider_id, query, retrieved_at)
        observations = []
        for row in payload:
            effective = datetime.strptime(str(row["data"]), "%d/%m/%Y").replace(tzinfo=UTC)
            observations.append(
                _observation(
                    self.provider_id,
                    query.series_id,
                    str(row["valor"]).replace(",", "."),
                    query.parameter("unit", "provider-defined") or "provider-defined",
                    effective,
                    retrieved_at,
                    vintage_id,
                    (("provider_url", url),),
                    row,
                )
            )
        return tuple(observations)


class SidraProvider:
    provider_id = "IBGE/SIDRA"
    base_url = "https://apisidra.ibge.gov.br/values"

    def __init__(self, transport: JsonTransport | None = None) -> None:
        self._transport = transport or UrlLibJsonTransport()

    def fetch(self, query: SeriesQuery, retrieved_at: datetime) -> tuple[Observation, ...]:
        table = _required(query, "table")
        variable = _required(query, "variable")
        territory = query.parameter("territory", "n1/all") or "n1/all"
        period = query.parameter("period", "all") or "all"
        url = (
            f"{self.base_url}/t/{quote(table)}/{quote(territory, safe='/')}/v/"
            f"{quote(variable)}/p/{quote(period)}?formato=json"
        )
        payload = self._transport.get_json(url)
        if not isinstance(payload, list) or not payload:
            raise ValueError("resposta SIDRA inválida")
        header, *rows = payload
        default_unit = str(header.get("MN", "provider-defined"))
        vintage_id = _vintage_id(self.provider_id, query, retrieved_at)
        observations = []
        for row in rows:
            raw_value = str(row.get("V", "")).strip()
            if raw_value in {"", "-", "...", ".."}:
                continue
            period_code = str(row.get("D3C") or row.get("D2C") or row.get("D4C"))
            effective = _sidra_period(period_code)
            unit = str(row.get("MN", default_unit))
            dimensions = tuple(
                (key, str(value))
                for key, value in sorted(row.items())
                if key.endswith("C") or key.endswith("N")
            )
            observations.append(
                _observation(
                    self.provider_id,
                    query.series_id,
                    raw_value.replace(",", "."),
                    unit,
                    effective,
                    retrieved_at,
                    vintage_id,
                    dimensions,
                    row,
                )
            )
        return tuple(observations)


class TreasuryDirectProvider:
    provider_id = "TESOURO_TRANSPARENTE/TESOURO_DIRETO"
    package_url = (
        "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show"
        "?id=taxas-dos-titulos-ofertados-pelo-tesouro-direto"
    )
    _fields: ClassVar[dict[str, tuple[str, str]]] = {
        "buy_rate": ("Taxa Compra Manha", "% a.a."),
        "sell_rate": ("Taxa Venda Manha", "% a.a."),
        "buy_price": ("PU Compra Manha", "BRL"),
        "sell_price": ("PU Venda Manha", "BRL"),
        "base_price": ("PU Base Manha", "BRL"),
    }

    def __init__(
        self,
        endpoint: str | None = None,
        transport: JsonTransport | None = None,
        text_transport: TextTransport | None = None,
    ) -> None:
        if endpoint is not None and not endpoint.startswith("https://"):
            raise ValueError("endpoint do Tesouro precisa usar HTTPS")
        self._endpoint = endpoint
        self._transport = transport or UrlLibJsonTransport()
        self._text_transport = text_transport or UrlLibTextTransport()

    def fetch(self, query: SeriesQuery, retrieved_at: datetime) -> tuple[Observation, ...]:
        if retrieved_at.tzinfo is None:
            raise ValueError("retrieved_at precisa de timezone")
        if self._endpoint is not None:
            return self._fetch_injected_json(query, retrieved_at)

        metadata = self._transport.get_json(self.package_url)
        resource_url, modified_at = _treasury_csv_resource(metadata)
        raw_csv = self._text_transport.get_text(resource_url)
        csv_hash = hashlib.sha256(raw_csv.encode("utf-8")).hexdigest()
        field, default_unit = self._fields.get(
            query.series_id,
            (query.series_id, query.parameter("unit", "provider-defined") or "provider-defined"),
        )
        unit = query.parameter("unit", default_unit) or default_unit
        vintage_id = _vintage_id(self.provider_id, query, retrieved_at)
        observations = []
        for row in csv.DictReader(StringIO(raw_csv), delimiter=";"):
            base_date = datetime.strptime(row["Data Base"], "%d/%m/%Y").date()
            if query.start is not None and base_date < query.start:
                continue
            if query.end is not None and base_date > query.end:
                continue
            raw_value = str(row.get(field, "")).strip()
            if not raw_value:
                continue
            effective = datetime.combine(base_date, datetime.min.time(), tzinfo=UTC)
            maturity = datetime.strptime(row["Data Vencimento"], "%d/%m/%Y").date()
            dimensions = (
                ("instrument", row["Tipo Titulo"].strip()),
                ("maturity", maturity.isoformat()),
                ("provider_url", resource_url),
            )
            observations.append(
                _observation(
                    self.provider_id,
                    query.series_id,
                    raw_value.replace(".", "").replace(",", "."),
                    unit,
                    effective,
                    retrieved_at,
                    vintage_id,
                    dimensions,
                    {
                        "row": row,
                        "csv_sha256": csv_hash,
                        "resource_last_modified": modified_at,
                    },
                )
            )
        return tuple(observations)

    def _fetch_injected_json(
        self, query: SeriesQuery, retrieved_at: datetime
    ) -> tuple[Observation, ...]:
        assert self._endpoint is not None
        payload = self._transport.get_json(self._endpoint)
        records = _find_records(payload)
        vintage_id = _vintage_id(self.provider_id, query, retrieved_at)
        observations = []
        for record in records:
            name = str(record.get("name") or record.get("TrsrBdNm") or record.get("bond_name"))
            maturity = str(record.get("maturity") or record.get("MtrtyDt") or "")
            value = record.get(query.series_id)
            if value is None:
                continue
            observations.append(
                _observation(
                    self.provider_id,
                    query.series_id,
                    str(value),
                    query.parameter("unit", "provider-defined") or "provider-defined",
                    retrieved_at,
                    retrieved_at,
                    vintage_id,
                    (("instrument", name), ("maturity", maturity)),
                    record,
                )
            )
        return tuple(observations)


class AuthenticatedJsonProvider:
    def __init__(
        self,
        provider_id: str,
        endpoint: str,
        token: str,
        value_field: str,
        date_field: str,
        transport: JsonTransport | None = None,
    ) -> None:
        if not endpoint.startswith("https://"):
            raise ValueError("endpoint precisa usar HTTPS")
        self.provider_id = provider_id
        self._endpoint = endpoint
        self._token = token
        self._value_field = value_field
        self._date_field = date_field
        self._transport = transport or UrlLibJsonTransport()

    def fetch(self, query: SeriesQuery, retrieved_at: datetime) -> tuple[Observation, ...]:
        payload = self._transport.get_json(
            self._endpoint,
            headers={"Authorization": f"Bearer {self._token}"},
        )
        records = _find_records(payload)
        vintage_id = _vintage_id(self.provider_id, query, retrieved_at)
        return tuple(
            _observation(
                self.provider_id,
                query.series_id,
                str(record[self._value_field]),
                query.parameter("unit", "provider-defined") or "provider-defined",
                _parse_datetime(str(record[self._date_field])),
                retrieved_at,
                vintage_id,
                (),
                record,
            )
            for record in records
        )


class AnbimaProvider(AuthenticatedJsonProvider):
    def __init__(
        self,
        endpoint: str,
        token: str,
        value_field: str,
        date_field: str,
        transport: JsonTransport | None = None,
    ) -> None:
        super().__init__("ANBIMA", endpoint, token, value_field, date_field, transport)


class B3Provider(AuthenticatedJsonProvider):
    def __init__(
        self,
        endpoint: str,
        token: str,
        value_field: str,
        date_field: str,
        transport: JsonTransport | None = None,
    ) -> None:
        super().__init__("B3", endpoint, token, value_field, date_field, transport)


class ObservationStore:
    def __init__(self) -> None:
        self._observations: dict[str, Observation] = {}

    def append(self, observations: tuple[Observation, ...]) -> None:
        for observation in observations:
            previous = self._observations.get(observation.observation_id)
            if previous is not None and previous != observation:
                raise ValueError(f"observation_id conflitante: {observation.observation_id}")
            self._observations[observation.observation_id] = observation

    def as_known_at(self, series_id: str, known_at: datetime) -> tuple[Observation, ...]:
        return tuple(
            sorted(
                (
                    observation
                    for observation in self._observations.values()
                    if observation.series_id == series_id
                    and observation.times.available_at <= known_at
                ),
                key=lambda observation: (
                    observation.times.effective_at,
                    observation.times.available_at,
                ),
            )
        )

    def vintage(self, vintage_id: str, created_at: datetime) -> DataVintage:
        identifiers = tuple(
            sorted(
                observation.observation_id
                for observation in self._observations.values()
                if observation.vintage_id == vintage_id
            )
        )
        raw_hashes = sorted(
            observation.raw_payload_hash
            for observation in self._observations.values()
            if observation.vintage_id == vintage_id
        )
        source_hash = hashlib.sha256("\n".join(raw_hashes).encode()).hexdigest()
        return DataVintage(vintage_id, created_at, source_hash, identifiers)

    def latest_as_known_at(self, series_id: str, known_at: datetime) -> tuple[Observation, ...]:
        latest: dict[tuple[datetime, tuple[tuple[str, str], ...]], Observation] = {}
        for observation in self.as_known_at(series_id, known_at):
            identity = (observation.times.effective_at, observation.dimensions)
            previous = latest.get(identity)
            if previous is None or observation.times.available_at > previous.times.available_at:
                latest[identity] = observation
        return tuple(latest[key] for key in sorted(latest))


@dataclass(frozen=True, slots=True)
class BusinessCalendar:
    calendar_id: str
    holidays: frozenset[date]

    def is_business_day(self, value: date) -> bool:
        return value.weekday() < 5 and value not in self.holidays

    def previous_business_day(self, value: date) -> date:
        candidate = value
        while not self.is_business_day(candidate):
            candidate = date.fromordinal(candidate.toordinal() - 1)
        return candidate


def _observation(
    source: str,
    series_id: str,
    value: str,
    unit: str,
    effective_at: datetime,
    retrieved_at: datetime,
    vintage_id: str,
    dimensions: tuple[tuple[str, str], ...],
    raw_payload: object,
) -> Observation:
    identity = f"{source}|{series_id}|{effective_at.isoformat()}|{value}|{dimensions}|{vintage_id}"
    observation_id = hashlib.sha256(identity.encode()).hexdigest()
    raw_payload_hash = hashlib.sha256(
        json.dumps(raw_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()
    return Observation(
        observation_id,
        series_id,
        Decimal(value),
        unit,
        source,
        TimeCoordinates(effective_at, effective_at, retrieved_at, retrieved_at),
        vintage_id,
        raw_payload_hash,
        dimensions,
        ("availability_conservative",),
    )


def _vintage_id(provider_id: str, query: SeriesQuery, retrieved_at: datetime) -> str:
    payload = f"{provider_id}|{query}|{retrieved_at.isoformat()}"
    return hashlib.sha256(payload.encode()).hexdigest()[:24]


def _required(query: SeriesQuery, key: str) -> str:
    value = query.parameter(key)
    if not value:
        raise ValueError(f"parâmetro obrigatório: {key}")
    return value


def _sidra_period(code: str) -> datetime:
    if len(code) == 6 and code.isdigit():
        year, month = int(code[:4]), int(code[4:])
        return datetime(year, month, monthrange(year, month)[1], tzinfo=UTC)
    if len(code) == 4 and code.isdigit():
        return datetime(int(code), 12, 31, tzinfo=UTC)
    raise ValueError(f"período SIDRA não suportado: {code}")


def _find_records(payload: list[dict[str, Any]] | dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    for key in ("data", "results", "items", "response", "TrsrBdTradgList"):
        value = payload.get(key)
        if isinstance(value, list):
            return [record for record in value if isinstance(record, dict)]
        if isinstance(value, dict):
            nested = _find_records(value)
            if nested:
                return nested
    return []


def _treasury_csv_resource(
    payload: list[dict[str, Any]] | dict[str, Any],
) -> tuple[str, str]:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise ValueError("catálogo CKAN do Tesouro retornou resposta inválida")
    result = payload.get("result")
    if not isinstance(result, dict):
        raise ValueError("catálogo CKAN do Tesouro não contém result")
    resources = result.get("resources")
    if not isinstance(resources, list):
        raise ValueError("catálogo CKAN do Tesouro não contém resources")
    candidates = [
        resource
        for resource in resources
        if isinstance(resource, dict)
        and str(resource.get("format", "")).upper() == "CSV"
        and str(resource.get("url", "")).startswith("https://")
    ]
    if not candidates:
        raise ValueError("catálogo CKAN do Tesouro não contém recurso CSV HTTPS")
    resource = max(
        candidates,
        key=lambda item: str(item.get("last_modified") or item.get("created") or ""),
    )
    return str(resource["url"]), str(
        resource.get("last_modified") or result.get("metadata_modified") or "unknown"
    )


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
