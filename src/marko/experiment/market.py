from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any

from marko.experiment.config import digest
from marko.experiment.store import write_json


def schedule(start: date, end: date) -> dict[str, dict[str, str]]:
    import pandas_market_calendars as calendars

    frame = calendars.get_calendar("NYSE").schedule(start_date=start, end_date=end)
    return {
        str(index.date()): {
            "open": row["market_open"].isoformat(),
            "close": row["market_close"].isoformat(),
        }
        for index, row in frame.iterrows()
    }


def fetch_snapshot(
    config: dict[str, Any],
    session: date,
    root: Path,
) -> dict[str, Any]:
    import yfinance as yf

    requested_at = datetime.now(UTC)
    recent = schedule(requested_at.date() - timedelta(days=14), requested_at.date())
    eligible = [
        on
        for on, times in recent.items()
        if datetime.fromisoformat(times["close"]) + timedelta(minutes=45) <= requested_at
    ]
    if not eligible or session.isoformat() != max(eligible):
        raise ValueError("snapshot precisa da última sessão concluída há pelo menos 45 minutos")
    if any(
        datetime.fromisoformat(times["open"])
        <= requested_at
        < datetime.fromisoformat(times["close"]) + timedelta(minutes=45)
        for times in recent.values()
    ):
        raise ValueError(
            "aguarde fechamento e publicação para evitar preços históricos reajustados"
        )
    # O cache do fornecedor é operacional; o snapshot canônico abaixo é imutável.
    yf.set_tz_cache_location(str(root / "provider-cache"))
    start = session - timedelta(days=config["training_sessions"] * 2 + 30)
    frame = yf.download(
        config["symbols"],
        start=start.isoformat(),
        end=(session + timedelta(days=1)).isoformat(),
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        back_adjust=False,
        actions=True,
        repair=False,
        keepna=True,
        threads=False,
        progress=False,
        timeout=25,
    )
    if frame is None or frame.empty:
        raise ValueError("provider não retornou dados")
    bars: dict[str, dict[str, dict[str, str]]] = {}
    for symbol in config["symbols"]:
        data = frame[symbol]
        bars[symbol] = {}
        for index, row in data.iterrows():
            on = str(index.date())
            if on > session.isoformat():
                continue
            values = {
                "open": row["Open"],
                "close": row["Close"],
                "adjusted_close": row["Adj Close"],
                "dividend": row.get("Dividends", 0),
                "split": row.get("Stock Splits", 0),
            }
            parsed = {key: Decimal(str(value)) for key, value in values.items()}
            if any(not value.is_finite() for value in parsed.values()):
                continue
            if any(parsed[key] <= 0 for key in ("open", "close", "adjusted_close")):
                continue
            if parsed["dividend"] < 0 or parsed["split"] < 0:
                raise ValueError(f"evento corporativo inválido em {symbol}")
            bars[symbol][on] = {key: str(value) for key, value in parsed.items()}
        if session.isoformat() not in bars[symbol]:
            raise ValueError(f"cotação ausente para {symbol} na sessão esperada")
    observed_at = datetime.now(UTC).isoformat()
    payload = {
        "provider": "Yahoo Finance / yfinance",
        "session": session.isoformat(),
        "observed_at": observed_at,
        "bars": bars,
    }
    payload["data_hash"] = digest(payload)
    write_json(root / "snapshots" / f"{payload['data_hash']}.json", payload, immutable=True)
    return payload


def training_returns(
    snapshot: dict[str, Any], symbols: list[str], count: int
) -> tuple[tuple[float, ...], ...]:
    bars = snapshot["bars"]
    common = sorted(set.intersection(*(set(bars[symbol]) for symbol in symbols)))
    common = [on for on in common if on <= snapshot["session"]]
    if len(common) < count + 1:
        raise ValueError("histórico comum insuficiente")
    common = common[-count - 1 :]
    expected = sorted(schedule(date.fromisoformat(common[0]), date.fromisoformat(common[-1])))
    if common != expected:
        raise ValueError("histórico de treino possui sessões ausentes")
    result = []
    for previous, current in pairwise(common):
        result.append(
            tuple(
                float(
                    Decimal(bars[symbol][current]["adjusted_close"])
                    / Decimal(bars[symbol][previous]["adjusted_close"])
                    - 1
                )
                for symbol in symbols
            )
        )
    return tuple(result)
