from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from itertools import combinations
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from backtester import download_data
from metrics import calculate_performance_metrics


METHOD_DISTANCE = "Distance-Based"
METHOD_COINTEGRATION = "Cointegration Walk-Forward"
METHOD_DYNAMIC = "Dynamic Kalman Hedge Ratio"


@dataclass
class PairsResearchResult:
    method_name: str
    ticker_a: str
    ticker_b: str
    stitched_data: pd.DataFrame
    diagnostics: pd.DataFrame
    trades: pd.DataFrame
    strategy_metrics: dict[str, float]
    benchmark_metrics: dict[str, float]
    full_sample_return_correlation: float
    full_sample_price_correlation: float


@lru_cache(maxsize=64)
def _prepare_pair_data_cached(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    data_a = download_data(ticker_a, start_date, end_date)
    data_b = download_data(ticker_b, start_date, end_date)

    pair = pd.DataFrame(
        {
            "price_a": data_a["Close"],
            "price_b": data_b["Close"],
        }
    ).dropna()

    if pair.empty:
        raise ValueError("No overlapping historical observations were found.")
    if (pair[["price_a", "price_b"]] <= 0).any().any():
        raise ValueError("Pairs trading requires strictly positive prices.")

    pair["log_price_a"] = np.log(pair["price_a"].astype(float))
    pair["log_price_b"] = np.log(pair["price_b"].astype(float))
    pair["return_a"] = pair["price_a"].pct_change()
    pair["return_b"] = pair["price_b"].pct_change()
    return pair


def prepare_pair_data(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    ticker_a = ticker_a.upper().strip()
    ticker_b = ticker_b.upper().strip()

    if not ticker_a or not ticker_b:
        raise ValueError("Both tickers must be provided.")
    if ticker_a == ticker_b:
        raise ValueError("Pairs trading requires two different tickers.")

    # Return a defensive copy so callers can add research columns without
    # mutating the cached market-data frame used by later sensitivity runs.
    return _prepare_pair_data_cached(
        ticker_a,
        ticker_b,
        start_date,
        end_date,
    ).copy(deep=True)


def prepare_universe_data(
    tickers: Sequence[str],
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    cleaned = []
    seen = set()
    for ticker in tickers:
        name = ticker.upper().strip()
        if name and name not in seen:
            cleaned.append(name)
            seen.add(name)

    if len(cleaned) < 2:
        raise ValueError("Pair discovery needs at least two distinct tickers.")

    output: dict[str, pd.DataFrame] = {}
    for ticker in cleaned:
        data = download_data(ticker, start_date, end_date)
        if data is None or data.empty:
            continue
        frame = pd.DataFrame({"price": data["Close"]}).dropna()
        if frame.empty or (frame["price"] <= 0).any():
            continue
        frame["log_price"] = np.log(frame["price"].astype(float))
        frame["return"] = frame["price"].pct_change()
        output[ticker] = frame

    if len(output) < 2:
        raise ValueError("Fewer than two usable tickers were downloaded.")

    return output


def iter_universe_pairs(
    universe: dict[str, pd.DataFrame],
) -> Iterable[tuple[str, str, pd.DataFrame]]:
    for ticker_a, ticker_b in combinations(sorted(universe), 2):
        joined = pd.concat(
            [
                universe[ticker_a].rename(
                    columns={
                        "price": "price_a",
                        "log_price": "log_price_a",
                        "return": "return_a",
                    }
                ),
                universe[ticker_b].rename(
                    columns={
                        "price": "price_b",
                        "log_price": "log_price_b",
                        "return": "return_b",
                    }
                ),
            ],
            axis=1,
            join="inner",
        ).dropna(subset=["price_a", "price_b"])

        if len(joined) >= 60:
            yield ticker_a, ticker_b, joined


def fit_ols(y: pd.Series, x: pd.Series) -> tuple[float, float]:
    x_values = x.to_numpy(dtype=float)
    y_values = y.to_numpy(dtype=float)
    design = np.column_stack([np.ones(len(x_values)), x_values])
    coef, _, _, _ = np.linalg.lstsq(design, y_values, rcond=None)
    return float(coef[0]), float(coef[1])


def count_mean_crossings(spread: pd.Series, mean: float) -> int:
    centered = spread.astype(float) - float(mean)
    signs = pd.Series(
        np.sign(centered.to_numpy(dtype=float)),
        index=centered.index,
        dtype=float,
    ).replace(0.0, np.nan).ffill()

    crossings = (
        signs.ne(signs.shift(1))
        & signs.notna()
        & signs.shift(1).notna()
    )
    return int(crossings.sum())


def generate_stateful_signal(
    zscore: pd.Series,
    entry_zscore: float,
    exit_zscore: float,
    stop_zscore: float,
    maximum_holding_days: int,
    tradable: pd.Series | None = None,
    relationship_broken: pd.Series | None = None,
) -> pd.DataFrame:
    if entry_zscore <= 0:
        raise ValueError("Entry z-score must be positive.")
    if exit_zscore < 0 or exit_zscore >= entry_zscore:
        raise ValueError("Exit z-score must be non-negative and below entry.")
    if stop_zscore <= entry_zscore:
        raise ValueError("Stop z-score must exceed entry z-score.")
    if maximum_holding_days < 1:
        raise ValueError("Maximum holding days must be at least 1.")

    index = zscore.index
    if tradable is None:
        tradable = pd.Series(True, index=index, dtype=bool)
    else:
        tradable = tradable.reindex(index).fillna(False).astype(bool)

    if relationship_broken is None:
        relationship_broken = pd.Series(False, index=index, dtype=bool)
    else:
        relationship_broken = (
            relationship_broken.reindex(index).fillna(False).astype(bool)
        )

    states: list[int] = []
    reasons: list[str] = []
    state = 0
    holding_days = 0
    cooldown = False

    for value, can_trade, broken in zip(
        zscore.to_numpy(dtype=float),
        tradable.to_numpy(dtype=bool),
        relationship_broken.to_numpy(dtype=bool),
    ):
        reason = ""

        if broken:
            if state != 0:
                reason = "relationship_break"
            state = 0
            holding_days = 0
            cooldown = True

        elif not can_trade or not np.isfinite(value):
            if state != 0:
                reason = "relationship_unavailable"
            state = 0
            holding_days = 0
            cooldown = False

        elif state == 0:
            if cooldown and abs(value) < entry_zscore:
                cooldown = False

            # A deviation already at the stop level is not an entry: it
            # would be stopped out on the very next observation.
            if not cooldown and abs(value) < stop_zscore:
                if value <= -entry_zscore:
                    state = 1
                    holding_days = 0
                elif value >= entry_zscore:
                    state = -1
                    holding_days = 0

        else:
            holding_days += 1
            converged = (
                (state == 1 and value >= -exit_zscore)
                or (state == -1 and value <= exit_zscore)
            )
            stopped = (
                (state == 1 and value <= -stop_zscore)
                or (state == -1 and value >= stop_zscore)
            )
            timed_out = holding_days >= maximum_holding_days

            if converged:
                state = 0
                holding_days = 0
                reason = "convergence"
            elif stopped:
                state = 0
                holding_days = 0
                cooldown = True
                reason = "zscore_stop"
            elif timed_out:
                state = 0
                holding_days = 0
                cooldown = True
                reason = "time_stop"

        states.append(state)
        reasons.append(reason)

    return pd.DataFrame(
        {
            "pair_signal": pd.Series(states, index=index, dtype=float),
            "exit_reason": pd.Series(reasons, index=index, dtype="object"),
        },
        index=index,
    )


def run_weighted_pair_backtest(
    data: pd.DataFrame,
    desired_weight_a: pd.Series,
    desired_weight_b: pd.Series,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    liquidate_at_end: bool = True,
    cash_rate: float = 0.0,
    borrow_fee: float = 0.0,
) -> pd.DataFrame:
    """
    Backtest daily target weights on two assets, executed one day later.

    Capital not used to buy the long leg earns cash_rate. Short proceeds are
    treated as posted collateral that earns nothing, and the short leg pays
    borrow_fee, both as annual rates.
    """
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")
    if transaction_cost_bps < 0:
        raise ValueError("Transaction costs cannot be negative.")

    result = data.copy()

    target_a = (
        desired_weight_a.reindex(result.index)
        .astype(float)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )
    target_b = (
        desired_weight_b.reindex(result.index)
        .astype(float)
        .replace([np.inf, -np.inf], np.nan)
        .fillna(0.0)
    )

    result["target_weight_a"] = target_a
    result["target_weight_b"] = target_b
    result["weight_a"] = target_a.shift(1).fillna(0.0)
    result["weight_b"] = target_b.shift(1).fillna(0.0)

    if "pair_signal" in result.columns:
        result["pair_position"] = (
            result["pair_signal"].astype(float).shift(1).fillna(0.0)
        )
    else:
        result["pair_position"] = 0.0

    previous_a = result["weight_a"].shift(1).fillna(0.0)
    previous_b = result["weight_b"].shift(1).fillna(0.0)

    result["turnover"] = (
        (result["weight_a"] - previous_a).abs()
        + (result["weight_b"] - previous_b).abs()
    )

    cost_rate = transaction_cost_bps / 10_000
    long_notional = (
        result["weight_a"].clip(lower=0.0) + result["weight_b"].clip(lower=0.0)
    )
    short_notional = (
        -result["weight_a"].clip(upper=0.0) - result["weight_b"].clip(upper=0.0)
    )
    daily_cash_rate = (1 + cash_rate) ** (1 / 252) - 1
    daily_borrow_fee = (1 + borrow_fee) ** (1 / 252) - 1
    elapsed = result["return_a"].notna() & result["return_b"].notna()
    result["carry_return"] = (
        (1.0 - long_notional).clip(lower=0.0) * daily_cash_rate
        - short_notional * daily_borrow_fee
    ).where(elapsed, 0.0)
    result["gross_strategy_return"] = (
        result["weight_a"] * result["return_a"].fillna(0.0)
        + result["weight_b"] * result["return_b"].fillna(0.0)
        + result["carry_return"]
    )
    result["transaction_cost"] = result["turnover"] * cost_rate

    if liquidate_at_end and not result.empty:
        last = len(result) - 1
        wa = result["weight_a"].to_numpy(dtype=float, copy=False)
        wb = result["weight_b"].to_numpy(dtype=float, copy=False)
        liquidation = abs(wa[last]) + abs(wb[last])
        if liquidation > 0:
            turnover = result["turnover"].to_numpy(dtype=float, copy=True)
            costs = result["transaction_cost"].to_numpy(dtype=float, copy=True)
            turnover[last] += liquidation
            costs[last] += liquidation * cost_rate
            result["turnover"] = turnover
            result["transaction_cost"] = costs

    result["strategy_return"] = (
        result["gross_strategy_return"] - result["transaction_cost"]
    )
    result["strategy_equity"] = (
        initial_capital
        * (1.0 + result["strategy_return"].fillna(0.0)).cumprod()
    )
    result["gross_exposure"] = (
        result["weight_a"].abs() + result["weight_b"].abs()
    )
    result["net_exposure"] = result["weight_a"] + result["weight_b"]
    result["strategy_peak"] = (
        result["strategy_equity"].cummax().clip(lower=initial_capital)
    )
    result["strategy_drawdown"] = (
        result["strategy_equity"] / result["strategy_peak"] - 1.0
    )
    return result


def extract_trades(
    data: pd.DataFrame,
    ticker_a: str,
    ticker_b: str,
) -> pd.DataFrame:
    if data.empty or "pair_position" not in data.columns:
        return pd.DataFrame()

    position = data["pair_position"].astype(float)
    previous = position.shift(1).fillna(0.0)
    entry_locs = [
        int(location)
        for location in np.flatnonzero(
            (position.ne(0) & previous.eq(0)).to_numpy()
        )
    ]

    rows: list[dict[str, object]] = []
    for entry_loc in entry_locs:
        direction = float(position.iloc[entry_loc])
        exit_loc = entry_loc + 1
        while exit_loc < len(data) and float(position.iloc[exit_loc]) == direction:
            exit_loc += 1

        last_held_loc = min(exit_loc - 1, len(data) - 1)
        segment = data.iloc[entry_loc : last_held_loc + 1]
        if segment.empty:
            continue

        signal_loc = max(entry_loc - 1, 0)
        signal_date = data.index[signal_loc]
        entry_date = data.index[entry_loc]
        exit_date = data.index[min(exit_loc, len(data) - 1)]

        weight_a = float(segment["weight_a"].iloc[0])
        weight_b = float(segment["weight_b"].iloc[0])

        long_asset = ticker_a if weight_a > 0 else ticker_b
        short_asset = ticker_b if weight_b < 0 else ticker_a

        leg_a = float((segment["weight_a"] * segment["return_a"].fillna(0.0)).sum())
        leg_b = float((segment["weight_b"] * segment["return_b"].fillna(0.0)).sum())
        gross = float(segment["gross_strategy_return"].sum())
        cost = float(segment["transaction_cost"].sum())

        # The closing trade is booked on the first flat row, so its cost
        # belongs to this trade rather than to the idle period after it.
        if exit_loc < len(data):
            cost += float(data["transaction_cost"].iloc[exit_loc])
        net = gross - cost

        # Signals are recorded one row before the position changes, so the
        # reason for leaving sits on the last held row. A held row without a
        # reason means the position was liquidated at a trading-window end.
        if exit_loc >= len(data):
            exit_reason = "end_of_sample"
        else:
            exit_reason = "window_end"
            if "exit_reason" in data.columns:
                candidate = str(data["exit_reason"].iloc[exit_loc - 1])
                if candidate:
                    exit_reason = candidate

        entry_z = float(data["spread_zscore"].iloc[signal_loc])
        max_abs_z = float(
            data["spread_zscore"].iloc[signal_loc : last_held_loc + 1].abs().max()
        )

        rows.append(
            {
                "signal_date": signal_date,
                "entry_date": entry_date,
                "exit_date": exit_date,
                "direction": "Long spread" if direction > 0 else "Short spread",
                "long_asset": long_asset,
                "short_asset": short_asset,
                "entry_zscore": entry_z,
                "holding_days": int(last_held_loc - entry_loc + 1),
                "exit_reason": exit_reason,
                "long_leg_contribution": leg_a if weight_a > 0 else leg_b,
                "short_leg_contribution": leg_b if weight_b < 0 else leg_a,
                "gross_pair_return": gross,
                "transaction_cost": cost,
                "net_pair_return": net,
                "maximum_abs_zscore": max_abs_z,
            }
        )

    return pd.DataFrame(rows)


def add_continuous_equal_weight_benchmark(
    data: pd.DataFrame,
    initial_capital: float,
    transaction_cost_bps: float,
) -> pd.DataFrame:
    result = data.copy()
    cost_rate = transaction_cost_bps / 10_000

    result["benchmark_turnover"] = 0.0
    if not result.empty:
        values = np.zeros(len(result), dtype=float)
        values[0] = 1.0
        result["benchmark_turnover"] = values

    result["benchmark_transaction_cost"] = (
        result["benchmark_turnover"] * cost_rate
    )
    result["benchmark_return"] = (
        0.5 * result["return_a"].fillna(0.0)
        + 0.5 * result["return_b"].fillna(0.0)
        - result["benchmark_transaction_cost"]
    )
    result["benchmark_equity"] = (
        initial_capital * (1.0 + result["benchmark_return"]).cumprod()
    )
    result["benchmark_peak"] = (
        result["benchmark_equity"].cummax().clip(lower=initial_capital)
    )
    result["benchmark_drawdown"] = (
        result["benchmark_equity"] / result["benchmark_peak"] - 1.0
    )
    return result


def build_research_result(
    method_name: str,
    ticker_a: str,
    ticker_b: str,
    full_pair_data: pd.DataFrame,
    strategy_parts: Sequence[pd.DataFrame],
    diagnostics: pd.DataFrame,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
) -> PairsResearchResult:
    if not strategy_parts:
        raise ValueError("No strategy observations were produced.")

    stitched = pd.concat(list(strategy_parts)).sort_index()
    stitched = stitched[~stitched.index.duplicated(keep="first")].copy()

    stitched["strategy_equity"] = (
        initial_capital
        * (1.0 + stitched["strategy_return"].fillna(0.0)).cumprod()
    )
    stitched["strategy_peak"] = (
        stitched["strategy_equity"].cummax().clip(lower=initial_capital)
    )
    stitched["strategy_drawdown"] = (
        stitched["strategy_equity"] / stitched["strategy_peak"] - 1.0
    )
    stitched = add_continuous_equal_weight_benchmark(
        stitched,
        initial_capital,
        transaction_cost_bps,
    )

    strategy_metrics = calculate_performance_metrics(
        returns=stitched["strategy_return"],
        equity=stitched["strategy_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )
    benchmark_metrics = calculate_performance_metrics(
        returns=stitched["benchmark_return"],
        equity=stitched["benchmark_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    return_corr = (
        full_pair_data[["return_a", "return_b"]]
        .dropna()
        .corr()
        .to_numpy(dtype=float)
    )
    price_corr = (
        full_pair_data[["price_a", "price_b"]]
        .dropna()
        .corr()
        .to_numpy(dtype=float)
    )

    trades = extract_trades(stitched, ticker_a, ticker_b)

    return PairsResearchResult(
        method_name=method_name,
        ticker_a=ticker_a.upper().strip(),
        ticker_b=ticker_b.upper().strip(),
        stitched_data=stitched,
        diagnostics=diagnostics,
        trades=trades,
        strategy_metrics=strategy_metrics,
        benchmark_metrics=benchmark_metrics,
        full_sample_return_correlation=float(return_corr[0, 1]),
        full_sample_price_correlation=float(price_corr[0, 1]),
    )


def build_walk_forward_boundaries(
    data: pd.DataFrame,
    formation_years: int,
    trading_months: int,
) -> list[tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, pd.Timestamp]]:
    if formation_years < 1:
        raise ValueError("Formation window must be at least one year.")
    if trading_months < 1:
        raise ValueError("Trading window must be at least one month.")

    index = pd.DatetimeIndex(data.index)
    if len(index) == 0:
        return []

    trading_start = _first_on_or_after(
        index,
        pd.Timestamp(index[0]) + pd.DateOffset(years=formation_years),
    )
    boundaries = []

    while trading_start is not None:
        formation_start = _first_on_or_after(
            index,
            trading_start - pd.DateOffset(years=formation_years),
        )
        formation_end = _last_before(index, trading_start)
        trading_end = _last_on_or_before(
            index,
            trading_start
            + pd.DateOffset(months=trading_months)
            - pd.Timedelta(days=1),
        )

        if (
            formation_start is None
            or formation_end is None
            or trading_end is None
            or trading_end < trading_start
        ):
            break

        boundaries.append(
            (formation_start, formation_end, trading_start, trading_end)
        )

        next_start = _first_on_or_after(
            index,
            trading_start + pd.DateOffset(months=trading_months),
        )
        if next_start is None or next_start <= trading_start:
            break
        trading_start = next_start

    return boundaries


def _first_on_or_after(
    index: pd.DatetimeIndex,
    timestamp: pd.Timestamp,
) -> pd.Timestamp | None:
    eligible = index[index >= timestamp]
    return None if len(eligible) == 0 else pd.Timestamp(eligible[0])


def _last_before(
    index: pd.DatetimeIndex,
    timestamp: pd.Timestamp,
) -> pd.Timestamp | None:
    eligible = index[index < timestamp]
    return None if len(eligible) == 0 else pd.Timestamp(eligible[-1])


def _last_on_or_before(
    index: pd.DatetimeIndex,
    timestamp: pd.Timestamp,
) -> pd.Timestamp | None:
    eligible = index[index <= timestamp]
    return None if len(eligible) == 0 else pd.Timestamp(eligible[-1])
