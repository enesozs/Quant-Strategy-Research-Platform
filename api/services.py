"""Glue between the HTTP layer and the core research modules.

Every function takes a validated request model and returns a JSON-safe dict
in the shape documented in api/CONTRACT.md.
"""

from __future__ import annotations

import dataclasses
import inspect
import math
from typing import Any

import numpy as np
import pandas as pd

from api import cache, schemas
from api.serialize import (
    clean_float,
    frame_to_rows,
    metrics_to_json,
    to_date_string,
    to_jsonable,
    to_timeseries,
)
from backtester import run_backtest
from comparison import compare_all_strategies
from metrics import calculate_performance_metrics
from optimization import (
    calculate_optimization_gain,
    calculate_optimization_robustness,
    calculate_relative_optimization_gain,
    create_parameter_sensitivity_profile,
    create_refined_parameter_grid,
    optimize_strategy,
)
from pairs_trading_cointegration import build_cointegration_pairs_research
from pairs_trading_core import METHOD_COINTEGRATION, METHOD_DISTANCE, METHOD_DYNAMIC
from pairs_trading_discovery import UNIVERSE_PRESETS, discover_pairs
from pairs_trading_distance import build_distance_pairs_research
from pairs_trading_dynamic import build_dynamic_pairs_research
from pairs_trading_portfolio import build_pairs_portfolio
from pairs_trading_sensitivity import run_parameter_sensitivity
from strategies import (
    OPTIMIZATION_GRIDS,
    STRATEGY_METADATA,
    apply_strategy,
    get_default_parameters,
    get_optimization_grid,
)
from validation import (
    build_validation_summary,
    validate_strategy_out_of_sample,
    validate_strategy_walk_forward,
)

cache.install()

MAX_RESULT_ROWS = 500

# --------------------------------------------------------------------------
# Meta
# --------------------------------------------------------------------------

OBJECTIVES = [
    {
        "key": "sharpe_ratio",
        "label": "Sharpe ratio",
        "higher_is_better": True,
        "format": "ratio",
    },
    {
        "key": "total_return",
        "label": "Total return",
        "higher_is_better": True,
        "format": "percent",
    },
    {"key": "cagr", "label": "CAGR", "higher_is_better": True, "format": "percent"},
    {
        "key": "annualized_volatility",
        "label": "Annualized volatility",
        "higher_is_better": False,
        "format": "percent",
    },
    {
        "key": "max_drawdown",
        "label": "Maximum drawdown",
        "higher_is_better": True,
        "format": "percent",
    },
    {
        "key": "calmar_ratio",
        "label": "Calmar ratio",
        "higher_is_better": True,
        "format": "ratio",
    },
]

PAIRS_METHODS = [
    {
        "key": "distance",
        "label": "Distance",
        "description": (
            "Rebases both prices on each formation window and trades the z-score of "
            "their normalized spread, walking forward through formation and trading windows."
        ),
    },
    {
        "key": "cointegration",
        "label": "Cointegration",
        "description": (
            "Re-estimates an OLS hedge ratio each formation window, trades only when the "
            "Engle-Granger test, half-life and mean-crossing filters qualify the pair."
        ),
    },
    {
        "key": "kalman",
        "label": "Kalman hedge ratio",
        "description": (
            "Tracks a time-varying hedge ratio with a Kalman filter and trades the z-score "
            "of the filter's innovations, locking the hedge ratio in at entry."
        ),
    },
]

METHOD_NAMES = {
    "distance": METHOD_DISTANCE,
    "cointegration": METHOD_COINTEGRATION,
    "kalman": METHOD_DYNAMIC,
}

PAIRS_BUILDERS = {
    "distance": build_distance_pairs_research,
    "cointegration": build_cointegration_pairs_research,
    "kalman": build_dynamic_pairs_research,
}

# Builder arguments the request supplies itself; `params` may not override them.
_PAIRS_RESERVED = {
    "ticker_a",
    "ticker_b",
    "start_date",
    "end_date",
    "initial_capital",
    "transaction_cost_bps",
    "risk_free_rate",
    "cash_rate",
    "borrow_fee",
}


