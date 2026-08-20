from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast

from marko.activities import Activity, ActivityKind
from marko.decision import (
    DecisionAlternative,
    DecisionPacket,
    TradeProposal,
    TradeSide,
    ValidatedModelRunRef,
)
from marko.money import Money
from marko.persistence.errors import UnsupportedSchemaError
from marko.portfolio_lab import (
    PortfolioCandidate,
    PortfolioProblem,
    ValidatedPortfolioCandidate,
)
from marko.research_registry import ModelRun, SolverRecord
from marko.temporal import Observation, TimeCoordinates

type JsonValue = bool | int | float | str | list[JsonValue] | dict[str, JsonValue] | None


@dataclass(frozen=True, slots=True)
class SerializationEnvelope:
    schema: str
    version: int
    payload: dict[str, JsonValue]

    def __post_init__(self) -> None:
        if not self.schema.strip() or self.version <= 0:
            raise ValueError("schema e version são obrigatórios")

    def canonical_json(self) -> str:
        return json.dumps(
            {"schema": self.schema, "version": self.version, "payload": self.payload},
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()

    @classmethod
    def from_json(cls, value: str) -> SerializationEnvelope:
        document = json.loads(value)
        mapping = _mapping(document, "envelope")
        _exact_keys(mapping, {"schema", "version", "payload"}, "envelope")
        payload = _mapping(mapping.get("payload"), "payload")
        return cls(
            _text(mapping.get("schema"), "schema"),
            _integer(mapping.get("version"), "version"),
            cast(dict[str, JsonValue], payload),
        )


def encode_activity(activity: Activity) -> SerializationEnvelope:
    return SerializationEnvelope(
        "marko.activity",
        1,
        {
            "activity_id": activity.activity_id,
            "kind": activity.kind.value,
            "account_id": activity.account_id,
            "effective_at": activity.effective_at.isoformat(),
            "recorded_at": activity.recorded_at.isoformat(),
            "gross_amount": _money(activity.gross_amount),
            "instrument_id": activity.instrument_id,
            "quantity": _decimal(activity.quantity),
            "fee": _money(activity.fee),
            "tax": _money(activity.tax),
            "cost_basis": _money(activity.cost_basis),
            "counter_amount": _money(activity.counter_amount),
            "related_account_id": activity.related_account_id,
            "related_activity_id": activity.related_activity_id,
            "related_instrument_id": activity.related_instrument_id,
            "ratio": _decimal(activity.ratio),
            "external_id": activity.external_id,
            "correction_of": activity.correction_of,
            "is_reversal": activity.is_reversal,
            "sequence": activity.sequence,
        },
    )


def decode_activity(envelope: SerializationEnvelope) -> Activity:
    payload = _payload(
        envelope,
        "marko.activity",
        1,
        {
            "activity_id",
            "kind",
            "account_id",
            "effective_at",
            "recorded_at",
            "gross_amount",
            "instrument_id",
            "quantity",
            "fee",
            "tax",
            "cost_basis",
            "counter_amount",
            "related_account_id",
            "related_activity_id",
            "related_instrument_id",
            "ratio",
            "external_id",
            "correction_of",
            "is_reversal",
            "sequence",
        },
    )
    return Activity(
        activity_id=_text(payload.get("activity_id"), "activity_id"),
        kind=ActivityKind(_text(payload.get("kind"), "kind")),
        account_id=_text(payload.get("account_id"), "account_id"),
        effective_at=_datetime(payload.get("effective_at"), "effective_at"),
        recorded_at=_datetime(payload.get("recorded_at"), "recorded_at"),
        gross_amount=_optional_money(payload.get("gross_amount")),
        instrument_id=_optional_text(payload.get("instrument_id")),
        quantity=_optional_decimal(payload.get("quantity")),
        fee=_optional_money(payload.get("fee")),
        tax=_optional_money(payload.get("tax")),
        cost_basis=_optional_money(payload.get("cost_basis")),
        counter_amount=_optional_money(payload.get("counter_amount")),
        related_account_id=_optional_text(payload.get("related_account_id")),
        related_activity_id=_optional_text(payload.get("related_activity_id")),
        related_instrument_id=_optional_text(payload.get("related_instrument_id")),
        ratio=_optional_decimal(payload.get("ratio")),
        external_id=_optional_text(payload.get("external_id")),
        correction_of=_optional_text(payload.get("correction_of")),
        is_reversal=_boolean(payload.get("is_reversal"), "is_reversal"),
        sequence=_integer(payload.get("sequence"), "sequence"),
    )


def encode_observation(observation: Observation) -> SerializationEnvelope:
    return SerializationEnvelope(
        "marko.observation",
        1,
        {
            "observation_id": observation.observation_id,
            "series_id": observation.series_id,
            "value": str(observation.value),
            "unit": observation.unit,
            "source": observation.source,
            "times": _times(observation.times),
            "vintage_id": observation.vintage_id,
            "raw_payload_hash": observation.raw_payload_hash,
            "dimensions": _pairs(observation.dimensions),
            "quality_flags": list(observation.quality_flags),
        },
    )


def decode_observation(envelope: SerializationEnvelope) -> Observation:
    payload = _payload(
        envelope,
        "marko.observation",
        1,
        {
            "observation_id",
            "series_id",
            "value",
            "unit",
            "source",
            "times",
            "vintage_id",
            "raw_payload_hash",
            "dimensions",
            "quality_flags",
        },
    )
    return Observation(
        _text(payload.get("observation_id"), "observation_id"),
        _text(payload.get("series_id"), "series_id"),
        _required_decimal(payload.get("value"), "value"),
        _text(payload.get("unit"), "unit"),
        _text(payload.get("source"), "source"),
        _decode_times(payload.get("times")),
        _text(payload.get("vintage_id"), "vintage_id"),
        _text(payload.get("raw_payload_hash"), "raw_payload_hash"),
        _decode_pairs(payload.get("dimensions"), "dimensions"),
        _text_tuple(payload.get("quality_flags"), "quality_flags"),
    )


def encode_model_run(run: ModelRun) -> SerializationEnvelope:
    return SerializationEnvelope(
        "marko.model_run",
        1,
        {
            "run_id": run.run_id,
            "created_at": run.created_at.isoformat(),
            "model_id": run.model_id,
            "code_version": run.code_version,
            "environment_fingerprint": run.environment_fingerprint,
            "dataset_fingerprint": run.dataset_fingerprint,
            "policy_id": run.policy_id,
            "policy_version": run.policy_version,
            "universe_id": run.universe_id,
            "universe_version": run.universe_version,
            "parameters": _pairs(run.parameters),
            "random_seed": run.random_seed,
            "solver": _solver(run.solver),
            "candidate": _candidate(run.candidate),
            "validated_candidate": (
                _validated_candidate(run.validated_candidate)
                if run.validated_candidate is not None
                else None
            ),
            "violations": list(run.violations),
        },
    )


def decode_model_run(envelope: SerializationEnvelope) -> ModelRun:
    payload = _payload(
        envelope,
        "marko.model_run",
        1,
        {
            "run_id",
            "created_at",
            "model_id",
            "code_version",
            "environment_fingerprint",
            "dataset_fingerprint",
            "policy_id",
            "policy_version",
            "universe_id",
            "universe_version",
            "parameters",
            "random_seed",
            "solver",
            "candidate",
            "validated_candidate",
            "violations",
        },
    )
    validated_payload = payload.get("validated_candidate")
    return ModelRun(
        run_id=_text(payload.get("run_id"), "run_id"),
        created_at=_datetime(payload.get("created_at"), "created_at"),
        model_id=_text(payload.get("model_id"), "model_id"),
        code_version=_text(payload.get("code_version"), "code_version"),
        environment_fingerprint=_text(
            payload.get("environment_fingerprint"), "environment_fingerprint"
        ),
        dataset_fingerprint=_text(payload.get("dataset_fingerprint"), "dataset_fingerprint"),
        policy_id=_text(payload.get("policy_id"), "policy_id"),
        policy_version=_integer(payload.get("policy_version"), "policy_version"),
        universe_id=_text(payload.get("universe_id"), "universe_id"),
        universe_version=_integer(payload.get("universe_version"), "universe_version"),
        parameters=_decode_pairs(payload.get("parameters"), "parameters"),
        random_seed=_integer(payload.get("random_seed"), "random_seed"),
        solver=_decode_solver(payload.get("solver")),
        candidate=_decode_candidate(payload.get("candidate")),
        validated_candidate=(
            _decode_validated_candidate(validated_payload)
            if validated_payload is not None
            else None
        ),
        violations=_text_tuple(payload.get("violations"), "violations"),
    )


def encode_decision_packet(packet: DecisionPacket) -> SerializationEnvelope:
    return SerializationEnvelope(
        "marko.decision_packet",
        1,
        {
            "packet_id": packet.packet_id,
            "created_at": packet.created_at.isoformat(),
            "policy_id": packet.policy_id,
            "policy_version": packet.policy_version,
            "model_runs": [_model_ref(reference) for reference in packet.model_runs],
            "evidence_ids": list(packet.evidence_ids),
            "alternatives": [_alternative(alternative) for alternative in packet.alternatives],
        },
    )


def decode_decision_packet(envelope: SerializationEnvelope) -> DecisionPacket:
    payload = _payload(
        envelope,
        "marko.decision_packet",
        1,
        {
            "packet_id",
            "created_at",
            "policy_id",
            "policy_version",
            "model_runs",
            "evidence_ids",
            "alternatives",
        },
    )
    return DecisionPacket(
        packet_id=_text(payload.get("packet_id"), "packet_id"),
        created_at=_datetime(payload.get("created_at"), "created_at"),
        policy_id=_text(payload.get("policy_id"), "policy_id"),
        policy_version=_integer(payload.get("policy_version"), "policy_version"),
        model_runs=tuple(
            _decode_model_ref(value) for value in _sequence(payload.get("model_runs"), "model_runs")
        ),
        evidence_ids=_text_tuple(payload.get("evidence_ids"), "evidence_ids"),
        alternatives=tuple(
            _decode_alternative(value)
            for value in _sequence(payload.get("alternatives"), "alternatives")
        ),
    )


def _money(value: Money | None) -> dict[str, JsonValue] | None:
    if value is None:
        return None
    return {"amount": str(value.amount), "currency": value.currency}


def _optional_money(value: object) -> Money | None:
    if value is None:
        return None
    mapping = _mapping(value, "money")
    return Money.of(
        _text(mapping.get("amount"), "money.amount"),
        _text(mapping.get("currency"), "money.currency"),
    )


def _decimal(value: Decimal | None) -> str | None:
    return str(value) if value is not None else None


def _optional_decimal(value: object) -> Decimal | None:
    return None if value is None else _required_decimal(value, "decimal")


def _required_decimal(value: object, name: str) -> Decimal:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} precisa ser decimal")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"{name} precisa ser finito")
    return result


