from __future__ import annotations

import numpy as np
import pandas as pd

from metrics import calculate_performance_metrics
from pairs_trading_core import (
    PairsResearchResult,
    build_research_result,
    build_walk_forward_boundaries,
    count_mean_crossings,
    generate_stateful_signal,
    prepare_pair_data,
    run_weighted_pair_backtest,
)


def _relationship_break_series(
    trading: pd.DataFrame,
    spread: pd.Series,
    formation_spread_mean: float,
    formation_spread_std: float,
    recent_window: int,
    maximum_recent_volatility_ratio: float,
    maximum_recent_mean_shift_z: float,
    minimum_recent_return_correlation: float,
) -> pd.DataFrame:
    if recent_window < 5:
        raise ValueError("Relationship-break window must be at least 5 days.")

    rolling_std = spread.rolling(
        recent_window,
        min_periods=recent_window,
    ).std(ddof=1)
    rolling_mean = spread.rolling(
        recent_window,
        min_periods=recent_window,
    ).mean()
    rolling_corr = (
        trading["return_a"]
        .rolling(recent_window, min_periods=recent_window)
        .corr(trading["return_b"])
    )

    volatility_ratio = rolling_std / formation_spread_std
    mean_shift_z = (rolling_mean - formation_spread_mean).abs() / formation_spread_std

    broken = (
        volatility_ratio.gt(maximum_recent_volatility_ratio)
        | mean_shift_z.gt(maximum_recent_mean_shift_z)
        | rolling_corr.lt(minimum_recent_return_correlation)
    ).fillna(False)

    return pd.DataFrame(
        {
            "recent_spread_std": rolling_std,
            "recent_spread_volatility_ratio": volatility_ratio,
            "recent_abs_mean_shift_z": mean_shift_z,
            "recent_return_correlation": rolling_corr,
            "relationship_broken": broken.astype(bool),
        },
        index=trading.index,
    )