def _grid_size(grid: dict[str, list[Any]]) -> int:
    return int(math.prod(len(values) for values in grid.values()))


def get_meta() -> dict[str, Any]:
    strategies = []
    for key, metadata in STRATEGY_METADATA.items():
        grid = get_optimization_grid(key) if key in OPTIMIZATION_GRIDS else {}
        strategies.append(
            {
                "key": key,
                "display_name": metadata.get("display_name", key),
                "family": metadata.get("family", ""),
                "subtype": metadata.get("subtype", ""),
                "features": list(metadata.get("features", [])),
                "signal_style": metadata.get("signal_style", ""),
                "best_suited_for": metadata.get("best_suited_for", ""),
                "description": metadata.get("description", ""),
                "thesis": metadata.get("thesis", ""),
                "favorable_environment": metadata.get("favorable_environment", ""),
                "unfavorable_environment": metadata.get("unfavorable_environment", ""),
                "main_risks": metadata.get("main_risks", ""),
                "optimization_notes": metadata.get("optimization_notes", ""),
                "validation_focus": metadata.get("validation_focus", ""),
                "related_strategies": list(metadata.get("related_strategies", [])),
                "parameters": {
                    name: {
                        field: spec[field]
                        for field in (
                            "label",
                            "type",
                            "default",
                            "min",
                            "max",
                            "step",
                            "format",
                        )
                        if field in spec
                    }
                    for name, spec in metadata["parameters"].items()
                },
                "default_grid": grid,
                "grid_size": _grid_size(grid) if grid else 0,
            }
        )

    return to_jsonable(
        {
            "strategies": strategies,
            "objectives": OBJECTIVES,
            "pairs_methods": PAIRS_METHODS,
            "universe_presets": UNIVERSE_PRESETS,
        }
    )


# --------------------------------------------------------------------------
# Parameter and grid validation
# --------------------------------------------------------------------------


def _coerce_value(strategy: str, name: str, value: float, where: str) -> int | float:
    spec = STRATEGY_METADATA[strategy]["parameters"][name]
    if spec["type"] == "int":
        if not float(value).is_integer():
            raise ValueError(f"{where} '{name}' must be a whole number, got {value}.")
        coerced: int | float = int(value)
    else:
        coerced = float(value)
    if not spec["min"] <= coerced <= spec["max"]:
        raise ValueError(
            f"{where} '{name}' must be between {spec['min']} and {spec['max']}, got {value}."
        )
    return coerced


def _check_names(strategy: str, names: list[str], where: str) -> None:
    valid = STRATEGY_METADATA[strategy]["parameters"]
    unknown = sorted(set(names) - set(valid))
    if unknown:
        raise ValueError(
            f"Unknown {where.lower()}(s) for strategy '{strategy}': {', '.join(unknown)}. "
            f"Valid: {', '.join(valid)}."
        )


def resolve_parameters(
    strategy: str, parameters: dict[str, float] | None
) -> dict[str, Any]:
    """Merge (validated) partial parameters over the strategy defaults."""
    resolved = get_default_parameters(strategy)
    if parameters:
        _check_names(strategy, list(parameters), "Parameter")
        for name, value in parameters.items():
            resolved[name] = _coerce_value(strategy, name, value, "Parameter")
    return resolved


def resolve_grid(
    strategy: str, grid: dict[str, list[float]] | None
) -> dict[str, list[Any]]:
    """Validate a user grid (or return the predefined one) and enforce the size cap."""
    if not grid:
        resolved = get_optimization_grid(strategy)
    else:
        _check_names(strategy, list(grid), "Grid parameter")
        resolved = {}
        for name, values in grid.items():
            coerced = [
                _coerce_value(strategy, name, value, "Grid value for")
                for value in values
            ]
            resolved[name] = sorted(set(coerced))
    _check_grid_size(resolved)
    return resolved