def _times(value: TimeCoordinates) -> dict[str, JsonValue]:
    return {
        "effective_at": value.effective_at.isoformat(),
        "observed_at": value.observed_at.isoformat(),
        "available_at": value.available_at.isoformat(),
        "ingested_at": value.ingested_at.isoformat(),
    }


def _decode_times(value: object) -> TimeCoordinates:
    mapping = _mapping(value, "times")
    return TimeCoordinates(
        _datetime(mapping.get("effective_at"), "times.effective_at"),
        _datetime(mapping.get("observed_at"), "times.observed_at"),
        _datetime(mapping.get("available_at"), "times.available_at"),
        _datetime(mapping.get("ingested_at"), "times.ingested_at"),
    )


def _problem(value: PortfolioProblem) -> dict[str, JsonValue]:
    return {
        "assets": list(value.assets),
        "returns": [list(row) for row in value.returns],
        "current_weights": list(value.current_weights),
        "minimum_weights": list(value.minimum_weights),
        "maximum_weights": list(value.maximum_weights),
    }


def _decode_problem(value: object) -> PortfolioProblem:
    mapping = _mapping(value, "problem")
    returns = tuple(
        tuple(_number(item, "returns") for item in _sequence(row, "returns.row"))
        for row in _sequence(mapping.get("returns"), "returns")
    )
    return PortfolioProblem(
        _text_tuple(mapping.get("assets"), "assets"),
        returns,
        _number_tuple(mapping.get("current_weights"), "current_weights"),
        _number_tuple(mapping.get("minimum_weights"), "minimum_weights"),
        _number_tuple(mapping.get("maximum_weights"), "maximum_weights"),
    )


