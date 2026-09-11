"""Relatórios derivados das evidências; carteiras alternativas nunca são somadas."""

from __future__ import annotations

import csv
import html
import io
import os
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return html.escape(str(value)).replace("|", "\\|").replace("\n", " ")


def _money(value: Any) -> str:
    number = Decimal(str(value))
    return f"{number:,.2f}"


def _week(session: str) -> str:
    year, week, _ = date.fromisoformat(session).isocalendar()
    return f"{year}-W{week:02d}"


def _latest_metrics(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in records:
        if row["status"] in {"ok", "completed"}:
            for metric in row.get("metrics", []):
                latest[metric["model_id"]] = metric | {"session": row["session"]}
    return latest


def render_report(
    records: list[dict[str, Any]],
    campaign: dict[str, Any],
    reviews: list[dict[str, Any]],
    *,
    period_start: str | None = None,
) -> str:
    ordered = sorted(records, key=lambda row: (row["session"], row.get("observed_at", "")))
    campaign_id = campaign.get("campaign_id", campaign.get("id", "não informado"))
    if any(row["campaign_id"] != campaign_id for row in ordered):
        raise ValueError("Relatório não pode misturar campanhas")
    initial = Decimal(str(campaign.get("initial_capital_usd", "10000")))
    if not initial.is_finite() or initial <= 0:
        raise ValueError("Capital inicial inválido")
    lines = [
        f"# Marko — {_text(campaign_id)}",
        "",
        f"Período previsto: {_text(campaign.get('start_date', campaign.get('start', '—')))} "
        f"a {_text(campaign.get('end_date', campaign.get('end', '—')))}.",
        "",
        f"Cada modelo representa uma alternativa independente de US$ {_money(initial)}, "
        "sem aportes. Os patrimônios não são somados. Capital real não foi movimentado.",
        "",
    ]
    if not ordered:
        return "\n".join([*lines, "Sem sessões registradas; desempenho ainda indisponível.", ""])
    latest = ordered[-1]
    cutoff = latest["session"]
    start = (
        period_start
        or (
            date.fromisoformat(cutoff) - timedelta(days=date.fromisoformat(cutoff).weekday())
        ).isoformat()
    )
    period_rows = [row for row in ordered if row["session"] >= start]
    counts = Counter(row["status"] for row in period_rows)
    lines += [
        f"Última sessão registrada: {_text(cutoff)}. Estado: {_text(latest['status'])}.",
        "",
        f"Janela semanal: {_text(start)} a {_text(cutoff)}. "
        f"Sessões válidas: {counts['ok']}; bloqueadas: {counts['blocked']}; "
        f"preflight: {counts['preflight']}; encerramento: {counts['completed']}.",
        "",
    ]
    metrics = _latest_metrics(ordered)
    before = _latest_metrics([row for row in ordered if row["session"] < start])
    if metrics:
        lines += [
            "| Modelo | Última marca | Patrimônio USD | P&L acumulado USD | Retorno acumulado | "
            "Retorno semanal | Drawdown máximo | Custos acumulados USD |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        for model, metric in sorted(metrics.items()):
            nav = Decimal(str(metric["nav_usd"]))
            baseline = Decimal(str(before.get(model, {}).get("nav_usd", initial)))
            weekly = (nav / baseline - 1) * 100 if baseline > 0 else None
            weekly_text = f"{weekly:+.2f}%" if weekly is not None else "indisponível"
            if metric["session"] < start:
                weekly_text = "sem marca na semana"
            lines.append(
                f"| {_text(model)} | {_text(metric['session'])} | {_money(nav)} | "
                f"{_money(metric['pnl_usd'])} | {float(metric['return_pct']):+.2f}% | "
                f"{weekly_text} | {float(metric['drawdown_pct']):.2f}% | "
                f"{_money(metric['costs_usd'])} |"
            )
        lines += [
            "",
            "Retorno semanal usa a última marca válida anterior à semana; "
            "na primeira semana, usa o capital inicial. Drawdown é a magnitude positiva "
            "da queda máxima. Custos de negociação já integram o P&L; custo de API é "
            "operacional, apresentado separadamente. Retornos não são anualizados.",
            "",
        ]
    else:
        lines += ["Desempenho prospectivo indisponível: não há marca válida de carteira.", ""]
    expected = campaign.get("expected_sessions")
    if expected is not None:
        observed = {row["session"] for row in ordered if row["status"] in {"ok", "completed"}}
        expected_until = max([cutoff, *expected])
        missing = sorted(
            session
            for session in expected
            if start <= session <= expected_until and session not in observed
        )
        lines += [
            f"Avaliação consultada até {_text(expected_until)}; última marca registrada em "
            f"{_text(cutoff)}.",
            "",
            "Sessões esperadas sem execução válida: "
            + (", ".join(map(_text, missing)) if missing else "nenhuma nesta janela."),
            "",
        ]
    else:
        lines += [
            "Calendário de sessões esperado não fornecido; lacunas não foram inferidas "
            "a partir de dias úteis genéricos.",
            "",
        ]
    problems = [row for row in period_rows if row["status"] in {"blocked", "preflight"}]
    if problems:
        lines += ["## Bloqueios e preparação", ""]
        for row in problems:
            lines.append(
                f"- {_text(row['session'])}: {_text(row['status'])}; "
                f"{_text(row.get('reason', row.get('warnings', 'sem motivo detalhado')))}."
            )
        lines.append("")
    relevant_reviews = [
        row
        for row in reviews
        if row.get("campaign_id") == campaign_id and start <= row["session"] <= cutoff
    ]
    completed = [row for row in relevant_reviews if row["status"] == "completed"]
    rules = [row for row in completed if row.get("backend") == "deterministic_rules"]
    completed_ai = [row for row in completed if row.get("backend") != "deterministic_rules"]
    local_completed = {
        (row["role"], row.get("record_hash"))
        for row in completed_ai
        if row.get("backend") == "codex_subscription" and row.get("record_hash")
    }
    disabled_api = [row for row in relevant_reviews if row["status"] == "pending_budget"]
    pending = [
        row
        for row in relevant_reviews
        if row["status"] != "completed"
        and not (
            row["status"] == "pending_budget"
            and (row["role"], row.get("record_hash")) in local_completed
        )
    ]
    costs = sum(
        (Decimal(row.get("estimated_cost_usd", "0")) for row in relevant_reviews), Decimal(0)
    )
    lines += [
        "## Avaliações independentes",
        "",
        f"Pareceres concluídos: {len(completed_ai)} por IA. "
        f"Verificações por regras concluídas: {len(rules)} (não são IA). "
        f"Pendentes ou falhos: {len(pending)}. "
        f"Revisões por API desativadas: {len(disabled_api)}. "
        f"Custo estimado pela utilização reportada nesta janela: US$ {costs:.6f}.",
        "",
        "As chamadas têm contextos separados; usar o mesmo provedor não garante "
        "independência estatística. Revisões geram propostas, sem alterar decisões, "
        "ledger ou a versão congelada do experimento.",
        "",
    ]
    if not relevant_reviews:
        lines += ["Nenhuma avaliação de LLM registrada nesta janela.", ""]
    if any(row.get("backend") == "codex_subscription" for row in relevant_reviews):
        lines += [
            "Revisões locais usam a assinatura ChatGPT já existente, sem chamadas pagas à API. "
            "Estão sujeitas à disponibilidade da máquina, autenticação e cotas da assinatura. "
            "O sandbox de somente leitura não é isolamento absoluto de ferramentas.",
            "",
        ]
    for row in relevant_reviews:
        status_label = "API desativada" if row["status"] == "pending_budget" else row["status"]
        lines.append(
            f"- {_text(row['session'])} / {_text(row['role'])} / "
            f"{_text(row.get('model', '—'))}: {_text(status_label)}."
        )
        result = row.get("result")
        if result:
            lines.append(f"  {_text(result['verdict'])}: {_text(result['summary'])}")
            for finding in result.get("findings", []):
                lines.append(
                    f"  Evidência ({_text(finding['severity'])}): "
                    f"{_text(finding['evidence'])}. Proposta: "
                    f"{_text(finding['recommendation'])}. Teste proposto: "
                    f"{_text(finding['proposed_test'])}."
                )
            if result.get("limitations"):
                lines.append("  Limitações: " + "; ".join(map(_text, result["limitations"])))
    if any(row["status"] == "pending_credentials" for row in pending):
        lines += [
            "",
            "Avaliação por agentes pendente de credencial de API; "
            "não foi apresentada como executada.",
        ]
    if disabled_api:
        lines += [
            "",
            "Avaliação por API não executada: orçamento ausente ou política de custo zero. "
            "Verificações locais por regras continuam sem chamadas pagas.",
        ]
    lines += [
        "",
        "## Evidência",
        "",
        f"Código: `{_text(latest.get('code_version', '—'))}`. "
        f"Configuração: `{_text(latest.get('config_hash', '—'))}`.",
        "",
        f"Último registro: `{_text(latest.get('record_hash', '—'))}`. "
        f"Corte de conhecimento: {_text(latest.get('knowledge_cutoff', '—'))}.",
        "",
        "Resultado de simulação prospectiva condicionado à fonte, custos e regras registrados; "
        "não equivale a lucro realizado nem comprova desempenho futuro.",
        "",
    ]
    return "\n".join(lines)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def write_reports(
    records: list[dict[str, Any]],
    campaign: dict[str, Any],
    reviews: list[dict[str, Any]],
    output_dir: Path,
) -> list[Path]:
    ordered = sorted(records, key=lambda row: (row["session"], row.get("observed_at", "")))
    reports: dict[Path, str] = {
        output_dir / "current.md": render_report(ordered, campaign, reviews)
    }
    sessions = sorted({row["session"] for row in ordered})
    for session in sessions:
        subset = [row for row in ordered if row["session"] <= session]
        historical_campaign = campaign | (
            {"expected_sessions": [day for day in campaign["expected_sessions"] if day <= session]}
            if "expected_sessions" in campaign
            else {}
        )
        reports[output_dir / "daily" / f"{session}.md"] = render_report(
            subset, historical_campaign, reviews
        )
    for week in sorted({_week(session) for session in sessions}):
        last = max(session for session in sessions if _week(session) == week)
        historical_campaign = campaign | (
            {"expected_sessions": [day for day in campaign["expected_sessions"] if day <= last]}
            if "expected_sessions" in campaign
            else {}
        )
        reports[output_dir / "weekly" / f"{week}.md"] = render_report(
            [row for row in ordered if row["session"] <= last], historical_campaign, reviews
        )
    buffer = io.StringIO(newline="")
    columns = [
        "session",
        "status",
        "model_id",
        "nav_usd",
        "pnl_usd",
        "return_pct",
        "drawdown_pct",
        "costs_usd",
        "record_hash",
    ]
    writer = csv.DictWriter(buffer, fieldnames=columns)
    writer.writeheader()
    for row in ordered:
        if row["status"] not in {"ok", "completed"}:
            continue
        for metric in row.get("metrics", []):
            values = {key: metric.get(key, row.get(key, "")) for key in columns}
            for key in ("model_id", "record_hash"):
                if str(values[key]).startswith(("=", "+", "-", "@")):
                    values[key] = "'" + str(values[key])
            writer.writerow(values)
    reports[output_dir / "performance.csv"] = buffer.getvalue()
    for path, content in reports.items():
        _write(path, content)
    return list(reports)
