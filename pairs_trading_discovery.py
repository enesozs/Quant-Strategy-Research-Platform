from __future__ import annotations

import numpy as np
import pandas as pd

from pairs_trading_cointegration import analyze_cointegration_formation
from pairs_trading_core import (
    METHOD_COINTEGRATION,
    METHOD_DISTANCE,
    METHOD_DYNAMIC,
    count_mean_crossings,
    iter_universe_pairs,
    prepare_universe_data,
)
from pairs_trading_dynamic import calculate_kalman_relationship




# Starting universes for discovery. Same-industry names and ETFs with
# overlapping exposures are where economic links (and so mean reversion) are
# most plausible.
UNIVERSE_PRESETS: dict[str, list[str]] = {
    "Beverages & snacks": ["KO", "PEP", "KDP", "MNST", "MDLZ", "GIS", "HSY"],
    "Oil majors": ["XOM", "CVX", "COP", "BP", "SHEL", "TTE", "EOG"],
    "US banks": ["JPM", "BAC", "C", "WFC", "USB", "PNC", "TFC"],
    "Payments": ["V", "MA", "AXP", "PYPL", "FI", "FIS"],
    "Home improvement & retail": ["HD", "LOW", "TGT", "WMT", "COST"],
    "Country ETFs": ["EWA", "EWC", "EWU", "EWG", "EWJ", "EWQ", "EWL"],
    "Sector ETFs": ["XLE", "XLF", "XLK", "XLU", "XLP", "XLV", "XLI", "XLY"],
    "Precious metals": ["GLD", "SLV", "GDX", "GDXJ", "NEM", "GOLD"],
}


def discover_pairs(
    tickers: list[str],
    start_date: str,
    end_date: str,
    method: str,
    formation_years: int = 2,
    minimum_observations: int = 120,
    top_n: int = 10,
    maximum_cointegration_pvalue: float = 0.10,
    minimum_half_life_days: float = 2.0,
    maximum_half_life_days: float = 120.0,
    minimum_mean_crossings: int = 4,
    kalman_warmup_window: int = 120,
    kalman_state_noise: float = 1e-5,
    kalman_observation_noise_scale: float = 1.0,
    kalman_zscore_window: int = 60,
) -> pd.DataFrame:
    """
    Rank candidate pairs on the first ``formation_years`` of the sample.

    Ranking on the whole period (or its end) and then backtesting the winners
    over the same period is selection look-ahead: the pair was chosen because
    it already behaved well in the data being traded. Using only the opening
    formation window, which is also the first walk-forward formation window,
    keeps every later trading period out of sample for the selection step.
    """
    universe = prepare_universe_data(tickers, start_date, end_date)
    formation_start = pd.Timestamp(start_date)
    formation_end = formation_start + pd.DateOffset(years=formation_years)
    rows: list[dict[str, object]] = []

    for ticker_a, ticker_b, pair in iter_universe_pairs(universe):
        formation = pair.loc[
            (pair.index >= formation_start) & (pair.index < formation_end)
        ].copy()
        if len(formation) < minimum_observations:
            continue

        return_corr = float(
            formation[["return_a", "return_b"]].dropna().corr().iloc[0, 1]
        )

        if method == METHOD_DISTANCE:
            base_a = float(formation["price_a"].iloc[0])
            base_b = float(formation["price_b"].iloc[0])
            spread = (
                formation["price_a"].astype(float) / base_a
                - formation["price_b"].astype(float) / base_b
            )
            distance_score = float(np.mean(np.square(spread.to_numpy(dtype=float))))
            spread_std = float(spread.std(ddof=1))
            crossings = count_mean_crossings(spread, float(spread.mean()))

            rows.append(
                {
                    "asset_a": ticker_a,
                    "asset_b": ticker_b,
                    "observations": len(formation),
                    "return_correlation": return_corr,
                    "distance_score": distance_score,
                    "spread_std": spread_std,
                    "mean_crossings": crossings,
                }
            )

        elif method == METHOD_COINTEGRATION:
            try:
                d = analyze_cointegration_formation(
                    formation,
                    maximum_cointegration_pvalue=maximum_cointegration_pvalue,
                    minimum_half_life_days=minimum_half_life_days,
                    maximum_half_life_days=maximum_half_life_days,
                    minimum_mean_crossings=minimum_mean_crossings,
                )
            except Exception:
                continue

            rows.append(
                {
                    "asset_a": ticker_a,
                    "asset_b": ticker_b,
                    "observations": len(formation),
                    "return_correlation": return_corr,
                    "qualified": d.qualified,
                    "cointegration_pvalue": d.cointegration_pvalue,
                    "adf_pvalue": d.adf_pvalue,
                    "half_life_days": d.half_life_days,
                    "mean_crossings": d.mean_crossings,
                    "beta": d.beta,
                }
            )

        elif method == METHOD_DYNAMIC:
            if len(formation) <= kalman_warmup_window + 20:
                continue
            try:
                modeled = calculate_kalman_relationship(
                    formation,
                    warmup_window=kalman_warmup_window,
                    state_noise=kalman_state_noise,
                    observation_noise_scale=kalman_observation_noise_scale,
                    zscore_window=kalman_zscore_window,
                )
            except Exception:
                continue

            beta = modeled["dynamic_beta"].dropna()
            if beta.empty:
                continue
            valid_beta = beta[beta > 0]
            if valid_beta.empty:
                continue

            beta_cv = float(valid_beta.std(ddof=1) / abs(valid_beta.mean()))
            innovation_std = float(modeled["spread"].dropna().std(ddof=1))
            valid_share = float((modeled["dynamic_beta"] > 0).mean())

            rows.append(
                {
                    "asset_a": ticker_a,
                    "asset_b": ticker_b,
                    "observations": len(formation),
                    "return_correlation": return_corr,
                    "valid_beta_share": valid_share,
                    "median_beta": float(valid_beta.median()),
                    "beta_coefficient_of_variation": beta_cv,
                    "innovation_std": innovation_std,
                }
            )
        else:
            raise ValueError(f"Unknown discovery method: {method}")

    result = pd.DataFrame(rows)
    if result.empty:
        return result

    if method == METHOD_DISTANCE:
        result = result.sort_values(
            ["distance_score", "spread_std", "mean_crossings"],
            ascending=[True, True, False],
        )
    elif method == METHOD_COINTEGRATION:
        # Testing many pairs at p < 0.10 guarantees false positives: with 45
        # pairs, about four pass by chance alone. The Bonferroni-adjusted
        # p-value shows which results survive that multiple-testing burden.
        result["bonferroni_pvalue"] = (
            result["cointegration_pvalue"] * len(result)
        ).clip(upper=1.0)
        result = result.sort_values(
            ["qualified", "cointegration_pvalue", "half_life_days", "mean_crossings"],
            ascending=[False, True, True, False],
        )
    else:
        result = result.sort_values(
            ["valid_beta_share", "beta_coefficient_of_variation", "return_correlation"],
            ascending=[False, True, False],
        )

    return result.head(top_n).reset_index(drop=True)
