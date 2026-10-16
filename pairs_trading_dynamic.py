from __future__ import annotations

import numpy as np
import pandas as pd

from metrics import calculate_performance_metrics
from pairs_trading_core import (
    PairsResearchResult,
    build_research_result,
    fit_ols,
    generate_stateful_signal,
    prepare_pair_data,
    run_weighted_pair_backtest,
)


def calculate_kalman_relationship(
    data: pd.DataFrame,
    warmup_window: int = 120,
    state_noise: float = 1e-5,
    observation_noise_scale: float = 1.0,
    zscore_window: int = 60,
) -> pd.DataFrame:
    """
    Track log(A) = alpha + beta * log(B) with a random-walk Kalman filter.

    The regressor is centred on its warmup mean. With raw log prices
    (x of roughly 4-6) alpha and beta are almost perfectly collinear, and the
    state uncertainty is multiplied by x**2 inside the innovation variance,
    which inflated it several-fold and kept |z| far below typical entry
    levels. After centring, alpha is the fitted level at the warmup average
    of log(B) and the two states are close to uncorrelated.

    The trading z-score scales each innovation by the standard deviation of
    the preceding ``zscore_window`` innovations, so it is calibrated to the
    spread's realised behaviour rather than to the assumed observation noise.
    The model-implied innovation standard deviation is kept as a diagnostic.
    """
    if warmup_window < 20:
        raise ValueError("Kalman warmup must be at least 20 observations.")
    if state_noise <= 0:
        raise ValueError("State noise must be positive.")
    if observation_noise_scale <= 0:
        raise ValueError("Observation-noise scale must be positive.")
    if zscore_window < 10:
        raise ValueError("Z-score window must be at least 10 observations.")
    if len(data) <= warmup_window:
        raise ValueError("History is too short for the Kalman warmup window.")

    result = data.copy()
    y = result["log_price_a"].to_numpy(dtype=float)
    x_raw = result["log_price_b"].to_numpy(dtype=float)
    x_center = float(np.mean(x_raw[:warmup_window]))
    x = x_raw - x_center

    alpha0, beta0 = fit_ols(
        pd.Series(y[:warmup_window]),
        pd.Series(x[:warmup_window]),
    )
    residual0 = y[:warmup_window] - alpha0 - beta0 * x[:warmup_window]
    residual_variance = float(np.var(residual0, ddof=2))
    if not np.isfinite(residual_variance) or residual_variance <= 0:
        residual_variance = 1e-6

    observation_variance = residual_variance * observation_noise_scale
    theta = np.array([alpha0, beta0], dtype=float)

    # Start from the OLS coefficient covariance instead of an arbitrary prior.
    design = np.column_stack([np.ones(warmup_window), x[:warmup_window]])
    covariance = np.linalg.pinv(design.T @ design) * residual_variance
    process_covariance = np.eye(2, dtype=float) * state_noise

    n = len(result)
    alpha_values = np.full(n, np.nan, dtype=float)
    beta_values = np.full(n, np.nan, dtype=float)
    innovation_values = np.full(n, np.nan, dtype=float)
    model_std_values = np.full(n, np.nan, dtype=float)

    for row in range(warmup_window, n):
        prior_theta = theta
        prior_covariance = covariance + process_covariance
        observation_vector = np.array([1.0, x[row]], dtype=float)

        innovation = float(y[row] - observation_vector @ prior_theta)
        innovation_variance = float(
            observation_vector @ prior_covariance @ observation_vector
            + observation_variance
        )

        if not np.isfinite(innovation_variance) or innovation_variance <= 0:
            continue

        # Record the state used to predict this row before updating on it.
        alpha_values[row] = prior_theta[0]
        beta_values[row] = prior_theta[1]
        innovation_values[row] = innovation
        model_std_values[row] = np.sqrt(innovation_variance)

        kalman_gain = prior_covariance @ observation_vector / innovation_variance
        theta = prior_theta + kalman_gain * innovation
        covariance = (
            np.eye(2) - np.outer(kalman_gain, observation_vector)
        ) @ prior_covariance

    innovations = pd.Series(innovation_values, index=result.index)
    # Only past innovations enter the scale, so today's shock cannot shrink
    # its own z-score.
    trailing_std = (
        innovations.rolling(zscore_window, min_periods=zscore_window)
        .std(ddof=1)
        .shift(1)
    )

    result["dynamic_alpha"] = alpha_values
    result["dynamic_beta"] = beta_values
    result["spread"] = innovations
    result["spread_std"] = trailing_std
    result["model_innovation_std"] = model_std_values
    result["spread_zscore"] = innovations / trailing_std.where(trailing_std > 0)
    return result


