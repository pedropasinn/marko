from __future__ import annotations

import copy
import json
from datetime import datetime
from decimal import ROUND_DOWN, Decimal
from pathlib import Path
from typing import Any

import numpy as np

from marko.experiment.config import digest
from marko.experiment.market import training_returns
from marko.experiment.store import write_json
from marko.persistence.codec import encode_model_run
from marko.portfolio_lab import PortfolioModel, PortfolioProblem
from marko.research_registry import SolverRecord, execute_model_run

D = Decimal
ZERO = D(0)
QUANTUM = D("0.00000001")


def initial_portfolios(config: dict[str, Any]) -> dict[str, Any]:
    return {
        model: {
            "cash": config["initial_capital_usd"],
            "receivables": "0",
            "units": {symbol: "0" for symbol in config["symbols"]},
            "costs": "0",
            "peak": config["initial_capital_usd"],
            "max_drawdown": "0",
            "pending": None,
            "initialized": False,
        }
        for model in config["models"] + config["benchmarks"]
    }


def nav(wallet: dict[str, Any], prices: dict[str, str]) -> Decimal:
    return (
        D(wallet["cash"])
        + D(wallet["receivables"])
        + sum((D(units) * D(prices[symbol]) for symbol, units in wallet["units"].items()), ZERO)
    )


def execute_target(
    wallet: dict[str, Any],
    weights: dict[str, float],
    prices: dict[str, str],
    cost_bps: str,
    session: str,
) -> list[dict[str, str]]:
    rate = D(cost_bps) / 10000
    if not rate.is_finite() or not 0 <= rate <= D("0.01"):
        raise ValueError("taxa de execução inválida")
    if set(weights) != set(prices) or any(not np.isfinite(w) or w < 0 for w in weights.values()):
        raise ValueError("pesos de execução inválidos")
    if sum(weights.values()) > 1 + 1e-7:
        raise ValueError("alavancagem não permitida")
    prices_d = {s: D(price) for s, price in prices.items()}
    if any(not p.is_finite() or p <= 0 for p in prices_d.values()):
        raise ValueError("preço de execução inválido")
    capital = nav(wallet, prices) - D(wallet["receivables"])
    units = {s: D(q) for s, q in wallet["units"].items()}
    cash, costs = D(wallet["cash"]), D(wallet["costs"])
    if capital <= 0 or not capital.is_finite() or cash < 0 or any(q < 0 for q in units.values()):
        raise ValueError("patrimônio negociável inválido")
    target_weights = {s: D(str(w)) for s, w in weights.items()}
    weight_sum = sum(target_weights.values(), ZERO)
    if weight_sum > 1:
        target_weights = {s: w / weight_sum for s, w in target_weights.items()}
    low, high = ZERO, capital
    for _ in range(100):
        estimated_cost = (low + high) / 2
        required = rate * sum(
            (
                abs((capital - estimated_cost) * target_weights[s] - units[s] * prices_d[s])
                for s in units
            ),
            ZERO,
        )
        if estimated_cost >= required:
            high = estimated_cost
        else:
            low = estimated_cost
    if rate == 0 or all(capital * target_weights[s] == units[s] * prices_d[s] for s in units):
        high = ZERO
    investable = capital - high
    target = {
        s: (investable * target_weights[s] / p).quantize(QUANTUM, rounding=ROUND_DOWN)
        for s, p in prices_d.items()
    }
    actions = []
    for symbol in sorted(units):
        sell = max(units[symbol] - target[symbol], ZERO)
        if sell == 0:
            continue
        notional = sell * prices_d[symbol]
        fee = notional * rate
        units[symbol] -= sell
        cash += notional - fee
        costs += fee
        actions.append(
            {
                "session": session,
                "symbol": symbol,
                "side": "sell",
                "quantity": str(sell),
                "price": str(prices_d[symbol]),
                "notional_usd": str(notional),
                "cost_usd": str(fee),
            }
        )
    needed = {s: max(target[s] - units[s], ZERO) for s in units}
    for symbol in sorted(units):
        buy = needed[symbol]
        if buy == 0:
            continue
        notional = buy * prices_d[symbol]
        fee = notional * rate
        if notional + fee > cash:
            raise ValueError("execução excedeu caixa")
        cash -= notional + fee
        units[symbol] += buy
        costs += fee
        actions.append(
            {
                "session": session,
                "symbol": symbol,
                "side": "buy",
                "quantity": str(buy),
                "price": str(prices_d[symbol]),
                "notional_usd": str(notional),
                "cost_usd": str(fee),
            }
        )
    if cash < 0 or any(q < 0 for q in units.values()):
        raise ValueError("execução produziu saldo negativo")
    wallet.update(cash=str(cash), costs=str(costs), units={s: str(q) for s, q in units.items()})
    ending_capital = nav(wallet, prices) - D(wallet["receivables"])
    actual_weights = {s: units[s] * prices_d[s] / ending_capital for s in units}
    deviation = max((abs(actual_weights[s] - target_weights[s]) for s in units), default=ZERO)
    tolerance = D("0.0000001") + max(prices_d.values()) * QUANTUM / ending_capital
    if deviation > tolerance:
        raise ValueError("pesos executados divergiram dos targets pós-custos")
    wallet["execution_weights"] = {s: str(w) for s, w in actual_weights.items()}
    wallet["execution_maximum_target_deviation"] = str(deviation)
    return actions


