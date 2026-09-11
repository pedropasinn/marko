from __future__ import annotations

import hashlib
import json
import re
import tomllib
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any


def digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode()).hexdigest()


def load_campaign(path: Path) -> dict[str, Any]:
    with path.open("rb") as stream:
        config = tomllib.load(stream)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", config["campaign_id"]):
        raise ValueError("campaign_id inválido")
    start, end = date.fromisoformat(config["start_date"]), date.fromisoformat(config["end_date"])
    if not start < end or (end - start).days > 200:
        raise ValueError("campanha precisa de intervalo positivo de até 200 dias")
    if config["real_capital"] is not False or config["currency"] != "USD":
        raise ValueError("experimento só admite USD virtual")
    if Decimal(config["initial_capital_usd"]) != Decimal("10000"):
        raise ValueError("esta campanha exige US$ 10000 por modelo")
    symbols = config["symbols"]
    if not symbols or len(set(symbols)) != len(symbols) or len(symbols) > 12:
        raise ValueError("universo inválido")
    if any(not re.fullmatch(r"[A-Z]{1,6}", symbol) for symbol in symbols):
        raise ValueError("símbolo inválido")
    if not {"SPY", "IEF"}.issubset(symbols):
        raise ValueError("benchmarks exigem SPY e IEF no universo")
    allowed = {"equal_weight", "minimum_variance", "risk_budgeting", "hrp", "cvar"}
    if not config["models"] or not set(config["models"]).issubset(allowed):
        raise ValueError("modelo desconhecido")
    if config["benchmarks"] != ["cash", "spy_buy_hold", "sixty_forty"]:
        raise ValueError("benchmarks precisam permanecer explícitos")
    if len(set(config["models"])) != len(config["models"]):
        raise ValueError("modelo duplicado")
    if not 0 < config["maximum_weight"] <= 1 or len(symbols) * config["maximum_weight"] < 1:
        raise ValueError("limite de peso inviável")
    if not 30 <= config["training_sessions"] <= 756:
        raise ValueError("janela de treino inválida")
    cost = Decimal(config["transaction_cost_bps"])
    if not cost.is_finite() or not 0 <= cost <= 100:
        raise ValueError("custo inválido")
    if (config["calendar"], config["rebalance"], config["dividend_policy"]) != (
        "NYSE",
        "month_end",
        "receivable_not_reinvested",
    ):
        raise ValueError("convenção não suportada")
    return config
