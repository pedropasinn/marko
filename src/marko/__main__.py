from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
from datetime import UTC, date, datetime
from pathlib import Path

from marko.case_config import load_case
from marko.data_gateway import BcbSgsProvider, SeriesQuery, SidraProvider
from marko.persistence import (
    PostgresStore,
    create_backup,
    restore_backup,
    verify_backup,
)
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

    migrate = commands.add_parser("db-migrate", help="aplica migrações PostgreSQL")
    migrate.add_argument("--dsn")

    backup = commands.add_parser("backup", help="cria backup canônico do PostgreSQL")
    backup.add_argument("output", type=Path)
    backup.add_argument("--dsn")

    backup_verify = commands.add_parser("backup-verify", help="verifica backup canônico")
    backup_verify.add_argument("input", type=Path)

    backup_restore = commands.add_parser("backup-restore", help="restaura backup idempotente")
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
        elif arguments.command == "db-migrate":
            store = _postgres_store(arguments.dsn)
            store.migrate()
            _print({"migrated": True})
        elif arguments.command == "backup":
            store = _postgres_store(arguments.dsn)
            _print(asdict(create_backup(arguments.output, store)))
        elif arguments.command == "backup-verify":
            _print(asdict(verify_backup(arguments.input)))
        elif arguments.command == "backup-restore":
            store = _postgres_store(arguments.dsn)
            store.migrate()
            _print(asdict(restore_backup(arguments.input, store)))
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
            report = reconcile_shadow_packet(
                packet,
                model_runs=store.model_runs(),
                observations=store.observations(),
                checked_at=arguments.checked_at,
            )
            report_payload = asdict(report)
            report_payload["checked_at"] = report.checked_at.isoformat()
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