def corporate_actions(
    wallet: dict[str, Any], bars: dict[str, Any], session: str
) -> list[dict[str, str]]:
    events = []
    for symbol, bar in bars.items():
        units = D(wallet["units"][symbol])
        split, dividend = D(bar["split"]), D(bar["dividend"])
        if split < 0 or dividend < 0:
            raise ValueError("evento corporativo negativo")
        if split not in (ZERO, D(1)):
            units *= split
            wallet["units"][symbol] = str(units)
            events.append(
                {"session": session, "symbol": symbol, "side": "split", "ratio": str(split)}
            )
        if dividend and units:
            amount = units * dividend
            wallet["receivables"] = str(D(wallet["receivables"]) + amount)
            events.append(
                {
                    "session": session,
                    "symbol": symbol,
                    "side": "dividend_receivable",
                    "amount_usd": str(amount),
                }
            )
    return events


def model_weights(
    model_id: str,
    config: dict[str, Any],
    snapshot: dict[str, Any],
    created_at: datetime,
    code_version: str,
    root: Path,
) -> tuple[dict[str, float], str | None]:
    symbols = config["symbols"]
    if model_id in config["benchmarks"]:
        weights = dict.fromkeys(symbols, 0.0)
        if model_id == "spy_buy_hold":
            weights["SPY"] = 1.0
        elif model_id == "sixty_forty":
            weights.update(SPY=0.6, IEF=0.4)
        return weights, None
    from importlib.metadata import version

    from marko.portfolio_lab import (
        EqualWeight,
        SkfolioCVaRAdapter,
        SkfolioHRPAdapter,
        SkfolioMinimumVarianceAdapter,
        SkfolioRiskBudgetingAdapter,
    )

    models: dict[str, PortfolioModel] = {
        "equal_weight": EqualWeight(),
        "minimum_variance": SkfolioMinimumVarianceAdapter(),
        "risk_budgeting": SkfolioRiskBudgetingAdapter(),
        "hrp": SkfolioHRPAdapter(),
        "cvar": SkfolioCVaRAdapter(),
    }
    returns = training_returns(snapshot, symbols, config["training_sessions"])
    problem = PortfolioProblem(
        tuple(symbols), returns, maximum_weights=(config["maximum_weight"],) * len(symbols)
    )
    solver_id = (
        "closed_form"
        if model_id == "equal_weight"
        else "scipy"
        if model_id == "hrp"
        else "CLARABEL"
    )
    solver_version = (
        "1" if model_id == "equal_weight" else version("scipy" if model_id == "hrp" else "clarabel")
    )
    run = execute_model_run(
        model=models[model_id],
        problem=problem,
        created_at=created_at,
        code_version=code_version,
        dataset_fingerprint=snapshot["data_hash"],
        policy_id=config["campaign_id"],
        policy_version=1,
        universe_id=digest(symbols),
        universe_version=1,
        parameters=(("maximum_weight", str(config["maximum_weight"])),),
        random_seed=0,
        solver=SolverRecord(solver_id, solver_version, (), (model_id,)),
    )
    if run.validated_candidate is None or run.violations:
        raise ValueError(f"candidato inválido: {model_id}")
    write_json(
        root / "model-runs" / f"{run.run_id}.json",
        json.loads(encode_model_run(run).canonical_json()),
        immutable=True,
    )
    return run.candidate.weight_map(), run.run_id