def _check_grid_size(grid: dict[str, list[Any]]) -> None:
    size = _grid_size(grid)
    if size > schemas.MAX_GRID_COMBINATIONS:
        raise ValueError(
            f"The grid has {size:,} raw combinations; the limit is "
            f"{schemas.MAX_GRID_COMBINATIONS:,}. Use fewer values per parameter."
        )


# --------------------------------------------------------------------------
# Single-asset research
# --------------------------------------------------------------------------

_HELPER_COLUMNS = {"signal", "target_position", "typical_price", "weekly_trend_signal"}


def _tracks_price(series: pd.Series, close: pd.Series) -> bool:
    frame = (
        pd.DataFrame({"value": series, "close": close})
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )
    if len(frame) < 3 or (frame["close"] == 0).any():
        return False
    ratio = frame["value"] / frame["close"]
    if float(ratio.between(0.5, 2.0).mean()) < 0.9:
        return False
    if frame["value"].std() == 0 or frame["close"].std() == 0:
        return False
    return bool(frame["value"].corr(frame["close"]) > 0.8)


def _split_indicators(
    strategy_data: pd.DataFrame,
    input_columns: set[str],
) -> tuple[list[str], list[str]]:
    """
    Classify a strategy's indicator columns as price overlays or oscillators.

    An overlay sits on the price's scale (median level within 0.5x-2x of the
    median close) and also tracks it: it stays within 0.5x-2x of the close on
    at least 90% of rows and is strongly correlated with it. The second test
    keeps bounded oscillators (RSI, +DI/-DI, stochastic) off the price chart
    when the asset happens to trade near their range.
    """
    close = strategy_data["Close"].astype(float)
    close_level = float(np.nanmedian(np.abs(close.to_numpy(dtype=float))))
    overlays: list[str] = []
    oscillators: list[str] = []

    for column in strategy_data.columns:
        if column in input_columns or column in _HELPER_COLUMNS:
            continue
        series = strategy_data[column]
        if series.dtype == bool or pd.api.types.is_integer_dtype(series):
            continue  # binary state flags, not plottable indicators
        if not pd.api.types.is_numeric_dtype(series):
            continue
        values = series.to_numpy(dtype=float)
        finite = values[np.isfinite(values)]
        if finite.size == 0:
            continue
        level = float(np.median(np.abs(finite)))
        if (
            close_level > 0
            and 0.5 * close_level <= level <= 2.0 * close_level
            and _tracks_price(series.astype(float), close)
        ):
            overlays.append(str(column))
        else:
            oscillators.append(str(column))

    return overlays, oscillators


def run_backtest_request(request: schemas.BacktestRequest) -> dict[str, Any]:
    parameters = resolve_parameters(request.strategy, request.parameters)
    data = cache.prepare_market_data(request.ticker, request.start, request.end)

    strategy_data = apply_strategy(data, request.strategy, parameters)
    results = run_backtest(
        strategy_data,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        cash_rate=request.cash_rate,
    )

    metrics = calculate_performance_metrics(
        returns=results["strategy_return"],
        equity=results["strategy_equity"],
        risk_free_rate=request.risk_free_rate,
        initial_value=request.initial_capital,
    )
    trades = results["trade"].astype(float)
    metrics.update(
        final_value=float(results["strategy_equity"].iloc[-1]),
        rebalancing_days=float((trades > 0).sum()),
        turnover=float(trades.sum()),
        average_exposure=float(results["position"].astype(float).mean()),
    )

    benchmark = calculate_performance_metrics(
        returns=results["buy_hold_return"],
        equity=results["buy_hold_equity"],
        risk_free_rate=request.risk_free_rate,
        initial_value=request.initial_capital,
    )
    benchmark_turnover = results["buy_hold_turnover"].astype(float)
    benchmark.update(
        final_value=float(results["buy_hold_equity"].iloc[-1]),
        rebalancing_days=float((benchmark_turnover > 0).sum()),
        turnover=float(benchmark_turnover.sum()),
        average_exposure=1.0,
    )

    overlays, oscillators = _split_indicators(strategy_data, set(data.columns))

    return {
        "strategy": request.strategy,
        "parameters": to_jsonable(parameters),
        "metrics": metrics_to_json(metrics),
        "benchmark_metrics": metrics_to_json(benchmark),
        "series": to_timeseries(
            results.rename(columns={"Close": "close"}),
            [
                "close",
                "position",
                "strategy_equity",
                "buy_hold_equity",
                "strategy_drawdown",
                "buy_hold_drawdown",
            ],
        ),
        "overlays": to_timeseries(strategy_data, overlays),
        "oscillators": to_timeseries(strategy_data, oscillators),
    }


