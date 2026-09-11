from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from marko.experiment.config import digest


def write_json(path: Path, payload: Any, *, immutable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    descriptor, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        if immutable:
            try:
                os.link(temporary, path)
            except FileExistsError:
                if path.read_text() != content:
                    raise ValueError(f"conflito append-only: {path.name}") from None
        else:
            os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(temporary).unlink(missing_ok=True)


def read_records(root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    previous_hash: str | None = None
    for path in sorted((root / "records").glob("*.json")):
        record = json.loads(path.read_text())
        claimed = record.pop("record_hash")
        if digest(record) != claimed or record["previous_hash"] != previous_hash:
            raise ValueError("cadeia histórica inválida")
        record["record_hash"] = claimed
        if path.stem != record["session"] or (
            records
            and (
                record["session"] <= records[-1]["session"]
                or record["campaign_id"] != records[-1]["campaign_id"]
                or record["config_hash"] != records[-1]["config_hash"]
            )
        ):
            raise ValueError("identidade ou configuração histórica divergente")
        previous_hash = claimed
        records.append(record)
    return records


def verify_artifacts(root: Path, records: list[dict[str, Any]] | None = None) -> None:
    from marko.persistence.codec import SerializationEnvelope, decode_model_run

    for record in read_records(root) if records is None else records:
        data_hash = record["data_hash"]
        snapshot = json.loads((root / "snapshots" / f"{data_hash}.json").read_text())
        if (
            snapshot["data_hash"] != data_hash
            or digest({key: value for key, value in snapshot.items() if key != "data_hash"})
            != data_hash
        ):
            raise ValueError("snapshot histórico corrompido")
        if (
            snapshot["session"] < record["session"]
            or snapshot["observed_at"] != record["knowledge_cutoff"]
            or datetime.fromisoformat(snapshot["observed_at"])
            > datetime.fromisoformat(record["observed_at"])
        ):
            raise ValueError("temporalidade do snapshot diverge do registro")
        for decision in record["decisions"]:
            if decision["action"] != "SCHEDULED":
                continue
            pending = {
                key: value
                for key, value in decision.items()
                if key not in {"action", "reason", "decision_id"}
            }
            if digest(pending) != decision["decision_id"] or decision["data_hash"] != data_hash:
                raise ValueError("decisão histórica corrompida")
            run_id = decision["model_run_id"]
            if run_id is None:
                continue
            path = root / "model-runs" / f"{run_id}.json"
            raw = path.read_text()
            if digest(json.loads(raw)) != decision["model_run_hash"]:
                raise ValueError("ModelRun histórico corrompido")
            run = decode_model_run(SerializationEnvelope.from_json(raw))
            if (
                run.run_id != run_id
                or run.dataset_fingerprint != data_hash
                or run.policy_id != record["campaign_id"]
                or run.candidate.weight_map() != decision["weights"]
                or run.created_at.isoformat() != decision["created_at"]
            ):
                raise ValueError("ModelRun diverge da decisão histórica")


def append_record(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    record = dict(record)
    record["record_hash"] = digest(record)
    write_json(root / "records" / f"{record['session']}.json", record, immutable=True)
    return record
