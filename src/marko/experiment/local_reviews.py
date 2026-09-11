"""Revisões locais pela assinatura existente; não usa chaves de API ou broker."""

from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from marko.experiment.reviews import (
    MAX_INPUT_BYTES,
    MAX_RESPONSE_BYTES,
    REVIEW_SCHEMA,
    _digest,
    _instructions,
    _json,
    _parse_response,
    _record_payload,
)
from marko.experiment.store import write_json

LOCAL_VERSION = "codex-subscription-review-v1"
DISABLED_FEATURES = (
    "shell_tool",
    "unified_exec",
    "code_mode_host",
    "apps",
    "plugins",
    "hooks",
    "multi_agent",
    "browser_use",
    "computer_use",
    "image_generation",
    "view_image",
    "memories",
    "skill_search",
    "sleep_tool",
    "goals",
    "skill_mcp_dependency_install",
    "remote_plugin",
    "recommended_plugins",
    "shell_snapshot",
)


def _environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "DBUS_SESSION_BUS_ADDRESS",
        "CODEX_HOME",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
    }
    return {key: value for key, value in os.environ.items() if key in allowed}


def _command(executable: str, directory: Path) -> list[str]:
    command = [executable, "exec", "--ignore-user-config", "--ignore-rules", "--ephemeral"]
    for feature in DISABLED_FEATURES:
        command.extend(["--disable", feature])
    return [
        *command,
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "-C",
        str(directory),
        "-c",
        'web_search="disabled"',
        "-c",
        'approval_policy="never"',
        "-c",
        'forced_login_method="chatgpt"',
        "--output-schema",
        str(directory / "schema.json"),
        "--output-last-message",
        str(directory / "result.json"),
        "--json",
        "-",
    ]


def _invoke(prompt: str) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    executable = shutil.which("codex")
    if executable is None:
        return None, {"status": "pending_local_cli", "reason": "codex_not_installed"}
    environment = _environment()
    try:
        login = subprocess.run(
            [executable, "login", "status"],
            env=environment,
            capture_output=True,
            timeout=15,
            check=False,
        )
        if login.returncode or b"Logged in using ChatGPT" not in login.stdout + login.stderr:
            return None, {"status": "pending_local_login", "reason": "chatgpt_login_required"}
        version = (
            subprocess.run(
                [executable, "--version"],
                env=environment,
                capture_output=True,
                timeout=15,
                check=False,
            )
            .stdout.decode(errors="replace")
            .strip()[:80]
        )
        with tempfile.TemporaryDirectory(prefix="marko-local-review-") as name:
            directory = Path(name)
            (directory / "schema.json").write_text(_json(REVIEW_SCHEMA), encoding="utf-8")
            with (directory / "process.log").open("wb") as log:
                process = subprocess.Popen(
                    _command(executable, directory),
                    stdin=subprocess.PIPE,
                    stdout=log,
                    stderr=log,
                    env=environment,
                    start_new_session=True,
                )
                try:
                    process.communicate(prompt.encode(), timeout=120)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=10)
                    return None, {"status": "pending_local_retry", "reason": "timeout_120s"}
            log_path = directory / "process.log"
            if log_path.stat().st_size > 1_000_000:
                return None, {"status": "pending_local_retry", "reason": "output_limit"}
            raw_log = log_path.read_text(errors="replace")
            if process.returncode:
                quota = any(
                    word in raw_log.lower()
                    for word in (
                        "usage limit",
                        "rate limit",
                        "quota",
                        "insufficient_quota",
                    )
                )
                return None, {
                    "status": "pending_local_quota" if quota else "pending_local_retry",
                    "reason": "subscription_limit" if quota else "codex_process_failed",
                }
            events = []
            for line in raw_log.splitlines():
                if line.startswith("{"):
                    events.append(json.loads(line))
            tool_events = {
                "command_execution",
                "file_change",
                "mcp_tool_call",
                "web_search",
                "collab_tool_call",
                "tool_call",
                "function_call",
            }
            used_tools = any(event.get("item", {}).get("type") in tool_events for event in events)
            if used_tools:
                return None, {"status": "pending_local_retry", "reason": "unexpected_tool_use"}
            output = directory / "result.json"
            if not output.exists() or output.stat().st_size > MAX_RESPONSE_BYTES:
                return None, {"status": "pending_local_retry", "reason": "invalid_output"}
            result = _parse_response(
                {
                    "status": "completed",
                    "output": [
                        {
                            "type": "message",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": output.read_text(encoding="utf-8"),
                                }
                            ],
                        }
                    ],
                }
            )
            usage: dict[str, Any] = next(
                (
                    event.get("usage", {})
                    for event in reversed(events)
                    if event.get("type") == "turn.completed"
                ),
                {},
            )
            return result, {
                "status": "completed",
                "cli_version": version,
                "usage": {
                    key: value
                    for key, value in usage.items()
                    if key in {"input_tokens", "output_tokens", "cached_input_tokens"}
                    and isinstance(value, int)
                },
                "tools_used": False,
            }
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return None, {"status": "pending_local_retry", "reason": "local_review_failed"}


