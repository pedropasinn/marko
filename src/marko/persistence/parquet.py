from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from marko.persistence.codec import (
    SerializationEnvelope,
    decode_observation,
    encode_observation,
)
from marko.persistence.errors import PersistenceConflictError, PersistenceIntegrityError
from marko.temporal import Observation

_DATASET_ID = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class DatasetArtifact:
    dataset_id: str
    path: Path
    content_hash: str
    file_hash: str
    rows: int
    schema: str = "marko.observation@1"


class ParquetObservationStore:
    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def write(
        self, dataset_id: str, observations: tuple[Observation, ...]
    ) -> DatasetArtifact:
        if not _DATASET_ID.fullmatch(dataset_id):
            raise ValueError("dataset_id contém caracteres inválidos")
        if not observations:
            raise ValueError("dataset exige observações")
        ordered = tuple(sorted(observations, key=lambda value: value.observation_id))
        identifiers = [value.observation_id for value in ordered]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("dataset contém observation_id duplicado")
        envelopes = [encode_observation(value).canonical_json() for value in ordered]
        content_hash = hashlib.sha256("\n".join(envelopes).encode()).hexdigest()
        self._root.mkdir(parents=True, exist_ok=True)
        target = self._root / f"{dataset_id}-{content_hash[:16]}.parquet"
        if target.exists():
            artifact, existing = self.read(target)
            if existing != ordered or artifact.content_hash != content_hash:
                raise PersistenceConflictError(f"artefato conflitante: {target.name}")
            return artifact
        pa, parquet = _pyarrow()
        table = pa.table(
            {
                "observation_id": identifiers,
                "series_id": [value.series_id for value in ordered],
                "effective_at": [value.times.effective_at for value in ordered],
                "available_at": [value.times.available_at for value in ordered],
                "vintage_id": [value.vintage_id for value in ordered],
                "payload": envelopes,
            }
        )
        metadata = dict(table.schema.metadata or {})
        metadata.update(
            {
                b"marko.schema": b"marko.observation@1",
                b"marko.dataset_id": dataset_id.encode(),
                b"marko.content_hash": content_hash.encode(),
            }
        )
        table = table.replace_schema_metadata(metadata)
        with tempfile.NamedTemporaryFile(
            dir=self._root,
            prefix=f".{dataset_id}.",
            suffix=".parquet",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            parquet.write_table(table, temporary_path, compression="zstd")
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        artifact, restored = self.read(target)
        if restored != ordered:
            raise PersistenceIntegrityError("round-trip Parquet divergiu")
        return artifact

    def read(self, path: str | Path) -> tuple[DatasetArtifact, tuple[Observation, ...]]:
        source = Path(path)
        _, parquet = _pyarrow()
        try:
            table = parquet.read_table(source)
        except (OSError, ValueError) as error:
            raise PersistenceIntegrityError("artefato Parquet ilegível") from error
        metadata = table.schema.metadata or {}
        if metadata.get(b"marko.schema") != b"marko.observation@1":
            raise PersistenceIntegrityError("schema Parquet não suportado")
        dataset_raw = metadata.get(b"marko.dataset_id")
        content_raw = metadata.get(b"marko.content_hash")
        if dataset_raw is None or content_raw is None:
            raise PersistenceIntegrityError("metadados Parquet incompletos")
        dataset_id = dataset_raw.decode()
        expected_hash = content_raw.decode()
        payloads = tuple(str(value) for value in table.column("payload").to_pylist())
        actual_hash = hashlib.sha256("\n".join(payloads).encode()).hexdigest()
        if actual_hash != expected_hash:
            raise PersistenceIntegrityError("hash do conteúdo Parquet diverge")
        observations = tuple(
            decode_observation(SerializationEnvelope.from_json(value)) for value in payloads
        )
        file_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        return (
            DatasetArtifact(
                dataset_id,
                source,
                actual_hash,
                file_hash,
                len(observations),
            ),
            observations,
        )


def _pyarrow() -> tuple[Any, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as parquet
    except ImportError as error:
        raise RuntimeError("instale o extra persistence para usar Parquet") from error
    return cast(Any, pa), cast(Any, parquet)