def build_dynamic_pairs_research(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
    warmup_window: int = 120,
    state_noise: float = 1e-5,
    observation_noise_scale: float = 1.0,
    zscore_window: int = 60,
    entry_zscore: float = 2.0,
    exit_zscore: float = 0.0,
    stop_zscore: float = 4.0,
    maximum_holding_days: int = 60,
    minimum_hedge_ratio: float = 0.25,
    maximum_hedge_ratio: float = 4.0,
    rehedge_daily: bool = False,
    trading_start: str | None = None,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    risk_free_rate: float = 0.0,
    cash_rate: float = 0.0,
    borrow_fee: float = 0.0,
) -> PairsResearchResult:
    if maximum_hedge_ratio <= minimum_hedge_ratio:
        raise ValueError("Maximum hedge ratio must exceed the minimum.")

    pair = prepare_pair_data(ticker_a, ticker_b, start_date, end_date)
    modeled = calculate_kalman_relationship(
        data=pair,
        warmup_window=warmup_window,
        state_noise=state_noise,
        observation_noise_scale=observation_noise_scale,
        zscore_window=zscore_window,
    )
    # The z-score needs a full window of innovations after the warmup.
    evaluation = modeled.iloc[warmup_window:].copy()

    # The filter still learns from earlier data; trading only begins here
    # (for example after a pair-selection window).
    if trading_start is not None:
        evaluation = evaluation.loc[evaluation.index >= pd.Timestamp(trading_start)]
        if evaluation.empty:
            raise ValueError("No observations remain after the trading start.")

    valid = (
        evaluation["dynamic_beta"].notna()
        & evaluation["spread_zscore"].notna()
        & evaluation["dynamic_beta"].between(
            minimum_hedge_ratio,
            maximum_hedge_ratio,
            inclusive="both",
        )
    )

    signals = generate_stateful_signal(
        zscore=evaluation["spread_zscore"],
        entry_zscore=entry_zscore,
        exit_zscore=exit_zscore,
        stop_zscore=stop_zscore,
        maximum_holding_days=maximum_holding_days,
        tradable=valid,
    )

    evaluation["pair_signal"] = signals["pair_signal"]
    evaluation["exit_reason"] = signals["exit_reason"]

    beta = evaluation["dynamic_beta"].astype(float)
    if not rehedge_daily:
        # Lock the hedge ratio in when a trade opens. Re-hedging every day to
        # the latest beta turns over both legs constantly, and on real pairs
        # that cost consumed most of the method's gross edge.
        signal = evaluation["pair_signal"]
        opened = signal.ne(0) & signal.shift(1, fill_value=0.0).eq(0)
        beta = beta.where(opened).ffill().where(signal.ne(0), beta)
    evaluation["hedge_beta"] = beta
    denominator = 1.0 + beta.abs()
    desired_a = (evaluation["pair_signal"] / denominator).where(valid, 0.0)
    desired_b = (
        -evaluation["pair_signal"] * beta / denominator
    ).where(valid, 0.0)

    tested = run_weighted_pair_backtest(
        evaluation,
        desired_a,
        desired_b,
        initial_capital,
        transaction_cost_bps,
        True,
        cash_rate=cash_rate,
        borrow_fee=borrow_fee,
    )

    metrics = calculate_performance_metrics(
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

    beta_values = tested.loc[valid, "dynamic_beta"].dropna().to_numpy(dtype=float)
    diagnostics = pd.DataFrame(
        [
            {
                "evaluation_start": tested.index[0],
                "evaluation_end": tested.index[-1],
                "warmup_window": warmup_window,
                "state_noise": state_noise,
                "observation_noise_scale": observation_noise_scale,
                "zscore_window": zscore_window,
                "valid_relationship_share": float(valid.mean()),
                "median_beta": (
                    float(np.median(beta_values)) if len(beta_values) else np.nan
                ),
                "minimum_beta": (
                    float(np.min(beta_values)) if len(beta_values) else np.nan
                ),
                "maximum_beta": (
                    float(np.max(beta_values)) if len(beta_values) else np.nan
                ),
                "trades": trades,
                "turnover": float(tested["turnover"].sum()),
                "test_return": metrics["total_return"],
                "test_sharpe": metrics["sharpe_ratio"],
            }
        ]
    )

    return build_research_result(
        "Dynamic Kalman Hedge Ratio",
        ticker_a,
        ticker_b,
        pair,
        [
            tested[
                [
                    "price_a",
                    "price_b",
                    "return_a",
                    "return_b",
                    "dynamic_alpha",
                    "dynamic_beta",
                    "hedge_beta",
                    "spread",
                    "spread_std",
                    "model_innovation_std",
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
                ]
            ].copy()
        ],
        diagnostics,
        initial_capital,
        transaction_cost_bps,
        risk_free_rate,
    )