def run_compare_request(request: schemas.CompareRequest) -> dict[str, Any]:
    comparison_result = compare_all_strategies(
        ticker=request.ticker,
        start_date=request.start,
        end_date=request.end,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        cash_rate=request.cash_rate,
        risk_free_rate=request.risk_free_rate,
        use_optimized_parameters=request.use_optimized_parameters,
        optimization_objective=request.objective,
    )

    summary = comparison_result.summary.rename(
        columns={"strategy": "display_name", "strategy_key": "strategy"}
    )
    leading = ["strategy", "display_name", "family", "parameters"]
    summary = summary[leading + [c for c in summary.columns if c not in leading]]

    equity = pd.DataFrame(
        {
            key: frame["strategy_equity"]
            for key, frame in comparison_result.strategy_results.items()
        }
    )
    first = next(iter(comparison_result.strategy_results.values()))
    equity["buy_hold"] = first["buy_hold_equity"]

    benchmark = dict(comparison_result.benchmark_metrics)
    benchmark.update(
        final_value=float(first["buy_hold_equity"].iloc[-1]),
        rebalancing_days=float((first["buy_hold_turnover"] > 0).sum()),
        turnover=float(first["buy_hold_turnover"].sum()),
        average_exposure=1.0,
    )

    return {
        "in_sample": bool(request.use_optimized_parameters),
        "rows": frame_to_rows(summary),
        "benchmark": metrics_to_json(benchmark),
        "equity": to_timeseries(equity),
    }


def _heatmap(
    results: pd.DataFrame, grid: dict[str, list[Any]], objective: str
) -> dict | None:
    candidates = [
        name
        for name in grid
        if name in results.columns and results[name].nunique() >= 2
    ]
    if len(candidates) < 2:
        return None
    # Stable sort: most distinct values first, grid order breaks ties.
    candidates.sort(key=lambda name: -results[name].nunique())
    x_name, y_name = candidates[0], candidates[1]

    frame = results[[x_name, y_name, objective]].copy()
    frame[objective] = pd.to_numeric(frame[objective], errors="coerce").replace(
        [np.inf, -np.inf], np.nan
    )
    aggregate = "min" if objective == "annualized_volatility" else "max"
    table = frame.pivot_table(
        index=y_name, columns=x_name, values=objective, aggfunc=aggregate, dropna=False
    )
    x_values = sorted(results[x_name].dropna().unique().tolist())
    y_values = sorted(results[y_name].dropna().unique().tolist())
    table = table.reindex(index=y_values, columns=x_values)

    return {
        "x_parameter": x_name,
        "y_parameter": y_name,
        "x_values": to_jsonable(x_values),
        "y_values": to_jsonable(y_values),
        "z": [
            [clean_float(value) for value in row] for row in table.to_numpy(dtype=float)
        ],
    }


def _profiles(
    results: pd.DataFrame, grid: dict[str, list[Any]], objective: str
) -> dict:
    profiles: dict[str, list[dict[str, Any]]] = {}
    for name in grid:
        try:
            profile = create_parameter_sensitivity_profile(results, name, objective)
        except ValueError:
            profiles[name] = []
            continue
        profiles[name] = [
            {
                "value": to_jsonable(row[name]),
                "best": clean_float(row["best_observed"]),
                "median": clean_float(row["median_objective"]),
            }
            for _, row in profile.iterrows()
        ]
    return profiles


