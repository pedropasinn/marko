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
            if (
                existing != ordered
                or artifact.content_hash != content_hash
                or artifact.dataset_id != dataset_id
            ):
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
            temporary_artifact, restored = self.read(temporary_path)
            if restored != ordered:
                raise PersistenceIntegrityError("round-trip Parquet divergiu")
            os.replace(temporary_path, target)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
        return DatasetArtifact(
            temporary_artifact.dataset_id,
            target,
            temporary_artifact.content_hash,
            temporary_artifact.file_hash,
            temporary_artifact.rows,
        )

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
        try:
            dataset_id = dataset_raw.decode("utf-8")
            expected_hash = content_raw.decode("ascii")
        except UnicodeError as error:
            raise PersistenceIntegrityError("metadados Parquet inválidos") from error
        if not _DATASET_ID.fullmatch(dataset_id):
            raise PersistenceIntegrityError("dataset_id Parquet inválido")
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            raise PersistenceIntegrityError("content_hash Parquet inválido")
        expected_columns = {
            "observation_id",
            "series_id",
            "effective_at",
            "available_at",
            "vintage_id",
            "payload",
        }
        if set(table.column_names) != expected_columns:
            raise PersistenceIntegrityError("colunas Parquet incompatíveis")
        raw_payloads = table.column("payload").to_pylist()
        if not all(isinstance(value, str) for value in raw_payloads):
            raise PersistenceIntegrityError("payload Parquet precisa ser texto não nulo")
        payloads = cast(tuple[str, ...], tuple(raw_payloads))
        actual_hash = hashlib.sha256("\n".join(payloads).encode()).hexdigest()
        if actual_hash != expected_hash:
            raise PersistenceIntegrityError("hash do conteúdo Parquet diverge")
        try:
            envelopes = tuple(SerializationEnvelope.from_json(value) for value in payloads)
            if any(
                raw != envelope.canonical_json()
                for raw, envelope in zip(payloads, envelopes, strict=True)
            ):
                raise PersistenceIntegrityError("payload Parquet não está em forma canônica")
            observations = tuple(decode_observation(envelope) for envelope in envelopes)
            identifiers = tuple(item.observation_id for item in observations)
            if identifiers != tuple(sorted(identifiers)) or len(identifiers) != len(
                set(identifiers)
            ):
                raise PersistenceIntegrityError(
                    "observações Parquet precisam de IDs únicos em ordem canônica"
                )
            derived_rows = zip(
                table.column("observation_id").to_pylist(),
                table.column("series_id").to_pylist(),
                table.column("effective_at").to_pylist(),
                table.column("available_at").to_pylist(),
                table.column("vintage_id").to_pylist(),
                observations,
                strict=True,
            )
            for observation_id, series_id, effective_at, available_at, vintage_id, item in (
                derived_rows
            ):
                if (
                    observation_id != item.observation_id
                    or series_id != item.series_id
                    or effective_at != item.times.effective_at
                    or available_at != item.times.available_at
                    or vintage_id != item.vintage_id
                ):
                    raise PersistenceIntegrityError("coluna derivada diverge do payload Parquet")
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, PersistenceIntegrityError):
                raise
            raise PersistenceIntegrityError("conteúdo Parquet inválido") from error
        try:
            file_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        except OSError as error:
            raise PersistenceIntegrityError("artefato Parquet ilegível") from error
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
