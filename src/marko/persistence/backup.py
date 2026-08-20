from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from marko.persistence.codec import (
    SerializationEnvelope,
    decode_activity,
    decode_decision_packet,
    decode_model_run,
    decode_observation,
    encode_activity,
    encode_decision_packet,
    encode_model_run,
    encode_observation,
)
from marko.persistence.contracts import PersistenceStore
from marko.persistence.errors import PersistenceIntegrityError


@dataclass(frozen=True, slots=True)
class BackupManifest:
    content_hash: str
    activities: int
    observations: int
    model_runs: int
    decision_packets: int


def create_backup(path: str | Path, store: PersistenceStore) -> BackupManifest:
    target = Path(path)
    collections: dict[str, list[object]] = {
        "activities": [_document(encode_activity(value)) for value in store.activities()],
        "observations": [_document(encode_observation(value)) for value in store.observations()],
        "model_runs": [_document(encode_model_run(value)) for value in store.model_runs()],
        "decision_packets": [
            _document(encode_decision_packet(value)) for value in store.decision_packets()
        ],
    }
    content_hash = _content_hash(collections)
    document = {
        "format": "marko.backup",
        "version": 1,
        "content_hash": content_hash,
        "collections": collections,
    }
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
    return _manifest(content_hash, collections)


def verify_backup(path: str | Path) -> BackupManifest:
    collections, content_hash = _load(path)
    return _manifest(content_hash, collections)


def restore_backup(path: str | Path, store: PersistenceStore) -> BackupManifest:
    collections, content_hash = _load(path)
    store.append_activities(
        tuple(decode_activity(_envelope(value)) for value in collections["activities"])
    )
    for value in collections["observations"]:
        store.append_observation(decode_observation(_envelope(value)))
    for value in collections["model_runs"]:
        store.append_model_run(decode_model_run(_envelope(value)))
    for value in collections["decision_packets"]:
        store.append_decision_packet(decode_decision_packet(_envelope(value)))
    return _manifest(content_hash, collections)


def _load(
    path: str | Path,
) -> tuple[dict[str, list[object]], str]:
    try:
        document = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PersistenceIntegrityError("backup ilegível") from error
    if not isinstance(document, dict):
        raise PersistenceIntegrityError("backup precisa ser objeto")
    if document.get("format") != "marko.backup" or document.get("version") != 1:
        raise PersistenceIntegrityError("formato de backup não suportado")
    raw_collections = document.get("collections")
    if not isinstance(raw_collections, dict):
        raise PersistenceIntegrityError("collections ausente")
    expected_keys = {"activities", "observations", "model_runs", "decision_packets"}
    if set(raw_collections) != expected_keys:
        raise PersistenceIntegrityError("collections incompatíveis")
    collections: dict[str, list[object]] = {}
    for key in expected_keys:
        values = raw_collections[key]
        if not isinstance(values, list):
            raise PersistenceIntegrityError(f"collection inválida: {key}")
        collections[key] = cast(list[object], values)
    content_hash = document.get("content_hash")
    if not isinstance(content_hash, str) or content_hash != _content_hash(collections):
        raise PersistenceIntegrityError("hash do backup diverge")
    return collections, content_hash


def _document(envelope: SerializationEnvelope) -> dict[str, object]:
    return cast(dict[str, object], json.loads(envelope.canonical_json()))


def _envelope(value: object) -> SerializationEnvelope:
    return SerializationEnvelope.from_json(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )


def _content_hash(collections: object) -> str:
    canonical = json.dumps(collections, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _manifest(content_hash: str, collections: dict[str, list[object]]) -> BackupManifest:
    return BackupManifest(
        content_hash,
        len(collections["activities"]),
        len(collections["observations"]),
        len(collections["model_runs"]),
        len(collections["decision_packets"]),
    )
