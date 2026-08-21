from __future__ import annotations

import hashlib
import hmac
import json
import os
import tempfile
from base64 import b64decode, b64encode
from binascii import Error as Base64Error
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from marko.activities import Activity
from marko.decision import DecisionPacket
from marko.ledger import Ledger
from marko.persistence.codec import (
    SerializationEnvelope,
    decode_activity,
    decode_decision_packet,
    decode_model_run,
    decode_observation,
    decode_shadow_run_request,
    encode_activity,
    encode_decision_packet,
    encode_model_run,
    encode_observation,
    encode_shadow_run_request,
)
from marko.persistence.contracts import PersistenceStore
from marko.persistence.errors import PersistenceIntegrityError
from marko.research_registry import ModelRun
from marko.shadow import ShadowRunRequest
from marko.shadow_operation import (
    ShadowCycleEnvelope,
    ShadowCycleRecord,
    decode_shadow_cycle_record,
    encode_shadow_cycle_record,
    shadow_cycle_reference_ids,
)
from marko.temporal import Observation

_LEGACY_COLLECTION_NAMES = {"activities", "observations", "model_runs", "decision_packets"}
_COLLECTION_NAMES_V3 = _LEGACY_COLLECTION_NAMES | {"shadow_run_requests"}
_COLLECTION_NAMES = _COLLECTION_NAMES_V3 | {"shadow_cycle_records"}
_SCHEMAS_V2 = {
    "activities": "marko.activity@1",
    "observations": "marko.observation@1",
    "model_runs": "marko.model_run@1",
    "decision_packets": "marko.decision_packet@1",
}
_SCHEMAS_V3_LEGACY = _SCHEMAS_V2 | {
    "decision_packets": "marko.decision_packet@2",
    "shadow_run_requests": "marko.shadow_run_request@1",
}
_SCHEMAS_V3 = _SCHEMAS_V3_LEGACY | {
    "decision_packets": "marko.decision_packet@3",
}
_SCHEMAS = _SCHEMAS_V3 | {
    "shadow_cycle_records": "marko.shadow_cycle_record@1",
}


@dataclass(frozen=True, slots=True)
class BackupManifest:
    content_hash: str
    activities: int
    observations: int
    model_runs: int
    decision_packets: int
    shadow_run_requests: int = 0
    format_version: int = 3
    authenticated: bool = False
    key_id: str | None = None
    encrypted: bool = False
    shadow_cycle_records: int = 0


@dataclass(frozen=True, slots=True)
class _RestoreBatch:
    activities: tuple[Activity, ...]
    observations: tuple[Observation, ...]
    model_runs: tuple[ModelRun, ...]
    shadow_run_requests: tuple[ShadowRunRequest, ...]
    decision_packets: tuple[DecisionPacket, ...]
    shadow_cycle_records: tuple[ShadowCycleRecord, ...]


@runtime_checkable
class _AtomicRestoreStore(Protocol):
    def restore_validated(
        self,
        activities: tuple[Activity, ...],
        observations: tuple[Observation, ...],
        model_runs: tuple[ModelRun, ...],
        shadow_run_requests: tuple[ShadowRunRequest, ...],
        decision_packets: tuple[DecisionPacket, ...],
        shadow_cycle_records: tuple[ShadowCycleRecord, ...],
    ) -> None: ...


class _CanonicalEnvelope(Protocol):
    def canonical_json(self) -> str: ...


