"""Operação prospectiva: estado privado, código congelado e falha explícita."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import subprocess
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from marko.experiment.config import digest, load_campaign
from marko.experiment.engine import process_session
from marko.experiment.market import fetch_snapshot, schedule
from marko.experiment.reporting import write_reports
from marko.experiment.reviews import read_reviews, run_reviews, run_rule_reviews
from marko.experiment.store import append_record, read_records, verify_artifacts, write_json


def source_identity() -> dict[str, str]:
    source = Path(__file__).resolve().parents[3]
    version = subprocess.check_output(
        ["git", "-C", str(source), "rev-parse", "HEAD"], text=True
    ).strip()
    dirty = subprocess.check_output(
        [
            "git",
            "-C",
            str(source),
            "status",
            "--porcelain",
            "--",
            "src/marko",
            "config",
            "pyproject.toml",
            "uv.lock",
        ],
        text=True,
    ).strip()
    if dirty:
        raise ValueError("código operacional exige checkout limpo e commit identificável")
    return {
        "code_version": version,
        "lock_hash": hashlib.sha256((source / "uv.lock").read_bytes()).hexdigest(),
    }


def ensure_manifest(
    root: Path,
    config: dict[str, Any],
    identity: dict[str, str],
    now: datetime,
) -> dict[str, Any]:
    contract = {
        "schema_version": 1,
        "campaign": config,
        "config_hash": digest(config),
        **identity,
        "mode": "paper_only",
        "api_budget_usd": 0,
    }
    path = root / "manifest.json"
    if path.exists():
        manifest: dict[str, Any] = json.loads(path.read_text())
        if {k: v for k, v in manifest.items() if k != "registered_at"} != contract:
            raise ValueError("campanha congelada: código, dependências ou configuração divergiram")
        return manifest
    if read_records(root):
        raise ValueError("histórico sem manifesto")
    if now.date() > date.fromisoformat(config["end_date"]):
        raise ValueError("campanha encerrada antes do registro inicial")
    manifest = {**contract, "registered_at": now.isoformat()}
    write_json(path, manifest, immutable=True)
    return manifest


def campaign_calendar(config: dict[str, Any], now: datetime) -> dict[str, Any]:
    return schedule(
        date.fromisoformat(config["start_date"]) - timedelta(days=14),
        max(
            date.fromisoformat(config["end_date"]) + timedelta(days=14),
            now.date() + timedelta(days=7),
        ),
    )


def closed_sessions(sessions: dict[str, Any], now: datetime) -> list[str]:
    closes = [(on, datetime.fromisoformat(hours["close"])) for on, hours in sessions.items()]
    if any(close <= now < close + timedelta(minutes=45) for _, close in closes):
        raise ValueError("aguardando margem de 45 minutos após fechamento do fornecedor")
    return sorted(on for on, close in closes if close + timedelta(minutes=45) <= now)


def pending_sessions(
    config: dict[str, Any],
    closed: list[str],
    records: list[dict[str, Any]],
) -> list[str]:
    eligible = [on for on in closed if on <= config["end_date"]]
    if not eligible:
        return []
    if not records:
        # Instalação tardia começa em caixa hoje, sem inventar ordens no passado.
        return [eligible[-1]]
    return [on for on in eligible if on > records[-1]["session"]]


def verify_campaign(root: Path) -> list[dict[str, Any]]:
    records = read_records(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if digest(manifest["campaign"]) != manifest["config_hash"]:
        raise ValueError("manifesto corrompido")
    for record in records:
        if (
            record["config_hash"] != manifest["config_hash"]
            or record["code_version"] != manifest["code_version"]
            or record["campaign_id"] != manifest["campaign"]["campaign_id"]
        ):
            raise ValueError("registro diverge do contrato congelado")
    verify_artifacts(root, records)
    return records


def generate_reports(
    root: Path,
    config: dict[str, Any],
    sessions: dict[str, Any],
    now: datetime,
) -> None:
    records = verify_campaign(root)
    manifest = json.loads((root / "manifest.json").read_text())
    if digest(config) != manifest["config_hash"]:
        raise ValueError("configuração solicitada diverge do manifesto")
    expected = [
        on
        for on, hours in sessions.items()
        if config["start_date"] <= on <= config["end_date"]
        and datetime.fromisoformat(hours["close"]) + timedelta(minutes=45) <= now
    ]
    write_reports(
        records, {**config, "expected_sessions": expected}, read_reviews(root), root / "reports"
    )


def run_campaign(config_path: Path, root: Path, *, code_review: bool = False) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        now = datetime.now(UTC)
        config = load_campaign(config_path)
        identity = source_identity()
        ensure_manifest(root, config, identity, now)
        records = verify_campaign(root)
        sessions = campaign_calendar(config, now)
        closed = closed_sessions(sessions, now)
        pending = pending_sessions(config, closed, records)
        if pending:
            snapshot = fetch_snapshot(config, date.fromisoformat(closed[-1]), root)
            now = datetime.now(UTC)
            for on in pending:
                record = process_session(
                    config,
                    snapshot,
                    sessions,
                    records[-1] if records else None,
                    on,
                    now,
                    identity["code_version"],
                    root,
                )
                finished_at = datetime.now(UTC)
                if any(
                    decision["action"] == "SCHEDULED"
                    and finished_at
                    >= datetime.fromisoformat(sessions[decision["execute_session"]]["open"])
                    for decision in record["decisions"]
                ):
                    raise ValueError("janela prospectiva encerrou durante o cálculo")
                if len(pending) > 1:
                    record["warnings"] = [
                        "Recuperação de sessões; nenhuma nova decisão retroativa."
                    ]
                records.append(append_record(root, record))
                run_rule_reviews(records[-1], records, root)
                run_reviews(records[-1], records, root, monthly_budget_usd=0)
        if records:
            latest = records[-1]
            run_rule_reviews(latest, records, root)
            sources = None
            if code_review:
                source = Path(__file__).resolve().parents[3]
                paths = ["src/marko/experiment/engine.py", "src/marko/experiment/market.py"]
                sources = {path: (source / path).read_text() for path in paths}
            run_reviews(latest, records, root, monthly_budget_usd=0, code_sources=sources)
        generate_reports(root, config, sessions, now)
        failures: set[str] = set()
        for record in records:
            for decision in record["decisions"]:
                if decision.get("reason") == "model_failed":
                    failures.add(decision["model_id"])
                elif decision["action"] == "SCHEDULED":
                    failures.discard(decision["model_id"])
        expected = {on for on in closed if config["start_date"] <= on <= config["end_date"]}
        observed = {r["session"] for r in records if r["status"] in {"ok", "completed"}}
        missing = sorted(expected - observed)
        missed_window = bool(
            records
            and any(d.get("reason") == "missed_decision_window" for d in records[-1]["decisions"])
        )
        reviewed_roles = {
            review["role"]
            for review in read_reviews(root)
            if records
            and review.get("record_hash") == records[-1]["record_hash"]
            and review["status"] == "completed"
            and review.get("backend") != "deterministic_rules"
        }
        health = {
            "checked_at": now.isoformat(),
            "status": "degraded" if failures or missing or missed_window else "ok",
            "last_session": records[-1]["session"] if records else None,
            "records": len(records),
            "api_budget_usd": 0,
            "completed": bool(records and records[-1]["status"] == "completed"),
            "ai_reviews": "completed"
            if {"risk", "methodology"} <= reviewed_roles
            else "pending_local_subscription_runner",
            "model_failures": sorted(failures),
            "missing_sessions": missing,
            "missed_decision_window": missed_window,
        }
        write_json(root / "health.json", health)
        return health


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimento Marko: somente capital virtual")
    parser.add_argument("command", choices=("run", "verify", "report"))
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path, required=True)
    parser.add_argument("--code-review", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "run":
            result = run_campaign(args.config, args.state_dir, code_review=args.code_review)
        else:
            records = verify_campaign(args.state_dir)
            config = load_campaign(args.config)
            manifest = json.loads((args.state_dir / "manifest.json").read_text())
            if digest(config) != manifest["config_hash"]:
                raise ValueError("configuração solicitada diverge do manifesto")
            if args.command == "report":
                now = datetime.now(UTC)
                generate_reports(args.state_dir, config, campaign_calendar(config, now), now)
            result = {"status": "verified", "records": len(records)}
        print(json.dumps(result, sort_keys=True))
        return 1 if result["status"] == "degraded" else 0
    except Exception as error:
        # Não persistir mensagens do provedor: podem carregar URLs e credenciais.
        health = {
            "status": "blocked",
            "checked_at": datetime.now(UTC).isoformat(),
            "error_type": type(error).__name__,
            "error_code": operational_error_code(error),
            "api_budget_usd": 0,
        }
        write_json(args.state_dir / "health.json", health)
        print(json.dumps(health))
        return 1


def operational_error_code(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        return "source_checkout_unavailable"
    if isinstance(error, FileNotFoundError):
        return "required_artifact_missing"
    known = {
        "checkout limpo": "source_checkout_dirty",
        "campanha congelada": "frozen_contract_changed",
        "manifesto": "manifest_integrity",
        "corrompido": "artifact_integrity",
        "cadeia histórica": "record_chain_integrity",
        "split": "split_reconciliation_required",
        "45 minutos": "waiting_for_market_publication",
        "janela prospectiva": "decision_window_expired",
        "encerrada antes": "registration_after_campaign_end",
        "sessão": "market_session_unavailable",
    }
    return next(
        (code for fragment, code in known.items() if fragment in str(error)), "operation_failed"
    )


if __name__ == "__main__":
    raise SystemExit(main())