def _candidate(value: PortfolioCandidate) -> dict[str, JsonValue]:
    return {
        "model_id": value.model_id,
        "assets": list(value.assets),
        "weights": list(value.weights),
        "expected_return": value.expected_return,
        "volatility": value.volatility,
        "solver_status": value.solver_status,
        "diagnostics": _pairs(value.diagnostics),
    }


def _decode_candidate(value: object) -> PortfolioCandidate:
    mapping = _mapping(value, "candidate")
    return PortfolioCandidate(
        _text(mapping.get("model_id"), "candidate.model_id"),
        _text_tuple(mapping.get("assets"), "candidate.assets"),
        _number_tuple(mapping.get("weights"), "candidate.weights"),
        _number(mapping.get("expected_return"), "candidate.expected_return"),
        _number(mapping.get("volatility"), "candidate.volatility"),
        _text(mapping.get("solver_status"), "candidate.solver_status"),
        _decode_pairs(mapping.get("diagnostics"), "candidate.diagnostics"),
    )


def _validated_candidate(value: ValidatedPortfolioCandidate) -> dict[str, JsonValue]:
    return {"candidate": _candidate(value.candidate), "problem": _problem(value.problem)}


def _decode_validated_candidate(value: object) -> ValidatedPortfolioCandidate:
    mapping = _mapping(value, "validated_candidate")
    return ValidatedPortfolioCandidate(
        _decode_candidate(mapping.get("candidate")),
        _decode_problem(mapping.get("problem")),
    )


