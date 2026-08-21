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
    decode_shadow_run_request,
    encode_activity,
    encode_decision_packet,
    encode_model_run,
    encode_observation,
    encode_shadow_run_request,
)
from marko.persistence.contracts import (
    ActivityRepository,
    DecisionPacketRepository,
    ModelRunRepository,
    ObservationRepository,
    ShadowCycleRepository,
    ShadowRunRequestRepository,
)
from marko.persistence.errors import (
    PersistenceConflictError,
    PersistenceIntegrityError,
    UnsupportedSchemaError,
)
from marko.persistence.parquet import DatasetArtifact, ParquetObservationStore
from marko.persistence.postgres import PostgresStore
from marko.persistence.shadow_postgres import ShadowPostgresStore
from marko.shadow_operation import (
    ShadowCycleEnvelope,
    decode_shadow_cycle_record,
    encode_shadow_cycle_record,
)

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
    "ShadowCycleEnvelope",
    "ShadowCycleRepository",
    "ShadowPostgresStore",
    "ShadowRunRequestRepository",
    "UnsupportedSchemaError",
    "create_backup",
    "decode_activity",
    "decode_decision_packet",
    "decode_model_run",
    "decode_observation",
    "decode_shadow_cycle_record",
    "decode_shadow_run_request",
    "encode_activity",
    "encode_decision_packet",
    "encode_model_run",
    "encode_observation",
    "encode_shadow_cycle_record",
    "encode_shadow_run_request",
    "restore_backup",
    "verify_backup",
]
