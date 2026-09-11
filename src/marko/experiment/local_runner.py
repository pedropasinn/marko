"""Orquestra somente pareceres pela assinatura local; não gera decisões."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from marko.experiment.local_reviews import run_local_reviews
from marko.experiment.runner import verify_campaign
from marko.experiment.store import write_json


def review_latest(root: Path) -> dict[str, Any]:
    now = datetime.now(UTC)
    records = verify_campaign(root)
    if not records:
        return {"status": "pending_observation", "checked_at": now.isoformat()}
    manifest = json.loads((root / "manifest.json").read_text())
    if now.date() > datetime.fromisoformat(manifest["campaign"]["end_date"]).date() + timedelta(
        days=7
    ):
        return {"status": "campaign_closed", "checked_at": now.isoformat()}
    sources = None
    if now.weekday() in (4, 5):
        source = Path(__file__).resolve().parents[3]
        names = ["src/marko/experiment/engine.py", "src/marko/experiment/market.py"]
        sources = {name: (source / name).read_text() for name in names}
    reviews = run_local_reviews(records[-1], records, root, code_sources=sources)
    return {
        "status": "completed" if all(r["status"] == "completed" for r in reviews) else "pending",
        "checked_at": now.isoformat(),
        "session": records[-1]["session"],
        "record_hash": records[-1]["record_hash"],
        "api_cost_usd": 0,
        "roles": {r["role"]: r["status"] for r in reviews},
        "backend": "codex_subscription",
        "decisions_modified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Pareceres pela assinatura Codex, sem API paga")
    parser.add_argument("--state-dir", required=True, type=Path)
    root = parser.parse_args().state_dir
    try:
        result = review_latest(root)
    except Exception as error:
        result = {
            "status": "pending",
            "error_type": type(error).__name__,
            "checked_at": datetime.now(UTC).isoformat(),
            "api_cost_usd": 0,
        }
    write_json(root / "local-health.json", result)
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] in {"completed", "campaign_closed"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