def create_backup(
    path: str | Path,
    store: PersistenceStore,
    *,
    authentication_key: bytes | None = None,
    key_id: str | None = None,
    encryption_key: str | None = None,
) -> BackupManifest:
    if authentication_key is not None and encryption_key is not None:
        raise ValueError("use autenticação HMAC ou criptografia, não ambas")
    if encryption_key is None:
        _validate_authentication_options(authentication_key, key_id)
    elif key_id is not None and not key_id.strip():
        raise ValueError("key_id não pode ser vazio")
    target = Path(path)
    collections: dict[str, list[object]] = {
        "activities": [_document(encode_activity(value)) for value in store.activities()],
        "observations": [_document(encode_observation(value)) for value in store.observations()],
        "model_runs": [_document(encode_model_run(value)) for value in store.model_runs()],
        "shadow_run_requests": [
            _document(encode_shadow_run_request(value)) for value in store.shadow_run_requests()
        ],
        "decision_packets": [
            _document(encode_decision_packet(value)) for value in store.decision_packets()
        ],
        "shadow_cycle_records": [
            _document(encode_shadow_cycle_record(value)) for value in store.shadow_cycle_records()
        ],
    }
    content_hash = _content_hash(collections)
    authentication = (
        {"algorithm": "hmac-sha256", "key_id": key_id} if authentication_key is not None else None
    )
    document: dict[str, object] = {
        "format": "marko.backup",
        "version": 3,
        "metadata": {
            "version": 4,
            "schemas": _SCHEMAS,
            "content_hash_algorithm": "sha256",
            "authentication": authentication,
        },
        "content_hash": content_hash,
        "collections": collections,
        "authentication_tag": None,
    }
    if authentication_key is not None:
        document["authentication_tag"] = _authentication_tag(document, authentication_key)
    output_document = document
    output_version = 3
    output_key_id = key_id
    encrypted = False
    if encryption_key is not None:
        key = _decode_encryption_key(encryption_key)
        output_key_id = key_id or _derived_key_id(key)
        output_document = _encrypt_document(document, key, output_key_id)
        output_version = 4
        encrypted = True
    _write_document(target, output_document)
    return _manifest(
        content_hash,
        collections,
        output_version,
        authentication is not None or encrypted,
        output_key_id,
        encrypted=encrypted,
    )


