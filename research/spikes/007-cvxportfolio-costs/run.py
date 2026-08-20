import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "common"))

import cvxportfolio as cvx
import numpy as np
import pandas as pd
from harness import run


def experiment(data):
    cash = pd.Series(0.0, index=data.index, name="CASH")
    market_returns = pd.concat([data, cash], axis=1)
    policy = cvx.SinglePeriodOptimization(
        cvx.ReturnsForecast() - 2.0 * cvx.FullCovariance() - cvx.TransactionCost(a=0.0005, b=0.0),
        constraints=[cvx.LongOnly(), cvx.LeverageLimit(1)],
        solver="CLARABEL",
    )
    policy.initialize_estimator_recursive(
        universe=market_returns.columns, trading_calendar=market_returns.index
    )
    current = np.zeros(len(market_returns.columns))
    current[-1] = 1.0
    trades = (
        policy.values_in_time_recursive(
            t=market_returns.index[-1],
            current_weights=pd.Series(current, index=market_returns.columns),
            current_portfolio_value=50_000,
            past_returns=market_returns.iloc[:-1],
            past_volumes=pd.DataFrame(
                1_000_000.0, index=market_returns.index[:-1], columns=data.columns
            ),
            current_prices=pd.Series(100.0, index=data.columns),
        )
        - current
    )
    target = current + trades
    return {
        "trades": dict(zip(market_returns.columns, trades.tolist(), strict=True)),
        "target_weights": dict(zip(market_returns.columns, target.tolist(), strict=True)),
        "solver": "CLARABEL",
    }


run(
    Path(__file__).with_name("result.json"),
    ["cvxportfolio"],
    {"transaction_cost": 0.0005, "risk_aversion": 2.0},
    experiment,
)
