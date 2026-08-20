from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from pathlib import Path

from marko.case_config import load_case
from marko.data_gateway import BcbSgsProvider, SeriesQuery, SidraProvider
from marko.temporal import Observation


def main() -> None:
    parser = argparse.ArgumentParser(prog="marko")
    commands = parser.add_subparsers(dest="command", required=True)

    status = commands.add_parser("status", help="valida a configuração do caso pessoal")
    status.add_argument("--case", type=Path, default=Path("config/personal-case.toml"))

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

    arguments = parser.parse_args()
    if arguments.command == "status":
        case = load_case(arguments.case)
        issues = case.readiness_issues()
        _print({"ready": not issues, "issues": issues})
    elif arguments.command == "fetch-bcb":
        query = SeriesQuery(
            arguments.series,
            arguments.start,
            arguments.end,
            (("unit", arguments.unit),),
        )
        _print_observations(BcbSgsProvider().fetch(query, datetime.now(UTC)))
    else:
        query = SeriesQuery(
            arguments.series,
            parameters=(
                ("table", arguments.table),
                ("variable", arguments.variable),
                ("period", arguments.period),
            ),
        )
        _print_observations(SidraProvider().fetch(query, datetime.now(UTC)))


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
    main()
