"""Persistência auditável do Marko."""

from marko.persistence.backup import (
    BackupManifest,
    create_backup,
    restore_backup,
    verify_backup,
)
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
from marko.persistence.contracts import (
    ActivityRepository,
    DecisionPacketRepository,
    ModelRunRepository,
    ObservationRepository,
)
from marko.persistence.errors import (
    PersistenceConflictError,
    PersistenceIntegrityError,
    UnsupportedSchemaError,
)
from marko.persistence.parquet import DatasetArtifact, ParquetObservationStore
from marko.persistence.postgres import PostgresStore

__all__ = [
    "ActivityRepository",
    "BackupManifest",
    "DatasetArtifact",
    "DecisionPacketRepository",
    "ModelRunRepository",
    "ObservationRepository",
    "ParquetObservationStore",
    "PersistenceConflictError",
    "PersistenceIntegrityError",
    "PostgresStore",
    "SerializationEnvelope",
    "UnsupportedSchemaError",
    "create_backup",
    "decode_activity",
    "decode_decision_packet",
    "decode_model_run",
    "decode_observation",
    "encode_activity",
    "encode_decision_packet",
    "encode_model_run",
    "encode_observation",
    "restore_backup",
    "verify_backup",
]