def build_distance_pairs_research(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
    formation_years: int = 2,
    trading_months: int = 6,
    entry_zscore: float = 2.0,
    exit_zscore: float = 0.0,
    stop_zscore: float = 4.0,
    maximum_holding_days: int = 60,
    relationship_break_window: int = 20,
    maximum_recent_volatility_ratio: float = 2.0,
    maximum_recent_mean_shift_z: float = 2.5,
    minimum_recent_return_correlation: float = 0.0,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    risk_free_rate: float = 0.0,
    cash_rate: float = 0.0,
    borrow_fee: float = 0.0,
) -> PairsResearchResult:
    pair = prepare_pair_data(ticker_a, ticker_b, start_date, end_date)
    boundaries = build_walk_forward_boundaries(
        pair,
        formation_years,
        trading_months,
    )

    if not boundaries:
        raise ValueError("History is too short for the requested windows.")

    parts: list[pd.DataFrame] = []
    rows: list[dict[str, object]] = []
    previous_spread_std = float("nan")
    previous_distance_score = float("nan")

    for fold, (
        formation_start,
        formation_end,
        trading_start,
        trading_end,
    ) in enumerate(boundaries, start=1):
        formation = pair.loc[formation_start:formation_end].copy()
        trading = pair.loc[trading_start:trading_end].copy()

        base_a = float(formation["price_a"].iloc[0])
        base_b = float(formation["price_b"].iloc[0])
        norm_form_a = formation["price_a"].astype(float) / base_a
        norm_form_b = formation["price_b"].astype(float) / base_b
        formation_spread = norm_form_a - norm_form_b

        spread_mean = float(formation_spread.mean())
        spread_std = float(formation_spread.std(ddof=1))
        if not np.isfinite(spread_std) or spread_std <= 0:
            raise ValueError("Formation spread has no usable variation.")

        distance_score = float(
            np.mean(np.square(formation_spread.to_numpy(dtype=float)))
        )
        mean_crossings = count_mean_crossings(formation_spread, spread_mean)

        normalized_a = trading["price_a"].astype(float) / base_a
        normalized_b = trading["price_b"].astype(float) / base_b
        spread = normalized_a - normalized_b
        zscore = (spread - spread_mean) / spread_std

        # Warm the rolling filter on the end of the formation window so the
        # first weeks of each trading window are monitored too.
        context = pd.concat(
            [formation.iloc[-(relationship_break_window - 1):], trading]
        )
        context_spread = pd.concat(
            [formation_spread.iloc[-(relationship_break_window - 1):], spread]
        )
        stability = _relationship_break_series(
            trading=context,
            spread=context_spread,
            formation_spread_mean=spread_mean,
            formation_spread_std=spread_std,
            recent_window=relationship_break_window,
            maximum_recent_volatility_ratio=maximum_recent_volatility_ratio,
            maximum_recent_mean_shift_z=maximum_recent_mean_shift_z,
            minimum_recent_return_correlation=minimum_recent_return_correlation,
        ).loc[trading.index]

        signals = generate_stateful_signal(
            zscore=zscore,
            entry_zscore=entry_zscore,
            exit_zscore=exit_zscore,
            stop_zscore=stop_zscore,
            maximum_holding_days=maximum_holding_days,
            relationship_broken=stability["relationship_broken"],
        )

        method_data = trading.copy()
        method_data["normalized_a"] = normalized_a
        method_data["normalized_b"] = normalized_b
        method_data["spread"] = spread
        method_data["spread_zscore"] = zscore
        method_data["pair_signal"] = signals["pair_signal"]
        method_data["exit_reason"] = signals["exit_reason"]
        method_data["fold"] = fold
        for column in stability.columns:
            method_data[column] = stability[column]

        desired_a = 0.5 * method_data["pair_signal"]
        desired_b = -0.5 * method_data["pair_signal"]

        tested = run_weighted_pair_backtest(
            method_data,
            desired_a,
            desired_b,
            initial_capital,
            transaction_cost_bps,
            True,
            cash_rate=cash_rate,
            borrow_fee=borrow_fee,
        )

        fold_metrics = calculate_performance_metrics(
            returns=tested["strategy_return"],
            equity=tested["strategy_equity"],
            risk_free_rate=risk_free_rate,
            initial_value=initial_capital,
        )
        trades = int(
            (
                tested["pair_position"].ne(0)
                & tested["pair_position"].shift(1).fillna(0).eq(0)
            ).sum()
        )

        rows.append(
            {
                "fold": fold,
                "formation_start": formation_start,
                "formation_end": formation_end,
                "trading_start": trading_start,
                "trading_end": trading_end,
                "distance_score": distance_score,
                "spread_std": spread_std,
                "spread_std_vs_previous": (
                    spread_std / previous_spread_std
                    if np.isfinite(previous_spread_std) and previous_spread_std > 0
                    else np.nan
                ),
                "distance_score_vs_previous": (
                    distance_score / previous_distance_score
                    if np.isfinite(previous_distance_score) and previous_distance_score > 0
                    else np.nan
                ),
                "mean_crossings": mean_crossings,
                "relationship_break_days": int(
                    stability["relationship_broken"].sum()
                ),
                "max_recent_volatility_ratio": float(
                    stability["recent_spread_volatility_ratio"].max(skipna=True)
                ),
                "max_recent_mean_shift_z": float(
                    stability["recent_abs_mean_shift_z"].max(skipna=True)
                ),
                "trades": trades,
                "turnover": float(tested["turnover"].sum()),
                "test_return": fold_metrics["total_return"],
                "test_sharpe": fold_metrics["sharpe_ratio"],
            }
        )

        previous_spread_std = spread_std
        previous_distance_score = distance_score

        parts.append(
            tested[
                [
                    "price_a",
                    "price_b",
                    "return_a",
                    "return_b",
                    "normalized_a",
                    "normalized_b",
                    "spread",
                    "spread_zscore",
                    "pair_signal",
                    "pair_position",
                    "exit_reason",
                    "weight_a",
                    "weight_b",
                    "turnover",
                    "gross_strategy_return",
                    "transaction_cost",
                    "strategy_return",
                    "fold",
                    "recent_spread_volatility_ratio",
                    "recent_abs_mean_shift_z",
                    "recent_return_correlation",
                    "relationship_broken",
                ]
            ].copy()
        )

    return build_research_result(
        "Distance + Relationship-Break Filter",
        ticker_a,
        ticker_b,
        pair,
        parts,
        pd.DataFrame(rows),
        initial_capital,
        transaction_cost_bps,
        risk_free_rate,
    )