def run_optimize_request(request: schemas.OptimizeRequest) -> dict[str, Any]:
    if request.mode == "predefined":
        grid = resolve_grid(request.strategy, None)
    else:
        grid = resolve_grid(request.strategy, request.grid)

    data = cache.prepare_market_data(request.ticker, request.start, request.end)
    common: dict[str, Any] = {
        "data": data,
        "strategy_name": request.strategy,
        "objective": request.objective,
        "initial_capital": request.initial_capital,
        "transaction_cost_bps": request.transaction_cost_bps,
        "cash_rate": request.cash_rate,
        "risk_free_rate": request.risk_free_rate,
    }

    result = optimize_strategy(parameter_grid=grid, **common)
    stages = None
    combinations_tested = len(result.results)
    result_grid = grid

    if request.mode == "coarse_to_fine":
        # Mirrors optimize_strategy_coarse_to_fine, with the size cap applied
        # to the refined grid before it runs.
        broad = result
        refined_grid = create_refined_parameter_grid(
            strategy_name=request.strategy,
            broad_parameter_grid=grid,
            broad_best_parameters=broad.best_parameters,
            refinement_points=request.refinement_points,
        )
        _check_grid_size(refined_grid)
        result = optimize_strategy(
            parameter_grid=refined_grid,
            evaluation_start=broad.evaluation_start,
            **common,
        )
        result_grid = refined_grid
        combinations_tested = len(broad.results) + len(result.results)
        stages = {
            "broad_combinations": len(broad.results),
            "refined_combinations": len(result.results),
            "broad_best_parameters": to_jsonable(broad.best_parameters),
            "refined_grid": to_jsonable(refined_grid),
        }

    objective = request.objective
    robustness = calculate_optimization_robustness(result)
    best_value = float(result.best_metrics[objective])
    default_value = float(result.default_metrics[objective])

    response: dict[str, Any] = {
        "objective": objective,
        "evaluation_start": to_date_string(result.evaluation_start),
        "combinations_tested": int(combinations_tested),
        "best_parameters": to_jsonable(result.best_parameters),
        "best_metrics": metrics_to_json(result.best_metrics),
        "default_parameters": to_jsonable(result.default_parameters),
        "default_metrics": metrics_to_json(result.default_metrics),
        "optimization_gain": clean_float(
            calculate_optimization_gain(best_value, default_value, objective)
        ),
        "relative_optimization_gain": clean_float(
            calculate_relative_optimization_gain(best_value, default_value, objective)
        ),
        "probabilistic_sharpe_ratio": clean_float(result.probabilistic_sharpe_ratio),
        "deflated_sharpe_ratio": clean_float(result.deflated_sharpe_ratio),
        "robustness": to_jsonable(dataclasses.asdict(robustness)),
        "results": frame_to_rows(result.results.head(MAX_RESULT_ROWS)),
        "heatmap": _heatmap(result.results, result_grid, objective),
        "profiles": _profiles(result.results, result_grid, objective),
    }
    if stages is not None:
        response["stages"] = stages
    return response


_EQUITY_RENAME = {"Buy and Hold": "buy_hold"}


def _parameter_set(parameter_set: Any) -> dict[str, Any]:
    return {
        "label": parameter_set.label,
        "parameters": to_jsonable(parameter_set.parameters),
        "training_metrics": metrics_to_json(parameter_set.training_metrics),
        "test_metrics": metrics_to_json(parameter_set.test_metrics),
    }