def process_session(
    config: dict[str, Any],
    snapshot: dict[str, Any],
    sessions: dict[str, Any],
    previous: dict[str, Any] | None,
    session: str,
    now: datetime,
    code_version: str,
    root: Path,
) -> dict[str, Any]:
    if now.tzinfo is None:
        raise ValueError("now exige timezone")
    if session not in sessions or snapshot["session"] not in sessions:
        raise ValueError("sessão ausente no calendário")
    close = datetime.fromisoformat(sessions[session]["close"])
    observed = datetime.fromisoformat(snapshot["observed_at"])
    snapshot_close = datetime.fromisoformat(sessions[snapshot["session"]]["close"])
    if (
        observed.tzinfo is None
        or close > observed
        or snapshot_close > observed
        or observed > now
        or snapshot["session"] < session
    ):
        raise ValueError("dados ou sessão no futuro")
    source = {k: v for k, v in snapshot.items() if k != "data_hash"}
    if digest(source) != snapshot["data_hash"]:
        raise ValueError("snapshot corrompido")
    portfolios = copy.deepcopy(previous["portfolios"]) if previous else initial_portfolios(config)
    if previous and session <= previous["session"]:
        raise ValueError("sessão duplicada ou fora de ordem")
    if previous:
        expected = next((on for on in sorted(sessions) if on > previous["session"]), None)
        if session != expected:
            raise ValueError("sessão de calendário omitida na recuperação")
        if (
            previous["config_hash"] != digest(config)
            or previous["campaign_id"] != config["campaign_id"]
        ):
            raise ValueError("configuração da campanha alterada")
    if snapshot["session"] > session and any(
        D(bar["split"]) not in (ZERO, D(1))
        for symbol in config["symbols"]
        for on, bar in snapshot["bars"][symbol].items()
        if session < on <= snapshot["session"]
    ):
        raise ValueError("recovery cruza split; preços Yahoo exigem reconciliação explícita")
    bars = {symbol: snapshot["bars"][symbol][session] for symbol in config["symbols"]}
    prices = {s: bar["close"] for s, bar in bars.items()}
    opens = {s: bar["open"] for s, bar in bars.items()}
    next_sessions = [on for on in sorted(sessions) if on > session and on <= config["end_date"]]
    next_session = next_sessions[0] if next_sessions else None
    preflight = session < config["start_date"]
    actions: list[dict[str, Any]] = []
    decisions = []
    metrics = []
    final = session >= config["start_date"] and next_session is None
    for model_id, wallet in portfolios.items():
        if not preflight:
            actions.extend(
                {"model_id": model_id, **a} for a in corporate_actions(wallet, bars, session)
            )
            pending = wallet["pending"]
            if pending and pending["execute_session"] == session:
                if (
                    digest({k: v for k, v in pending.items() if k != "decision_id"})
                    != pending["decision_id"]
                ):
                    raise ValueError("decisão pendente corrompida")
                if datetime.fromisoformat(pending["knowledge_cutoff"]) > datetime.fromisoformat(
                    pending["created_at"]
                ):
                    raise ValueError("decisão precede disponibilidade dos dados")
                if datetime.fromisoformat(pending["created_at"]) >= datetime.fromisoformat(
                    sessions[session]["open"]
                ):
                    raise ValueError("decisão não precede a abertura de execução")
                actions.extend(
                    {"model_id": model_id, "decision_id": pending["decision_id"], **a}
                    for a in execute_target(
                        wallet, pending["weights"], opens, config["transaction_cost_bps"], session
                    )
                )
                wallet["pending"] = None
                wallet["initialized"] = True
            elif pending and pending["execute_session"] < session:
                raise ValueError("sessão de execução pendente foi omitida")
        value = nav(wallet, prices)
        peak = max(D(wallet["peak"]), value)
        drawdown = max(D(wallet["max_drawdown"]), 1 - value / peak)
        wallet.update(peak=str(peak), max_drawdown=str(drawdown))
        metrics.append(
            {
                "model_id": model_id,
                "nav_usd": str(value.quantize(D("0.01"))),
                "pnl_usd": str((value - D(config["initial_capital_usd"])).quantize(D("0.01"))),
                "return_pct": float((value / D(config["initial_capital_usd"]) - 1) * 100),
                "drawdown_pct": float(drawdown * 100),
                "costs_usd": str(D(wallet["costs"]).quantize(D("0.01"))),
                "cash_usd": wallet["cash"],
                "receivables_usd": wallet["receivables"],
            }
        )
        initial = not wallet.get("initialized", False) and wallet["pending"] is None
        month_end = bool(next_session and session[:7] != next_session[:7])
        due = initial or (model_id not in config["benchmarks"] and month_end)
        # Um dia perdido pode receber valuation; nunca uma decisão retroativa.
        prospective = bool(
            next_session and now < datetime.fromisoformat(sessions[next_session]["open"])
        )
        decision: dict[str, Any] = {
            "model_id": model_id,
            "action": "NO_ACTION",
            "reason": "hold_between_rebalances",
        }
        if final:
            decision["reason"] = "campaign_completed_mark_to_market"
        elif due and not prospective:
            decision["reason"] = "missed_decision_window"
        elif due and next_session and (not preflight or next_session >= config["start_date"]):
            try:
                weights, run_id = model_weights(model_id, config, snapshot, now, code_version, root)
                run_hash = (
                    digest(json.loads((root / "model-runs" / f"{run_id}.json").read_text()))
                    if run_id
                    else None
                )
                pending = {
                    "model_id": model_id,
                    "weights": weights,
                    "model_run_id": run_id,
                    "model_run_hash": run_hash,
                    "created_at": now.isoformat(),
                    "knowledge_cutoff": snapshot["observed_at"],
                    "data_hash": snapshot["data_hash"],
                    "execute_session": next_session,
                }
                pending["decision_id"] = digest(pending)
                wallet["pending"] = pending
                decision.update(
                    action="SCHEDULED", reason="initial" if initial else "month_end", **pending
                )
            except (ValueError, RuntimeError) as error:
                decision.update(reason="model_failed", error_type=type(error).__name__)
        decisions.append(decision)
    return {
        "schema_version": 1,
        "campaign_id": config["campaign_id"],
        "session": session,
        "observed_at": now.isoformat(),
        "knowledge_cutoff": snapshot["observed_at"],
        "code_version": code_version,
        "config_hash": digest(config),
        "data_hash": snapshot["data_hash"],
        "previous_hash": previous["record_hash"] if previous else None,
        "status": "preflight" if preflight else "completed" if final else "ok",
        "metrics": metrics,
        "protocol": config,
        "valuation_prices": prices,
        "execution_prices": opens,
        "actions": actions,
        "decisions": decisions,
        "portfolios": portfolios,
        "limitations": [
            "Capital virtual; impostos pessoais excluídos.",
            "Distribuições em recebíveis, sem reinvestimento antes de verificar pagamento.",
            "Preços indicativos de abertura e custos fixos; não são fills de corretora.",
        ],
    }