def _write_document(target: Path, document: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as temporary:
            json.dump(
                document,
                temporary,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, target)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def verify_backup(
    path: str | Path,
    *,
    authentication_key: bytes | None = None,
    encryption_key: str | None = None,
) -> BackupManifest:
    collections, content_hash, format_version, key_id, encrypted = _load(
        path, authentication_key, encryption_key
    )
    _decode_and_validate(collections)
    return _manifest(
        content_hash,
        collections,
        format_version,
        key_id is not None,
        key_id,
        encrypted=encrypted,
    )


def restore_backup(
    path: str | Path,
    store: PersistenceStore,
    *,
    authentication_key: bytes | None = None,
    encryption_key: str | None = None,
) -> BackupManifest:
    collections, content_hash, format_version, key_id, encrypted = _load(
        path, authentication_key, encryption_key
    )
    batch = _decode_and_validate(collections)
    if isinstance(store, _AtomicRestoreStore):
        store.restore_validated(
            batch.activities,
            batch.observations,
            batch.model_runs,
            batch.shadow_run_requests,
            batch.decision_packets,
            batch.shadow_cycle_records,
        )
    else:
        # Adaptadores externos preservam compatibilidade; o PostgreSQL usa a rota atômica acima.
        store.append_activities(batch.activities)
        for observation in batch.observations:
            store.append_observation(observation)
        for run in batch.model_runs:
            store.append_model_run(run)
        for request in batch.shadow_run_requests:
            store.append_shadow_run_request(request)
        for packet in batch.decision_packets:
            store.append_decision_packet(packet)
        for record in batch.shadow_cycle_records:
            store.append_shadow_cycle_record(record)
    return _manifest(
        content_hash,
        collections,
        format_version,
        key_id is not None,
        key_id,
        encrypted=encrypted,
    )


def _load(
    path: str | Path,
    authentication_key: bytes | None,
    encryption_key: str | None,
) -> tuple[dict[str, list[object]], str, int, str | None, bool]:
    try:
        document = json.loads(
            Path(path).read_text(encoding="utf-8"),
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise PersistenceIntegrityError("backup ilegível") from error
    if not isinstance(document, dict):
        raise PersistenceIntegrityError("backup precisa ser objeto")
    if document.get("format") == "marko.backup.encrypted":
        document, encrypted_key_id = _decrypt_document(document, encryption_key)
        collections, content_hash, _, inner_key_id = _load_document(document, authentication_key)
        if inner_key_id is not None:
            raise PersistenceIntegrityError("backup criptografado inválido")
        return collections, content_hash, 4, encrypted_key_id, True
    collections, content_hash, version, key_id = _load_document(document, authentication_key)
    return collections, content_hash, version, key_id, False


def _load_document(
    document: dict[str, object], authentication_key: bytes | None
) -> tuple[dict[str, list[object]], str, int, str | None]:
    if document.get("format") != "marko.backup":
        raise PersistenceIntegrityError("formato de backup não suportado")
    version = document.get("version")
    if version == 1:
        _exact_keys(
            document,
            {"format", "version", "content_hash", "collections"},
            "backup v1",
        )
        key_id = None
        collection_names = _LEGACY_COLLECTION_NAMES
    elif version == 2:
        _exact_keys(
            document,
            {
                "format",
                "version",
                "metadata",
                "content_hash",
                "collections",
                "authentication_tag",
            },
            "backup v2",
        )
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            raise PersistenceIntegrityError("metadados do backup ausentes")
        _exact_keys(
            metadata,
            {"version", "schemas", "content_hash_algorithm", "authentication"},
            "metadata",
        )
        if (
            metadata.get("version") != 1
            or metadata.get("schemas") != _SCHEMAS_V2
            or metadata.get("content_hash_algorithm") != "sha256"
        ):
            raise PersistenceIntegrityError("metadados do backup não suportados")
        key_id = _verify_authentication(document, metadata, authentication_key)
        collection_names = _LEGACY_COLLECTION_NAMES
    elif version == 3:
        _exact_keys(
            document,
            {
                "format",
                "version",
                "metadata",
                "content_hash",
                "collections",
                "authentication_tag",
            },
            "backup v3",
        )
        metadata = document.get("metadata")
        if not isinstance(metadata, dict):
            raise PersistenceIntegrityError("metadados do backup ausentes")
        _exact_keys(
            metadata,
            {"version", "schemas", "content_hash_algorithm", "authentication"},
            "metadata",
        )
        metadata_version = metadata.get("version")
        if metadata_version == 2:
            expected_schemas = _SCHEMAS_V3_LEGACY
            collection_names = _COLLECTION_NAMES_V3
        elif metadata_version == 3:
            expected_schemas = _SCHEMAS_V3
            collection_names = _COLLECTION_NAMES_V3
        elif metadata_version == 4:
            expected_schemas = _SCHEMAS
            collection_names = _COLLECTION_NAMES
        else:
            raise PersistenceIntegrityError("metadados do backup não suportados")
        if (
            metadata.get("schemas") != expected_schemas
            or metadata.get("content_hash_algorithm") != "sha256"
        ):
            raise PersistenceIntegrityError("metadados do backup não suportados")
        key_id = _verify_authentication(document, metadata, authentication_key)
    else:
        raise PersistenceIntegrityError("formato de backup não suportado")
    raw_collections = document.get("collections")
    if not isinstance(raw_collections, dict):
        raise PersistenceIntegrityError("collections ausente")
    if set(raw_collections) != collection_names:
        raise PersistenceIntegrityError("collections incompatíveis")
    collections: dict[str, list[object]] = {}
    for key in collection_names:
        values = raw_collections[key]
        if not isinstance(values, list):
            raise PersistenceIntegrityError(f"collection inválida: {key}")
        collections[key] = cast(list[object], values)
    content_hash = document.get("content_hash")
    if not isinstance(content_hash, str) or content_hash != _content_hash(collections):
        raise PersistenceIntegrityError("hash do backup diverge")
    return collections, content_hash, version, key_id


def _document(envelope: _CanonicalEnvelope) -> dict[str, object]:
    return cast(dict[str, object], json.loads(envelope.canonical_json()))


def _envelope(value: object) -> SerializationEnvelope:
    return SerializationEnvelope.from_json(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _content_hash(collections: object) -> str:
    canonical = json.dumps(collections, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _manifest(
    content_hash: str,
    collections: dict[str, list[object]],
    format_version: int,
    authenticated: bool,
    key_id: str | None,
    *,
    encrypted: bool = False,
) -> BackupManifest:
    return BackupManifest(
        content_hash,
        len(collections["activities"]),
        len(collections["observations"]),
        len(collections["model_runs"]),
        len(collections["decision_packets"]),
        len(collections.get("shadow_run_requests", [])),
        format_version=format_version,
        authenticated=authenticated,
        key_id=key_id,
        encrypted=encrypted,
        shadow_cycle_records=len(collections.get("shadow_cycle_records", [])),
    )


def _encrypt_document(document: dict[str, object], key: bytes, key_id: str) -> dict[str, object]:
    nonce = os.urandom(12)
    encryption = {
        "algorithm": "aes-256-gcm",
        "key_id": key_id,
        "nonce": b64encode(nonce).decode("ascii"),
    }
    header: dict[str, object] = {
        "format": "marko.backup.encrypted",
        "version": 4,
        "encryption": encryption,
    }
    plaintext = _canonical_json(document).encode()
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _canonical_json(header).encode())
    return header | {"ciphertext": b64encode(ciphertext).decode("ascii")}


def _decrypt_document(
    document: dict[str, object], encryption_key: str | None
) -> tuple[dict[str, object], str]:
    try:
        _exact_keys(
            document,
            {"format", "version", "encryption", "ciphertext"},
            "backup criptografado",
        )
        if document.get("version") != 4:
            raise PersistenceIntegrityError("backup criptografado inválido")
        encryption = document.get("encryption")
        if not isinstance(encryption, dict):
            raise PersistenceIntegrityError("backup criptografado inválido")
        _exact_keys(encryption, {"algorithm", "key_id", "nonce"}, "encryption")
        key_id = encryption.get("key_id")
        nonce_value = encryption.get("nonce")
        ciphertext_value = document.get("ciphertext")
        if (
            encryption.get("algorithm") != "aes-256-gcm"
            or not isinstance(key_id, str)
            or not key_id.strip()
            or not isinstance(nonce_value, str)
            or not isinstance(ciphertext_value, str)
        ):
            raise PersistenceIntegrityError("backup criptografado inválido")
        if encryption_key is None:
            raise PersistenceIntegrityError("backup criptografado exige chave externa")
        key = _decode_encryption_key(encryption_key, integrity_error=True)
        nonce = b64decode(nonce_value, validate=True)
        ciphertext = b64decode(ciphertext_value, validate=True)
        if len(nonce) != 12:
            raise PersistenceIntegrityError("backup criptografado inválido")
        header = {key: value for key, value in document.items() if key != "ciphertext"}
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, _canonical_json(header).encode())
        decoded = json.loads(
            plaintext,
            object_pairs_hook=_unique_json_object,
            parse_constant=_reject_json_constant,
        )
        if not isinstance(decoded, dict):
            raise PersistenceIntegrityError("backup criptografado inválido")
        return decoded, key_id
    except PersistenceIntegrityError:
        raise
    except (Base64Error, InvalidTag, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise PersistenceIntegrityError(
            "backup criptografado inválido ou chave incorreta"
        ) from error


def _decode_encryption_key(value: str, *, integrity_error: bool = False) -> bytes:
    try:
        key = b64decode(value, validate=True)
    except (Base64Error, ValueError) as error:
        if integrity_error:
            raise PersistenceIntegrityError(
                "backup criptografado inválido ou chave incorreta"
            ) from error
        raise ValueError("encryption_key precisa ser base64 válido") from error
    if len(key) != 32:
        if integrity_error:
            raise PersistenceIntegrityError("backup criptografado inválido ou chave incorreta")
        raise ValueError("encryption_key precisa decodificar exatamente 32 bytes")
    return key


def _derived_key_id(key: bytes) -> str:
    return f"sha256:{hashlib.sha256(key).hexdigest()[:16]}"


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _decode_and_validate(collections: dict[str, list[object]]) -> _RestoreBatch:
    try:
        activities = tuple(decode_activity(_envelope(value)) for value in collections["activities"])
        observations = tuple(
            decode_observation(_envelope(value)) for value in collections["observations"]
        )
        model_runs = tuple(
            decode_model_run(_envelope(value)) for value in collections["model_runs"]
        )
        shadow_run_requests = tuple(
            decode_shadow_run_request(_envelope(value))
            for value in collections.get("shadow_run_requests", [])
        )
        decision_packets = tuple(
            decode_decision_packet(_envelope(value)) for value in collections["decision_packets"]
        )
        runs = {run.run_id: run for run in model_runs}
        requests = {request.request_id: request for request in shadow_run_requests}
        packets = {packet.packet_id: packet for packet in decision_packets}
        shadow_cycle_records = tuple(
            _decode_shadow_cycle(value, requests, runs, packets)
            for value in collections.get("shadow_cycle_records", [])
        )
        batch = _RestoreBatch(
            activities,
            observations,
            model_runs,
            shadow_run_requests,
            decision_packets,
            shadow_cycle_records,
        )
        _unique_identifiers(batch)
        Ledger(batch.activities).validate_integrity()
        for packet in batch.decision_packets:
            for reference in packet.model_runs:
                run = runs.get(reference.run_id)
                if run is None or not reference.reconciles_with(run):
                    raise ValueError("DecisionPacket referencia ModelRun ausente ou divergente")
            if packet.shadow_request_id is not None:
                request = requests.get(packet.shadow_request_id)
                if request is None or request.knowledge_cutoff != packet.knowledge_cutoff:
                    raise ValueError(
                        "DecisionPacket referencia ShadowRunRequest ausente ou divergente"
                    )
    except (KeyError, TypeError, ValueError) as error:
        raise PersistenceIntegrityError("conteúdo semântico do backup inválido") from error
    return batch


def _decode_shadow_cycle(
    value: object,
    requests: dict[str, ShadowRunRequest],
    runs: dict[str, ModelRun],
    packets: dict[str, DecisionPacket],
) -> ShadowCycleRecord:
    envelope = ShadowCycleEnvelope.from_json(_canonical_json(value))
    request_id, run_ids, packet_id = shadow_cycle_reference_ids(envelope)
    request = requests.get(request_id)
    packet = packets.get(packet_id)
    referenced_runs = tuple(runs[run_id] for run_id in run_ids if run_id in runs)
    if request is None:
        raise ValueError(f"ShadowCycleRecord referencia request ausente: {request_id}")
    if packet is None:
        raise ValueError(f"ShadowCycleRecord referencia pacote ausente: {packet_id}")
    if len(referenced_runs) != len(run_ids):
        missing = tuple(run_id for run_id in run_ids if run_id not in runs)
        raise ValueError(f"ShadowCycleRecord referencia ModelRuns ausentes: {missing}")
    return decode_shadow_cycle_record(
        envelope,
        request=request,
        model_runs=referenced_runs,
        decision_packet=packet,
    )


def _unique_identifiers(batch: _RestoreBatch) -> None:
    collections = (
        (item.activity_id for item in batch.activities),
        (item.observation_id for item in batch.observations),
        (item.run_id for item in batch.model_runs),
        (item.request_id for item in batch.shadow_run_requests),
        (item.packet_id for item in batch.decision_packets),
        (item.record_id for item in batch.shadow_cycle_records),
    )
    for identifiers in collections:
        values = tuple(identifiers)
        if len(values) != len(set(values)):
            raise ValueError("backup contém identificadores duplicados")


def _validate_authentication_options(key: bytes | None, key_id: str | None) -> None:
    if key is None:
        if key_id is not None:
            raise ValueError("key_id exige authentication_key")
        return
    if len(key) < 32:
        raise ValueError("authentication_key precisa ter ao menos 32 bytes")
    if key_id is None or not key_id.strip():
        raise ValueError("key_id é obrigatório para backup autenticado")


def _verify_authentication(
    document: dict[str, object],
    metadata: dict[str, object],
    key: bytes | None,
) -> str | None:
    authentication = metadata.get("authentication")
    tag = document.get("authentication_tag")
    if authentication is None:
        if tag is not None:
            raise PersistenceIntegrityError("tag sem configuração de autenticação")
        return None
    if not isinstance(authentication, dict):
        raise PersistenceIntegrityError("configuração de autenticação inválida")
    _exact_keys(authentication, {"algorithm", "key_id"}, "authentication")
    key_id = authentication.get("key_id")
    if authentication.get("algorithm") != "hmac-sha256" or not isinstance(key_id, str):
        raise PersistenceIntegrityError("autenticação do backup não suportada")
    if key is None:
        raise PersistenceIntegrityError("backup autenticado exige chave externa")
    if len(key) < 32 or not isinstance(tag, str):
        raise PersistenceIntegrityError("chave ou tag de autenticação inválida")
    expected = _authentication_tag(document, key)
    if not hmac.compare_digest(tag, expected):
        raise PersistenceIntegrityError("autenticação do backup diverge")
    return key_id


def _authentication_tag(document: dict[str, object], key: bytes) -> str:
    unsigned = document | {"authentication_tag": None}
    canonical = json.dumps(
        unsigned,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hmac.new(key, canonical.encode(), hashlib.sha256).hexdigest()


def _exact_keys(value: dict[str, object], expected: set[str], name: str) -> None:
    if set(value) != expected:
        raise PersistenceIntegrityError(f"campos incompatíveis em {name}")


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"chave JSON duplicada: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"constante JSON inválida: {value}")
