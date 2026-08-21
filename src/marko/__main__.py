from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from marko.case_config import load_case
from marko.data_gateway import (
    BcbSgsProvider,
    SeriesQuery,
    SidraProvider,
    TreasuryDirectProvider,
)
from marko.persistence import (
    PostgresStore,
    create_backup,
    restore_backup,
    verify_backup,
)
from marko.read_api.demo import DemoReadStore
from marko.shadow import MonthlyShadowSchedule, reconcile_shadow_packet
from marko.temporal import Observation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="marko")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="valida a configuração do caso pessoal")
    status.add_argument("--case", type=Path)

    bcb = commands.add_parser("fetch-bcb", help="consulta uma série BCB/SGS")
    bcb.add_argument("series")
    bcb.add_argument("--start", type=date.fromisoformat)
    bcb.add_argument("--end", type=date.fromisoformat)
    bcb.add_argument("--unit", default="provider-defined")

    sidra = commands.add_parser("fetch-sidra", help="consulta uma série IBGE/SIDRA")
    sidra.add_argument("series")
    sidra.add_argument("--table", required=True)
    sidra.add_argument("--variable", required=True)
    sidra.add_argument("--period", default="last 1")

    treasury = commands.add_parser(
        "fetch-tesouro", help="consulta o CSV oficial do Tesouro Direto"
    )
    treasury.add_argument(
        "series",
        choices=("buy_rate", "sell_rate", "buy_price", "sell_price", "base_price"),
    )
    treasury.add_argument("--start", type=date.fromisoformat)
    treasury.add_argument("--end", type=date.fromisoformat)

    migrate = commands.add_parser("db-migrate", help="aplica migrações PostgreSQL")
    migrate.add_argument("--dsn")

    seed_demo = commands.add_parser(
        "db-seed-demo", help="grava o dataset demonstrativo explicitamente sintético"
    )
    seed_demo.add_argument("--dsn")
    seed_demo.add_argument("--confirm-synthetic", action="store_true")

    backup = commands.add_parser(
        "backup",
        help="cria backup canônico; backup privado exige MARKO_BACKUP_ENCRYPTION_KEY",
        description=(
            "Cria backup canônico. Use --private com "
            "MARKO_BACKUP_ENCRYPTION_KEY em base64 para dados privados."
        ),
    )
    backup.add_argument("output", type=Path)
    backup.add_argument("--dsn")
    backup.add_argument(
        "--private",
        action="store_true",
        help="criptografa com AES-256-GCM usando MARKO_BACKUP_ENCRYPTION_KEY",
    )
    backup.add_argument("--key-id", help="identificador público da chave de criptografia")

    backup_verify = commands.add_parser(
        "backup-verify",
        help="verifica backup; backup privado exige MARKO_BACKUP_ENCRYPTION_KEY",
        description=(
            "Verifica backup canônico. Backup privado exige "
            "MARKO_BACKUP_ENCRYPTION_KEY em base64."
        ),
    )
    backup_verify.add_argument("input", type=Path)

    backup_restore = commands.add_parser(
        "backup-restore",
        help="restaura backup; backup privado exige MARKO_BACKUP_ENCRYPTION_KEY",
        description=(
            "Restaura backup idempotente. Backup privado exige "
            "MARKO_BACKUP_ENCRYPTION_KEY em base64."
        ),
    )
    backup_restore.add_argument("input", type=Path)
    backup_restore.add_argument("--dsn")

    shadow_due = commands.add_parser("shadow-due", help="calcula ciclos shadow vencidos")
    shadow_due.add_argument("--schedule-id", default="monthly")
    shadow_due.add_argument("--day", type=int, required=True)
    shadow_due.add_argument("--hour", type=int, default=9)
    shadow_due.add_argument("--minute", type=int, default=0)
    shadow_due.add_argument("--timezone", default="America/Sao_Paulo")
    shadow_due.add_argument("--after", type=datetime.fromisoformat, required=True)
    shadow_due.add_argument("--until", type=datetime.fromisoformat, required=True)

    shadow_reconcile = commands.add_parser(
        "shadow-reconcile", help="reconcilia referências PIT de um DecisionPacket"
    )
    shadow_reconcile.add_argument("packet_id")
    shadow_reconcile.add_argument("--checked-at", type=datetime.fromisoformat, required=True)
    shadow_reconcile.add_argument("--dsn")

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "status":
            case_path = _case_path(arguments.case)
            case = load_case(case_path)
            issues = case.readiness_issues()
            _print({"ready": not issues, "issues": issues, "case_path": str(case_path)})
        elif arguments.command == "fetch-bcb":
            query = SeriesQuery(
                arguments.series,
                arguments.start,
                arguments.end,
                (("unit", arguments.unit),),
            )
            _print_observations(BcbSgsProvider().fetch(query, datetime.now(UTC)))
        elif arguments.command == "fetch-sidra":
            query = SeriesQuery(
                arguments.series,
                parameters=(
                    ("table", arguments.table),
                    ("variable", arguments.variable),
                    ("period", arguments.period),
                ),
            )
            _print_observations(SidraProvider().fetch(query, datetime.now(UTC)))
        elif arguments.command == "fetch-tesouro":
            query = SeriesQuery(arguments.series, arguments.start, arguments.end)
            _print_observations(TreasuryDirectProvider().fetch(query, datetime.now(UTC)))
        elif arguments.command == "db-migrate":
            store = _postgres_store(arguments.dsn)
            store.migrate()
            _print({"migrated": True})
        elif arguments.command == "db-seed-demo":
            if not arguments.confirm_synthetic:
                raise ValueError("db-seed-demo exige --confirm-synthetic")
            store = _postgres_store(arguments.dsn)
            demo = DemoReadStore()
            store.append_activities(demo.activities())
            demo_observations = demo.observations_as_known_at(
                None, datetime.max.replace(tzinfo=UTC)
            )
            for observation in demo_observations:
                store.append_observation(observation)
            for run in demo.model_runs():
                store.append_model_run(run)
            for request in demo.shadow_run_requests():
                store.append_shadow_run_request(request)
            for packet in demo.decision_packets():
                store.append_decision_packet(packet)
            _print(
                {
                    "synthetic": True,
                    "activities": len(demo.activities()),
                    "observations": len(demo_observations),
                    "model_runs": len(demo.model_runs()),
                    "shadow_run_requests": len(demo.shadow_run_requests()),
                    "decision_packets": len(demo.decision_packets()),
                }
            )
        elif arguments.command == "backup":
            store = _postgres_store(arguments.dsn)
            encryption_key = _backup_encryption_key() if arguments.private else None
            if arguments.private and encryption_key is None:
                raise ValueError(
                    "backup privado exige MARKO_BACKUP_ENCRYPTION_KEY em base64"
                )
            _print(
                asdict(
                    create_backup(
                        arguments.output,
                        store,
                        encryption_key=encryption_key,
                        key_id=arguments.key_id,
                    )
                )
            )
        elif arguments.command == "backup-verify":
            _print(
                asdict(
                    verify_backup(
                        arguments.input,
                        encryption_key=_backup_encryption_key(),
                    )
                )
            )
        elif arguments.command == "backup-restore":
            encryption_key = _backup_encryption_key()
            verify_backup(arguments.input, encryption_key=encryption_key)
            store = _postgres_store(arguments.dsn)
            store.migrate()
            _print(
                asdict(
                    restore_backup(
                        arguments.input,
                        store,
                        encryption_key=encryption_key,
                    )
                )
            )
        elif arguments.command == "shadow-due":
            schedule = MonthlyShadowSchedule(
                arguments.schedule_id,
                arguments.day,
                arguments.hour,
                arguments.minute,
                arguments.timezone,
            )
            requests = schedule.due_between(arguments.after, arguments.until)
            _print(
                [
                    {
                        "request_id": request.request_id,
                        "schedule_id": request.schedule_id,
                        "scheduled_for": request.scheduled_for.isoformat(),
                        "knowledge_cutoff": request.knowledge_cutoff.isoformat(),
                    }
                    for request in requests
                ]
            )
        else:
            store = _postgres_store(arguments.dsn)
            packet = store.get_decision_packet(arguments.packet_id)
            if packet.shadow_request_id is None:
                raise ValueError("DecisionPacket não está ligado a um ShadowRunRequest")
            request = store.get_shadow_run_request(packet.shadow_request_id)
            report = reconcile_shadow_packet(
                packet,
                request=request,
                model_runs=store.model_runs(),
                observations=store.observations(),
                checked_at=arguments.checked_at,
            )
            report_payload = asdict(report)
            report_payload["checked_at"] = report.checked_at.isoformat()
            if report.knowledge_cutoff is not None:
                report_payload["knowledge_cutoff"] = report.knowledge_cutoff.isoformat()
            report_payload["ready"] = report.ready
            _print(report_payload)
    except (KeyError, OSError, ValueError, RuntimeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


def _case_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    configured = os.environ.get("MARKO_CASE_PATH")
    if configured:
        return Path(configured)
    local = Path("config/personal-case.local.toml")
    if local.exists():
        return local
    return Path("config/personal-case.example.toml")


def _postgres_store(explicit_dsn: str | None) -> PostgresStore:
    dsn = explicit_dsn or os.environ.get("MARKO_DATABASE_URL")
    if not dsn:
        raise ValueError("informe --dsn ou MARKO_DATABASE_URL")
    return PostgresStore(dsn)


def _backup_encryption_key() -> str | None:
    value = os.environ.get("MARKO_BACKUP_ENCRYPTION_KEY")
    return value if value and value.strip() else None


def _print_observations(observations: tuple[Observation, ...]) -> None:
    _print(
        [
            {
                "id": observation.observation_id,
                "series": observation.series_id,
                "value": str(observation.value),
                "unit": observation.unit,
                "effective_at": observation.times.effective_at.isoformat(),
                "available_at": observation.times.available_at.isoformat(),
                "vintage": observation.vintage_id,
            }
            for observation in observations
        ]
    )


def _print(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