def run_validate_split_request(request: schemas.ValidateSplitRequest) -> dict[str, Any]:
    grid = resolve_grid(request.strategy, request.grid)
    data = cache.prepare_market_data(request.ticker, request.start, request.end)

    validation = validate_strategy_out_of_sample(
        data=data,
        strategy_name=request.strategy,
        split_date=request.split_date.isoformat(),
        parameter_grid=grid,
        objective=request.objective,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        cash_rate=request.cash_rate,
        risk_free_rate=request.risk_free_rate,
    )

    return {
        "split_date": to_date_string(validation.split_date),
        "training_evaluation_start": to_date_string(
            validation.optimization_result.evaluation_start
        ),
        "robustness_label": validation.robustness.robustness_label,
        "parameter_sets": [
            _parameter_set(validation.default),
            _parameter_set(validation.optimized),
            _parameter_set(validation.robust_candidate),
        ],
        "benchmark": {
            "training_metrics": metrics_to_json(validation.benchmark_training_metrics),
            "test_metrics": metrics_to_json(validation.benchmark_test_metrics),
        },
        "summary": frame_to_rows(build_validation_summary(validation)),
        "test_equity": to_timeseries(
            validation.test_equity_curves.rename(columns=_EQUITY_RENAME)
        ),
    }


def run_walk_forward_request(request: schemas.WalkForwardRequest) -> dict[str, Any]:
    data = cache.prepare_market_data(request.ticker, request.start, request.end)

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name=request.strategy,
        objective=request.objective,
        training_window_type=request.window_type,
        initial_training_years=request.initial_training_years,
        test_window_years=request.test_window_years,
        initial_capital=request.initial_capital,
        transaction_cost_bps=request.transaction_cost_bps,
        cash_rate=request.cash_rate,
        risk_free_rate=request.risk_free_rate,
    )

    return {
        "folds": frame_to_rows(result.fold_summary),
        "parameter_history": frame_to_rows(result.parameter_history),
        "aggregate": frame_to_rows(result.aggregate_summary),
        "stitched_equity": to_timeseries(
            result.stitched_equity_curves.rename(columns=_EQUITY_RENAME)
        ),
    }


# --------------------------------------------------------------------------
# Pairs
# --------------------------------------------------------------------------


def _builder_defaults(method: str) -> dict[str, Any]:
    signature = inspect.signature(PAIRS_BUILDERS[method])
    return {
        name: parameter.default
        for name, parameter in signature.parameters.items()
        if parameter.default is not inspect.Parameter.empty
        and name not in _PAIRS_RESERVED
    }