def _run_local_reviews(
    record: dict[str, Any],
    history: list[dict[str, Any]],
    state_dir: Path,
    code_sources: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    current = _record_payload(record)
    prior = [
        _record_payload(row)
        for row in history[-10:]
        if row.get("record_hash") != record["record_hash"]
    ]
    if any(
        row["campaign_id"] != current["campaign_id"] or row["session"] > current["session"]
        for row in prior
    ):
        raise ValueError("Histórico local incompatível com a sessão")
    for previous_record in prior:
        previous_record.pop("portfolios", None)
        previous_record.pop("actions", None)
    if code_sources is not None:
        for name, source in code_sources.items():
            path = PurePosixPath(name)
            if (
                path.is_absolute()
                or ".." in path.parts
                or path.suffix != ".py"
                or (not name.startswith(("src/marko/", "tests/")) or not isinstance(source, str))
            ):
                raise ValueError("Fonte fora do escopo da revisão local")
    local_dir = state_dir / "reviews" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    roles = ["risk", "methodology"] + (["code"] if code_sources else [])
    results = []
    for role in roles:
        evidence = {"record": current, "history": prior, "history_total_records": len(history)}
        if role == "code":
            evidence["code_sources"] = code_sources
        while prior and len(_json(evidence).encode()) > MAX_INPUT_BYTES:
            prior.pop(0)
        if len(_json(evidence).encode()) > MAX_INPUT_BYTES:
            raise ValueError("Payload local excede limite")
        input_hash = _digest(evidence)
        review_id = _digest({"role": role, "input_hash": input_hash, "version": LOCAL_VERSION})
        now = datetime.now(UTC)
        final_path = local_dir / f"{review_id}.json"
        attempt_path = local_dir / f"{review_id}-{now:%Y%m%d}.json"
        previous_path = final_path if final_path.exists() else attempt_path
        if previous_path.exists():
            results.append(json.loads(previous_path.read_text()))
            continue
        prompt = (
            _instructions(role) + " Você está em sessão local da assinatura ChatGPT. "
            "Não chame ferramenta alguma, mesmo se o runtime as disponibilizar. "
            "Não leia arquivos nem execute comandos; todas as evidências estão neste prompt. "
            "Não modifique ledger, decisões, arquivos ou código. Não emita ordens. "
            "O sandbox é read-only; isto não constitui isolamento absoluto de ferramentas. "
            "Não acesse rede. Retorne apenas o JSON no schema solicitado.\nEVIDÊNCIAS:\n"
            + _json(evidence)
        )
        result, metadata = _invoke(prompt)
        row: dict[str, Any] = {
            "review_id": review_id,
            "campaign_id": current["campaign_id"],
            "session": current["session"],
            "record_hash": current["record_hash"],
            "code_version": current["code_version"],
            "input_hash": input_hash,
            "role": role,
            "model": "codex-default-subscription",
            "backend": "codex_subscription",
            "created_at": now.isoformat(),
            "authority": "advisory_only",
            "api_cost_usd": "0",
            "prompt_version": LOCAL_VERSION,
            "isolation": "read_only_sandbox_not_absolute_tool_isolation",
            **metadata,
        }
        if result is not None:
            row["result"] = result
        destination = final_path if row["status"] == "completed" else attempt_path
        write_json(destination, row, immutable=True)
        results.append(row)
    return results


def run_local_reviews(
    record: dict[str, Any],
    history: list[dict[str, Any]],
    state_dir: Path,
    code_sources: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    state_dir.mkdir(parents=True, exist_ok=True)
    with (state_dir / "local-reviews.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return _run_local_reviews(record, history, state_dir, code_sources)
