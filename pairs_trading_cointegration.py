from __future__ import annotations

from dataclasses import dataclass
from math import log

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, coint

from metrics import calculate_performance_metrics
from pairs_trading_core import (
    PairsResearchResult,
    build_research_result,
    build_walk_forward_boundaries,
    count_mean_crossings,
    fit_ols,
    generate_stateful_signal,
    prepare_pair_data,
    run_weighted_pair_backtest,
)


@dataclass(frozen=True)
class CointegrationDiagnostics:
    alpha: float
    beta: float
    spread_mean: float
    spread_std: float
    cointegration_pvalue: float
    adf_pvalue: float
    adf_supportive: bool
    half_life_days: float
    mean_crossings: int
    qualified: bool
    rejection_reasons: tuple[str, ...]


def _estimate_half_life(spread: pd.Series) -> float:
    clean = spread.dropna().astype(float)
    regression = pd.DataFrame(
        {
            "lagged": clean.shift(1),
            "delta": clean.diff(),
        }
    ).dropna()

    if len(regression) < 10:
        return float("inf")

    _, slope = fit_ols(regression["delta"], regression["lagged"])
    if slope >= 0:
        return float("inf")

    value = -log(2.0) / slope
    return float(value) if np.isfinite(value) and value > 0 else float("inf")


def analyze_cointegration_formation(
    formation_data: pd.DataFrame,
    maximum_cointegration_pvalue: float = 0.10,
    adf_reference_pvalue: float = 0.10,
    minimum_half_life_days: float = 2.0,
    maximum_half_life_days: float = 120.0,
    minimum_mean_crossings: int = 4,
) -> CointegrationDiagnostics:
    if len(formation_data) < 60:
        raise ValueError("Formation period needs at least 60 observations.")

    y = formation_data["log_price_a"].astype(float)
    x = formation_data["log_price_b"].astype(float)
    alpha, beta = fit_ols(y, x)
    spread = y - alpha - beta * x
    spread_mean = float(spread.mean())
    spread_std = float(spread.std(ddof=1))

    if not np.isfinite(spread_std) or spread_std <= 0:
        raise ValueError("Formation spread has no usable variation.")

    cointegration_pvalue = float(
        coint(
            y.to_numpy(dtype=float),
            x.to_numpy(dtype=float),
            trend="c",
            autolag="AIC",
        )[1]
    )
    adf_pvalue = float(
        adfuller(
            spread.to_numpy(dtype=float),
            regression="c",
            autolag="AIC",
            result_object=False,
        )[1]
    )
    half_life_days = _estimate_half_life(spread)
    mean_crossings = count_mean_crossings(spread, spread_mean)

    reasons: list[str] = []
    if not np.isfinite(beta) or beta <= 0:
        reasons.append("invalid/non-positive hedge ratio")
    if cointegration_pvalue > maximum_cointegration_pvalue:
        reasons.append("cointegration p-value above threshold")
    if not np.isfinite(half_life_days):
        reasons.append("no finite mean-reversion half-life")
    elif half_life_days < minimum_half_life_days:
        reasons.append("half-life below minimum")
    elif half_life_days > maximum_half_life_days:
        reasons.append("half-life above maximum")
    if mean_crossings < minimum_mean_crossings:
        reasons.append("too few formation mean crossings")

    return CointegrationDiagnostics(
        alpha=alpha,
        beta=beta,
        spread_mean=spread_mean,
        spread_std=spread_std,
        cointegration_pvalue=cointegration_pvalue,
        adf_pvalue=adf_pvalue,
        adf_supportive=adf_pvalue <= adf_reference_pvalue,
        half_life_days=half_life_days,
        mean_crossings=mean_crossings,
        qualified=len(reasons) == 0,
        rejection_reasons=tuple(reasons),
    )


def build_cointegration_pairs_research(
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
    maximum_cointegration_pvalue: float = 0.10,
    adf_reference_pvalue: float = 0.10,
    minimum_half_life_days: float = 2.0,
    maximum_half_life_days: float = 120.0,
    minimum_mean_crossings: int = 4,
    require_qualification: bool = True,
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

    for fold, (
        formation_start,
        formation_end,
        trading_start,
        trading_end,
    ) in enumerate(boundaries, start=1):
        formation = pair.loc[formation_start:formation_end].copy()
        trading = pair.loc[trading_start:trading_end].copy()

        d = analyze_cointegration_formation(
            formation,
            maximum_cointegration_pvalue,
            adf_reference_pvalue,
            minimum_half_life_days,
            maximum_half_life_days,
            minimum_mean_crossings,
        )

        spread = (
            trading["log_price_a"].astype(float)
            - d.alpha
            - d.beta * trading["log_price_b"].astype(float)
        )
        zscore = (spread - d.spread_mean) / d.spread_std

        valid_beta = np.isfinite(d.beta) and d.beta > 0
        can_trade = valid_beta and (d.qualified or not require_qualification)
        tradable = pd.Series(can_trade, index=trading.index, dtype=bool)

        signals = generate_stateful_signal(
            zscore=zscore,
            entry_zscore=entry_zscore,
            exit_zscore=exit_zscore,
            stop_zscore=stop_zscore,
            maximum_holding_days=maximum_holding_days,
            tradable=tradable,
        )

        method_data = trading.copy()
        method_data["spread"] = spread
        method_data["spread_zscore"] = zscore
        method_data["pair_signal"] = signals["pair_signal"]
        method_data["exit_reason"] = signals["exit_reason"]
        method_data["beta"] = d.beta
        method_data["fold"] = fold
        method_data["qualified"] = d.qualified

        if valid_beta:
            denominator = 1.0 + abs(d.beta)
            desired_a = method_data["pair_signal"] / denominator
            desired_b = -method_data["pair_signal"] * d.beta / denominator
        else:
            desired_a = pd.Series(0.0, index=method_data.index)
            desired_b = pd.Series(0.0, index=method_data.index)

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

        rows.append(
            {
                "fold": fold,
                "formation_start": formation_start,
                "formation_end": formation_end,
                "trading_start": trading_start,
                "trading_end": trading_end,
                "qualified": d.qualified,
                "cointegration_pvalue": d.cointegration_pvalue,
                "adf_pvalue": d.adf_pvalue,
                "adf_supportive": d.adf_supportive,
                "beta": d.beta,
                "half_life_days": d.half_life_days,
                "mean_crossings": d.mean_crossings,
                "trades": trades,
                "turnover": float(tested["turnover"].sum()),
                "test_return": metrics["total_return"],
                "test_sharpe": metrics["sharpe_ratio"],
                "rejection_reasons": "; ".join(d.rejection_reasons),
            }
        )

        parts.append(
            tested[
                [
                    "price_a",
                    "price_b",
                    "return_a",
                    "return_b",
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
                    "qualified",
                    "beta",
                ]
            ].copy()
        )

    return build_research_result(
        "Cointegration Walk-Forward",
        ticker_a,
        ticker_b,
        pair,
        parts,
        pd.DataFrame(rows),
        initial_capital,
        transaction_cost_bps,
        risk_free_rate,
    )
