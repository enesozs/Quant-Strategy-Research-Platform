"""
Out-of-sample portfolio of pairs selected by discovery.

A single pair's backtest says little: whether it worked is mostly luck of the
pair. The honest question is whether the *selection process* works. This
module ranks a universe on the opening formation window only, takes the top N
pairs, trades each of them strictly after that window, and combines them into
one equally weighted portfolio.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from metrics import calculate_performance_metrics
from pairs_trading_cointegration import build_cointegration_pairs_research
from pairs_trading_core import (
    METHOD_COINTEGRATION,
    METHOD_DISTANCE,
    METHOD_DYNAMIC,
    PairsResearchResult,
)
from pairs_trading_discovery import discover_pairs
from pairs_trading_distance import build_distance_pairs_research
from pairs_trading_dynamic import build_dynamic_pairs_research


@dataclass
class PairsPortfolioResult:
    method_name: str
    selection_start: pd.Timestamp
    selection_end: pd.Timestamp
    discovery: pd.DataFrame
    pair_summary: pd.DataFrame
    pair_results: dict[str, PairsResearchResult]
    portfolio: pd.DataFrame
    portfolio_metrics: dict[str, float]
    average_pair_correlation: float


def _research_pair(
    method: str,
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
    selection_end: pd.Timestamp,
    method_kwargs: dict[str, Any],
) -> PairsResearchResult:
    if method == METHOD_DISTANCE:
        return build_distance_pairs_research(
            ticker_a, ticker_b, start_date, end_date, **method_kwargs
        )
    if method == METHOD_COINTEGRATION:
        return build_cointegration_pairs_research(
            ticker_a, ticker_b, start_date, end_date, **method_kwargs
        )
    if method == METHOD_DYNAMIC:
        return build_dynamic_pairs_research(
            ticker_a,
            ticker_b,
            start_date,
            end_date,
            trading_start=selection_end.isoformat(),
            **method_kwargs,
        )
    raise ValueError(f"Unknown pairs method: {method}")


def build_pairs_portfolio(
    tickers: list[str],
    start_date: str,
    end_date: str,
    method: str,
    top_n: int = 5,
    formation_years: int = 2,
    method_kwargs: dict[str, Any] | None = None,
    initial_capital: float = 10_000,
    risk_free_rate: float = 0.0,
    cash_rate: float = 0.0,
) -> PairsPortfolioResult:
    """
    Select the top pairs on the opening formation window and trade them
    out of sample as one equally weighted, daily rebalanced portfolio.

    For the walk-forward methods the first trading window starts exactly
    where the selection window ends, so formation_years is shared. method_kwargs
    may carry any other builder argument (entry/exit rules, costs, borrow fee).
    """
    if top_n < 1:
        raise ValueError("Select at least one pair.")

    method_kwargs = dict(method_kwargs or {})
    method_kwargs.setdefault("initial_capital", initial_capital)
    method_kwargs.setdefault("risk_free_rate", risk_free_rate)
    method_kwargs.setdefault("cash_rate", cash_rate)
    if method in {METHOD_DISTANCE, METHOD_COINTEGRATION}:
        method_kwargs["formation_years"] = formation_years

    selection_start = pd.Timestamp(start_date)
    selection_end = selection_start + pd.DateOffset(years=formation_years)

    discovery_kwargs: dict[str, Any] = {}
    if method == METHOD_DYNAMIC:
        for source, target in (
            ("warmup_window", "kalman_warmup_window"),
            ("state_noise", "kalman_state_noise"),
            ("observation_noise_scale", "kalman_observation_noise_scale"),
            ("zscore_window", "kalman_zscore_window"),
        ):
            if source in method_kwargs:
                discovery_kwargs[target] = method_kwargs[source]

    discovery = discover_pairs(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        method=method,
        formation_years=formation_years,
        top_n=top_n,
        **discovery_kwargs,
    )

    if discovery.empty:
        raise ValueError("Discovery found no candidate pairs to trade.")

    pair_results: dict[str, PairsResearchResult] = {}
    summary_rows: list[dict[str, object]] = []
    returns: dict[str, pd.Series] = {}

    for _, row in discovery.iterrows():
        ticker_a, ticker_b = str(row["asset_a"]), str(row["asset_b"])
        label = f"{ticker_a}/{ticker_b}"
        try:
            result = _research_pair(
                method,
                ticker_a,
                ticker_b,
                start_date,
                end_date,
                selection_end,
                method_kwargs,
            )
        except ValueError as error:
            summary_rows.append({"pair": label, "status": f"skipped: {error}"})
            continue

        pair_returns = result.stitched_data["strategy_return"].astype(float)
        pair_returns = pair_returns.loc[pair_returns.index >= selection_end]
        if pair_returns.empty:
            summary_rows.append({"pair": label, "status": "skipped: no trading days"})
            continue

        pair_results[label] = result
        returns[label] = pair_returns
        summary_rows.append(
            {
                "pair": label,
                "status": "traded",
                "trades": len(result.trades),
                "total_return": result.strategy_metrics["total_return"],
                "sharpe_ratio": result.strategy_metrics["sharpe_ratio"],
                "max_drawdown": result.strategy_metrics["max_drawdown"],
            }
        )

    if not returns:
        raise ValueError("None of the selected pairs could be traded.")

    panel = pd.DataFrame(returns).sort_index()

    # A pair with no data on a day holds its capital in cash.
    daily_cash_rate = (1 + cash_rate) ** (1 / 252) - 1
    panel = panel.fillna(daily_cash_rate)

    portfolio = pd.DataFrame(index=panel.index)
    portfolio["portfolio_return"] = panel.mean(axis=1)
    portfolio["portfolio_equity"] = (
        initial_capital * (1.0 + portfolio["portfolio_return"]).cumprod()
    )
    peak = portfolio["portfolio_equity"].cummax().clip(lower=initial_capital)
    portfolio["portfolio_drawdown"] = portfolio["portfolio_equity"] / peak - 1.0
    for label in panel.columns:
        portfolio[f"equity::{label}"] = initial_capital * (1.0 + panel[label]).cumprod()

    portfolio_metrics = calculate_performance_metrics(
        returns=portfolio["portfolio_return"],
        equity=portfolio["portfolio_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    if panel.shape[1] > 1:
        correlation = panel.corr().to_numpy(dtype=float)
        upper = correlation[np.triu_indices_from(correlation, k=1)]
        average_correlation = float(np.nanmean(upper))
    else:
        average_correlation = float("nan")

    return PairsPortfolioResult(
        method_name=method,
        selection_start=selection_start,
        selection_end=selection_end,
        discovery=discovery,
        pair_summary=pd.DataFrame(summary_rows),
        pair_results=pair_results,
        portfolio=portfolio,
        portfolio_metrics=portfolio_metrics,
        average_pair_correlation=average_correlation,
    )