def _coerce_pairs_params(
    method: str,
    params: dict[str, Any] | None,
    extra_defaults: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate free-form pairs params against the builder's signature
    (plus ``extra_defaults``, e.g. discovery-only arguments) and coerce each
    value to the type of its default."""
    defaults = {**(extra_defaults or {}), **_builder_defaults(method)}
    allowed = set(defaults)
    reserved = sorted(set(params or {}) & _PAIRS_RESERVED)
    if reserved:
        raise ValueError(
            f"Set {', '.join(reserved)} in the request body, not in params."
        )
    unknown = sorted(set(params or {}) - allowed)
    if unknown:
        raise ValueError(
            f"Unknown {method} parameter(s): {', '.join(unknown)}. "
            f"Valid: {', '.join(sorted(allowed))}."
        )

    coerced: dict[str, Any] = {}
    for name, value in (params or {}).items():
        default = defaults.get(name)
        if value is None:
            if default is None:
                coerced[name] = None
                continue
            raise ValueError(f"Parameter '{name}' cannot be null.")
        if isinstance(default, bool):
            if not isinstance(value, bool):
                # ValueError (not TypeError) so the API maps it to 422.
                raise ValueError(f"Parameter '{name}' must be true or false.")  # noqa: TRY004
            coerced[name] = value
        elif isinstance(default, int):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not float(value).is_integer()
            ):
                raise ValueError(f"Parameter '{name}' must be a whole number.")
            coerced[name] = int(value)
        elif isinstance(default, float):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError(f"Parameter '{name}' must be a finite number.")
            coerced[name] = float(value)
        else:  # e.g. trading_start (str | None)
            coerced[name] = value if isinstance(value, str) else str(value)
    return coerced


def _pairs_assumptions(request: schemas.PairsAssumptions) -> dict[str, Any]:
    return {
        "initial_capital": request.initial_capital,
        "transaction_cost_bps": request.transaction_cost_bps,
        "risk_free_rate": request.risk_free_rate,
        "cash_rate": request.cash_rate,
        "borrow_fee": request.borrow_fee,
    }


def _research_kwargs(request: schemas.PairsResearchRequest) -> dict[str, Any]:
    return {
        "ticker_a": request.ticker_a,
        "ticker_b": request.ticker_b,
        "start_date": request.start,
        "end_date": request.end,
        **_pairs_assumptions(request),
        **_coerce_pairs_params(request.method, request.params),
    }


def run_pairs_research_request(request: schemas.PairsResearchRequest) -> dict[str, Any]:
    result = PAIRS_BUILDERS[request.method](**_research_kwargs(request))
    stitched = result.stitched_data.copy()

    stitched["normalized_a"] = stitched["price_a"] / float(stitched["price_a"].iloc[0])
    stitched["normalized_b"] = stitched["price_b"] / float(stitched["price_b"].iloc[0])
    if "hedge_beta" not in stitched.columns and "beta" in stitched.columns:
        stitched["hedge_beta"] = stitched["beta"]

    columns = [
        "normalized_a",
        "normalized_b",
        "spread",
        "spread_zscore",
        "pair_position",
        "strategy_equity",
        "benchmark_equity",
        "strategy_drawdown",
        "benchmark_drawdown",
        "hedge_beta",
        "dynamic_beta",
    ]

    trades = result.trades
    exit_reasons: dict[str, int] = {}
    if not trades.empty and "exit_reason" in trades.columns:
        exit_reasons = {
            str(reason): int(count)
            for reason, count in trades["exit_reason"].value_counts().items()
        }

    return {
        "method": request.method,
        "ticker_a": result.ticker_a,
        "ticker_b": result.ticker_b,
        "metrics": metrics_to_json(
            {
                **result.strategy_metrics,
                "final_value": stitched["strategy_equity"].iloc[-1],
            }
        ),
        "benchmark_metrics": metrics_to_json(
            {
                **result.benchmark_metrics,
                "final_value": stitched["benchmark_equity"].iloc[-1],
            }
        ),
        "return_correlation": clean_float(result.full_sample_return_correlation),
        "price_correlation": clean_float(result.full_sample_price_correlation),
        "series": to_timeseries(stitched, columns),
        "trades": frame_to_rows(trades),
        "exit_reasons": exit_reasons,
        "diagnostics": frame_to_rows(result.diagnostics),
    }


def run_pairs_sensitivity_request(
    request: schemas.PairsResearchRequest,
) -> dict[str, Any]:
    method_params = _builder_defaults(request.method)
    method_params.update(_coerce_pairs_params(request.method, request.params))
    base_kwargs = {
        "ticker_a": request.ticker_a,
        "ticker_b": request.ticker_b,
        "start_date": request.start,
        "end_date": request.end,
        **_pairs_assumptions(request),
        **method_params,
    }
    rows, recommended = run_parameter_sensitivity(
        METHOD_NAMES[request.method], base_kwargs
    )
    return {
        "rows": frame_to_rows(rows),
        "recommended_params": to_jsonable(
            {
                name: value
                for name, value in recommended.items()
                if name in method_params
            }
        ),
    }


_DISCOVERY_KALMAN_KEYS = {
    "warmup_window": "kalman_warmup_window",
    "state_noise": "kalman_state_noise",
    "observation_noise_scale": "kalman_observation_noise_scale",
    "zscore_window": "kalman_zscore_window",
}


def _discovery_kwargs(method: str, params: dict[str, Any]) -> dict[str, Any]:
    """Pick the params discover_pairs understands; builder-only params are ignored."""
    accepted = set(inspect.signature(discover_pairs).parameters) - {
        "tickers",
        "start_date",
        "end_date",
        "method",
        "formation_years",
        "top_n",
    }
    kwargs = {name: value for name, value in params.items() if name in accepted}
    if method == "kalman":
        for source, target in _DISCOVERY_KALMAN_KEYS.items():
            if source in params:
                kwargs[target] = params[source]
    return kwargs


def _usable_tickers(tickers: list[str], start: str, end: str) -> list[str]:
    """Drop tickers whose download fails, so one bad symbol does not sink a universe."""
    usable: list[str] = []
    last_error: Exception | None = None
    for ticker in tickers:
        try:
            cache.download_data(ticker, start, end)
        except cache.MarketDataError as error:
            last_error = error
            continue
        usable.append(ticker)
    if len(usable) < 2:
        raise cache.MarketDataError(
            "Fewer than two tickers could be downloaded"
            + (f" (last error: {last_error})" if last_error else ".")
        )
    return usable


def _selection_window(request: schemas.PairsUniverseRequest) -> tuple[str, str]:
    start = pd.Timestamp(request.start_date)
    return to_date_string(start), to_date_string(
        start + pd.DateOffset(years=request.formation_years)
    )


def _universe_params(request: schemas.PairsUniverseRequest) -> dict[str, Any]:
    discovery_defaults = {
        name: parameter.default
        for name, parameter in inspect.signature(discover_pairs).parameters.items()
        if parameter.default is not inspect.Parameter.empty and name != "top_n"
    }
    params = _coerce_pairs_params(
        request.method, request.params, extra_defaults=discovery_defaults
    )
    params.pop("formation_years", None)  # set by the body field
    params.pop("trading_start", None)  # the portfolio sets it from the selection window
    return params


def run_pairs_discover_request(request: schemas.PairsUniverseRequest) -> dict[str, Any]:
    params = _universe_params(request)
    tickers = _usable_tickers(request.tickers, request.start, request.end)
    rows = discover_pairs(
        tickers=tickers,
        start_date=request.start,
        end_date=request.end,
        method=METHOD_NAMES[request.method],
        formation_years=request.formation_years,
        top_n=request.top_n or 10,
        **_discovery_kwargs(request.method, params),
    )
    selection_start, selection_end = _selection_window(request)
    return {
        "selection_start": selection_start,
        "selection_end": selection_end,
        "rows": frame_to_rows(rows),
    }


def run_pairs_portfolio_request(
    request: schemas.PairsUniverseRequest,
) -> dict[str, Any]:
    params = _universe_params(request)
    builder_names = set(_builder_defaults(request.method))
    method_kwargs = {
        name: value for name, value in params.items() if name in builder_names
    }
    method_kwargs.update(
        transaction_cost_bps=request.transaction_cost_bps,
        borrow_fee=request.borrow_fee,
    )
    tickers = _usable_tickers(request.tickers, request.start, request.end)

    result = build_pairs_portfolio(
        tickers=tickers,
        start_date=request.start,
        end_date=request.end,
        method=METHOD_NAMES[request.method],
        top_n=request.top_n or 5,
        formation_years=request.formation_years,
        method_kwargs=method_kwargs,
        initial_capital=request.initial_capital,
        risk_free_rate=request.risk_free_rate,
        cash_rate=request.cash_rate,
    )

    portfolio = result.portfolio
    series_columns = ["portfolio_equity", "portfolio_drawdown"] + [
        column for column in portfolio.columns if str(column).startswith("equity::")
    ]
    return {
        "selection_start": to_date_string(result.selection_start),
        "selection_end": to_date_string(result.selection_end),
        "discovery": frame_to_rows(result.discovery),
        "pair_summary": frame_to_rows(result.pair_summary),
        "metrics": metrics_to_json(
            {
                **result.portfolio_metrics,
                "final_value": portfolio["portfolio_equity"].iloc[-1],
            }
        ),
        "average_pair_correlation": clean_float(result.average_pair_correlation),
        "series": to_timeseries(portfolio, series_columns),
    }


__all__ = [
    "get_meta",
    "run_backtest_request",
    "run_compare_request",
    "run_optimize_request",
    "run_pairs_discover_request",
    "run_pairs_portfolio_request",
    "run_pairs_research_request",
    "run_pairs_sensitivity_request",
    "run_validate_split_request",
    "run_walk_forward_request",
]