def _solver(value: SolverRecord) -> dict[str, JsonValue]:
    return {
        "solver_id": value.solver_id,
        "version": value.version,
        "tolerances": [[key, tolerance] for key, tolerance in value.tolerances],
        "capabilities": list(value.capabilities),
    }


def _decode_solver(value: object) -> SolverRecord:
    mapping = _mapping(value, "solver")
    tolerances = tuple(
        (
            _text(_sequence(item, "solver.tolerance")[0], "solver.tolerance.key"),
            _number(_sequence(item, "solver.tolerance")[1], "solver.tolerance.value"),
        )
        for item in _sequence(mapping.get("tolerances"), "solver.tolerances")
    )
    return SolverRecord(
        _text(mapping.get("solver_id"), "solver.solver_id"),
        _text(mapping.get("version"), "solver.version"),
        tolerances,
        _text_tuple(mapping.get("capabilities"), "solver.capabilities"),
    )


def _model_ref(value: ValidatedModelRunRef) -> dict[str, JsonValue]:
    return {"run_id": value.run_id, "candidate": _validated_candidate(value.candidate)}


def _decode_model_ref(value: object) -> ValidatedModelRunRef:
    mapping = _mapping(value, "model_ref")
    return ValidatedModelRunRef(
        _text(mapping.get("run_id"), "model_ref.run_id"),
        _decode_validated_candidate(mapping.get("candidate")),
    )


def _trade(value: TradeProposal) -> dict[str, JsonValue]:
    return {
        "instrument_id": value.instrument_id,
        "side": value.side.value,
        "quantity": str(value.quantity),
        "notional": _money(value.notional),
        "estimated_cost": _money(value.estimated_cost),
    }


def _decode_trade(value: object) -> TradeProposal:
    mapping = _mapping(value, "trade")
    notional = _optional_money(mapping.get("notional"))
    estimated_cost = _optional_money(mapping.get("estimated_cost"))
    if notional is None or estimated_cost is None:
        raise ValueError("trade exige notional e estimated_cost")
    return TradeProposal(
        _text(mapping.get("instrument_id"), "trade.instrument_id"),
        TradeSide(_text(mapping.get("side"), "trade.side")),
        _required_decimal(mapping.get("quantity"), "trade.quantity"),
        notional,
        estimated_cost,
    )


