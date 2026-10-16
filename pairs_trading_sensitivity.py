"""
Local, in-sample parameter sensitivity for the pairs-trading methods.

Every active parameter is tested around its current value while the best
values found for earlier parameters are kept (coordinate descent). The result
is a coherent, tested parameter set, but it is selected on the same sample it
is reported on, so treat it as in-sample research rather than validation.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd

from pairs_trading_cointegration import build_cointegration_pairs_research
from pairs_trading_core import (
    METHOD_COINTEGRATION,
    METHOD_DISTANCE,
    METHOD_DYNAMIC,
    PairsResearchResult,
)
from pairs_trading_distance import build_distance_pairs_research
from pairs_trading_dynamic import build_dynamic_pairs_research


def _grid_around(
    value: float,
    step: float,
    lower: float,
    upper: float,
) -> list[float]:
    values = {
        max(lower, value - step),
        value,
        min(upper, value + step),
    }
    return sorted(float(item) for item in values)


def _integer_grid_around(
    value: int,
    step: int,
    lower: int,
    upper: int,
) -> list[int]:
    values = {
        max(lower, value - step),
        value,
        min(upper, value + step),
    }
    return sorted(int(item) for item in values)


def _multiplicative_grid(
    value: float,
    lower: float,
    upper: float,
) -> list[float]:
    values = {
        max(lower, value * 0.5),
        value,
        min(upper, value * 2.0),
    }
    return sorted(float(item) for item in values)


def _sensitivity_specifications(
    method: str,
    kwargs: dict[str, Any],
) -> list[tuple[str, Sequence[float | int]]]:
    entry = float(kwargs["entry_zscore"])
    exit_value = float(kwargs["exit_zscore"])
    stop = float(kwargs["stop_zscore"])

    specifications: list[tuple[str, Sequence[float | int]]] = [
        (
            "entry_zscore",
            _grid_around(
                entry,
                0.25,
                max(0.5, exit_value + 0.25),
                min(5.0, stop - 0.25),
            ),
        ),
        (
            "exit_zscore",
            _grid_around(
                exit_value,
                0.25,
                0.0,
                max(0.0, entry - 0.25),
            ),
        ),
        (
            "stop_zscore",
            _grid_around(
                stop,
                0.25,
                entry + 0.25,
                10.0,
            ),
        ),
        (
            "maximum_holding_days",
            _integer_grid_around(
                int(kwargs["maximum_holding_days"]),
                15,
                1,
                504,
            ),
        ),
    ]

    if method == METHOD_DISTANCE:
        specifications.extend(
            [
                (
                    "formation_years",
                    _integer_grid_around(
                        int(kwargs["formation_years"]), 1, 1, 10
                    ),
                ),
                (
                    "trading_months",
                    _integer_grid_around(
                        int(kwargs["trading_months"]), 3, 1, 24
                    ),
                ),
                (
                    "relationship_break_window",
                    _integer_grid_around(
                        int(kwargs["relationship_break_window"]), 10, 5, 120
                    ),
                ),
                (
                    "maximum_recent_volatility_ratio",
                    _grid_around(
                        float(kwargs["maximum_recent_volatility_ratio"]),
                        0.25,
                        1.0,
                        4.0,
                    ),
                ),
                (
                    "maximum_recent_mean_shift_z",
                    _grid_around(
                        float(kwargs["maximum_recent_mean_shift_z"]),
                        0.25,
                        0.5,
                        5.0,
                    ),
                ),
                (
                    "minimum_recent_return_correlation",
                    _grid_around(
                        float(kwargs["minimum_recent_return_correlation"]),
                        0.10,
                        -0.75,
                        0.75,
                    ),
                ),
            ]
        )
    elif method == METHOD_COINTEGRATION:
        specifications.extend(
            [
                (
                    "formation_years",
                    _integer_grid_around(
                        int(kwargs["formation_years"]), 1, 1, 10
                    ),
                ),
                (
                    "trading_months",
                    _integer_grid_around(
                        int(kwargs["trading_months"]), 3, 1, 24
                    ),
                ),
                (
                    "maximum_cointegration_pvalue",
                    _grid_around(
                        float(kwargs["maximum_cointegration_pvalue"]),
                        0.025,
                        0.025,
                        0.25,
                    ),
                ),
                (
                    "minimum_half_life_days",
                    _grid_around(
                        float(kwargs["minimum_half_life_days"]),
                        1.0,
                        0.5,
                        min(30.0, float(kwargs["maximum_half_life_days"]) - 1.0),
                    ),
                ),
                (
                    "maximum_half_life_days",
                    _grid_around(
                        float(kwargs["maximum_half_life_days"]),
                        30.0,
                        float(kwargs["minimum_half_life_days"]) + 1.0,
                        360.0,
                    ),
                ),
                (
                    "minimum_mean_crossings",
                    _integer_grid_around(
                        int(kwargs["minimum_mean_crossings"]), 2, 0, 20
                    ),
                ),
            ]
        )
    else:
        specifications.extend(
            [
                (
                    "warmup_window",
                    _integer_grid_around(
                        int(kwargs["warmup_window"]), 30, 30, 252
                    ),
                ),
                (
                    "zscore_window",
                    _integer_grid_around(
                        int(kwargs.get("zscore_window", 60)), 20, 10, 252
                    ),
                ),
                (
                    "state_noise",
                    _multiplicative_grid(
                        float(kwargs["state_noise"]), 1e-7, 0.01
                    ),
                ),
                (
                    "observation_noise_scale",
                    _grid_around(
                        float(kwargs["observation_noise_scale"]),
                        0.25,
                        0.10,
                        5.0,
                    ),
                ),
                (
                    "minimum_hedge_ratio",
                    _grid_around(
                        float(kwargs["minimum_hedge_ratio"]),
                        0.10,
                        0.01,
                        min(2.0, float(kwargs["maximum_hedge_ratio"]) - 0.05),
                    ),
                ),
                (
                    "maximum_hedge_ratio",
                    _grid_around(
                        float(kwargs["maximum_hedge_ratio"]),
                        0.50,
                        float(kwargs["minimum_hedge_ratio"]) + 0.05,
                        8.0,
                    ),
                ),
            ]
        )

    return specifications


def run_pairs_method(method: str, kwargs: dict[str, Any]) -> PairsResearchResult:
    if method == METHOD_DISTANCE:
        return build_distance_pairs_research(**kwargs)
    if method == METHOD_COINTEGRATION:
        return build_cointegration_pairs_research(**kwargs)
    return build_dynamic_pairs_research(**kwargs)


def _objective_key(result: PairsResearchResult) -> tuple[float, float]:
    sharpe = float(result.strategy_metrics["sharpe_ratio"])
    total_return = float(result.strategy_metrics["total_return"])
    if not np.isfinite(sharpe):
        sharpe = float("-inf")
    if not np.isfinite(total_return):
        total_return = float("-inf")
    return sharpe, total_return


def run_parameter_sensitivity(
    method: str,
    base_kwargs: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run a local coordinate sensitivity search across every active parameter.

    Each parameter is tested around the current setting while the best settings
    found for earlier parameters are retained. The final recommendation is therefore
    a tested, coherent parameter set rather than a collection of independently best
    one-dimensional values. This remains in-sample research, not validation.
    """
    current = dict(base_kwargs)
    rows: list[dict[str, object]] = []

    for parameter, candidate_values in _sensitivity_specifications(method, current):
        baseline_value = current[parameter]
        best_value = baseline_value
        best_key = (float("-inf"), float("-inf"))

        for candidate in candidate_values:
            trial = dict(current)
            trial[parameter] = candidate

            # Structural constraints that can change when neighboring parameters
            # are tested. Invalid candidates are skipped rather than crashing the
            # entire sensitivity analysis.
            if float(trial["exit_zscore"]) >= float(trial["entry_zscore"]):
                continue
            if float(trial["stop_zscore"]) <= float(trial["entry_zscore"]):
                continue
            if method == METHOD_COINTEGRATION and (
                float(trial["maximum_half_life_days"])
                <= float(trial["minimum_half_life_days"])
            ):
                continue
            if method == METHOD_DYNAMIC and (
                float(trial["maximum_hedge_ratio"])
                <= float(trial["minimum_hedge_ratio"])
            ):
                continue

            result = run_pairs_method(method, trial)
            key = _objective_key(result)

            rows.append(
                {
                    "parameter": parameter,
                    "base_value": baseline_value,
                    "tested_value": candidate,
                    "total_return": result.strategy_metrics["total_return"],
                    "sharpe_ratio": result.strategy_metrics["sharpe_ratio"],
                    "max_drawdown": result.strategy_metrics["max_drawdown"],
                    "trades": len(result.trades),
                    "turnover": float(result.stitched_data["turnover"].sum()),
                }
            )

            if key > best_key:
                best_key = key
                best_value = candidate

        for row in rows:
            if row["parameter"] == parameter:
                row["selected"] = (row["tested_value"] == best_value)

        current[parameter] = best_value

    # Evaluate the final combined sensitivity-derived parameter set explicitly.
    optimized_result = run_pairs_method(method, current)
    rows.append(
        {
            "parameter": "FINAL COMBINED SET",
            "base_value": "—",
            "tested_value": "—",
            "total_return": optimized_result.strategy_metrics["total_return"],
            "sharpe_ratio": optimized_result.strategy_metrics["sharpe_ratio"],
            "max_drawdown": optimized_result.strategy_metrics["max_drawdown"],
            "trades": len(optimized_result.trades),
            "turnover": float(optimized_result.stitched_data["turnover"].sum()),
            "selected": True,
        }
    )

    return pd.DataFrame(rows), current