def _alternative(value: DecisionAlternative) -> dict[str, JsonValue]:
    return {
        "alternative_id": value.alternative_id,
        "trades": [_trade(trade) for trade in value.trades],
        "projected_weights": _decimal_pairs(value.projected_weights),
        "unallocated_cash": _money(value.unallocated_cash),
        "turnover": str(value.turnover),
        "feasible": value.feasible,
        "reasons": list(value.reasons),
    }


def _decode_alternative(value: object) -> DecisionAlternative:
    mapping = _mapping(value, "alternative")
    unallocated = _optional_money(mapping.get("unallocated_cash"))
    if unallocated is None:
        raise ValueError("alternative exige unallocated_cash")
    return DecisionAlternative(
        _text(mapping.get("alternative_id"), "alternative.alternative_id"),
        tuple(_decode_trade(item) for item in _sequence(mapping.get("trades"), "trades")),
        _decode_decimal_pairs(mapping.get("projected_weights"), "projected_weights"),
        unallocated,
        _required_decimal(mapping.get("turnover"), "turnover"),
        _boolean(mapping.get("feasible"), "feasible"),
        _text_tuple(mapping.get("reasons"), "reasons"),
    )


def _pairs(values: tuple[tuple[str, str], ...]) -> list[JsonValue]:
    return [[key, value] for key, value in values]


def _decimal_pairs(values: tuple[tuple[str, Decimal], ...]) -> list[JsonValue]:
    return [[key, str(value)] for key, value in values]


def _decode_pairs(value: object, name: str) -> tuple[tuple[str, str], ...]:
    pairs = []
    for raw in _sequence(value, name):
        item = _sequence(raw, f"{name}.item")
        if len(item) != 2:
            raise ValueError(f"{name} exige pares")
        pairs.append((_text(item[0], f"{name}.key"), _text(item[1], f"{name}.value")))
    return tuple(pairs)


def _decode_decimal_pairs(value: object, name: str) -> tuple[tuple[str, Decimal], ...]:
    pairs = []
    for raw in _sequence(value, name):
        item = _sequence(raw, f"{name}.item")
        if len(item) != 2:
            raise ValueError(f"{name} exige pares")
        pairs.append(
            (_text(item[0], f"{name}.key"), _required_decimal(item[1], f"{name}.value"))
        )
    return tuple(pairs)


def _payload(
    envelope: SerializationEnvelope,
    schema: str,
    version: int,
    expected_keys: set[str],
) -> dict[str, JsonValue]:
    if envelope.schema != schema or envelope.version != version:
        raise UnsupportedSchemaError(
            f"contrato não suportado: {envelope.schema}@{envelope.version}; "
            f"esperado {schema}@{version}"
        )
    _exact_keys(envelope.payload, expected_keys, f"{schema}@{version}.payload")
    return envelope.payload


def _exact_keys(value: Mapping[str, object], expected: set[str], name: str) -> None:
    actual = set(value)
    if actual != expected:
        missing = ", ".join(sorted(expected - actual)) or "nenhuma"
        unknown = ", ".join(sorted(actual - expected)) or "nenhuma"
        raise ValueError(f"{name} incompatível; ausentes: {missing}; desconhecidas: {unknown}")


def _mapping(value: object, name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{name} precisa ser objeto")
    return cast(Mapping[str, object], value)


def _sequence(value: object, name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{name} precisa ser lista")
    return cast(Sequence[object], value)


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} precisa ser texto não vazio")
    return value


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    return _text(value, "texto opcional")


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{name} precisa ser inteiro")
    return value


def _number(value: object, name: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{name} precisa ser número")
    result = float(value)
    if not Decimal(str(result)).is_finite():
        raise ValueError(f"{name} precisa ser finito")
    return result


def _boolean(value: object, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} precisa ser booleano")
    return value


def _datetime(value: object, name: str) -> datetime:
    result = datetime.fromisoformat(_text(value, name))
    if result.tzinfo is None:
        raise ValueError(f"{name} precisa de timezone")
    return result


def _text_tuple(value: object, name: str) -> tuple[str, ...]:
    return tuple(_text(item, f"{name}.item") for item in _sequence(value, name))


def _number_tuple(value: object, name: str) -> tuple[float, ...]:
    return tuple(_number(item, f"{name}.item") for item in _sequence(value, name))
