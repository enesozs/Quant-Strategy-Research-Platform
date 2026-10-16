from dataclasses import dataclass
from itertools import product
from typing import Any, Literal

import numpy as np
import pandas as pd

from backtester import run_strategy_on_window
from metrics import (
    calculate_deflated_sharpe_ratio,
    calculate_performance_metrics,
    calculate_probabilistic_sharpe_ratio,
)
from strategies import (
    STRATEGY_METADATA,
    get_default_parameters,
    get_lookback_observations,
    get_optimization_grid,
)

OptimizationObjective = Literal[
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "max_drawdown",
    "calmar_ratio",
]


@dataclass
class OptimizationResults:
    """Store a complete parameter-grid optimization result."""

    strategy_name: str
    objective: OptimizationObjective
    results: pd.DataFrame
    best_parameters: dict[str, Any]
    best_metrics: dict[str, float]
    default_parameters: dict[str, Any]
    default_metrics: dict[str, float]
    # First date every candidate is scored on. Earlier rows only warm up
    # indicators, so short and long lookbacks are compared on equal terms.
    evaluation_start: pd.Timestamp | None = None
    # Probability that the raw optimum's Sharpe ratio is above zero, before
    # (probabilistic) and after (deflated) accounting for the number of
    # configurations tried. NaN when the optimum never traded.
    probabilistic_sharpe_ratio: float = float("nan")
    deflated_sharpe_ratio: float = float("nan")


@dataclass
class CoarseToFineOptimizationResults:
    """Store both stages of a coarse-to-fine optimization run."""

    broad_result: OptimizationResults
    refined_result: OptimizationResults
    broad_parameter_grid: dict[str, list[Any]]
    refined_parameter_grid: dict[str, list[Any]]


def _validate_parameter_grid(
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
) -> None:
    """Validate parameter names and ensure every grid dimension is non-empty."""
    if strategy_name not in STRATEGY_METADATA:
        raise ValueError(
            f"No metadata exists for strategy '{strategy_name}'."
        )

    valid_parameter_names = set(
        STRATEGY_METADATA[strategy_name]["parameters"]
    )

    unknown_parameters = set(parameter_grid) - valid_parameter_names

    if unknown_parameters:
        unknown = ", ".join(sorted(unknown_parameters))
        raise ValueError(
            f"Unknown optimization parameter(s) for strategy "
            f"'{strategy_name}': {unknown}."
        )

    if not parameter_grid:
        raise ValueError("The parameter grid cannot be empty.")

    for parameter_name, values in parameter_grid.items():
        if not values:
            raise ValueError(
                f"Optimization values for '{parameter_name}' "
                "cannot be empty."
            )


def _is_valid_parameter_combination(
    strategy_name: str,
    parameters: dict[str, Any],
) -> bool:
    """
    Reject structurally invalid combinations before running a backtest.

    The checks mirror relationships already enforced by the strategy
    implementations, but applying them here prevents avoidable failed runs
    during a large grid search.
    """
    if strategy_name in {"moving_average", "ema", "macd"}:
        fast_window = parameters.get("fast_window")
        slow_window = parameters.get("slow_window")

        if (
            fast_window is not None
            and slow_window is not None
            and fast_window >= slow_window
        ):
            return False

    if strategy_name in {"rsi", "stochastic", "cci"}:
        entry_threshold = parameters.get("entry_threshold")
        exit_threshold = parameters.get("exit_threshold")

        if (
            entry_threshold is not None
            and exit_threshold is not None
            and entry_threshold >= exit_threshold
        ):
            return False

    if strategy_name == "donchian":
        entry_window = parameters.get("entry_window")
        exit_window = parameters.get("exit_window")

        if (
            entry_window is not None
            and exit_window is not None
            and exit_window >= entry_window
        ):
            return False

    return True


def _objective_is_maximized(
    objective: OptimizationObjective,
) -> bool:
    """Return whether larger values represent better objective performance."""
    return objective != "annualized_volatility"


def _calculate_activity_statistics(
    results: pd.DataFrame,
) -> tuple[int, float]:
    """Calculate rebalancing-day count and cumulative one-way turnover."""
    turnover = results["trade"].astype(float)

    rebalancing_days = int((turnover > 0).sum())
    cumulative_turnover = float(turnover.sum())

    return rebalancing_days, cumulative_turnover


def resolve_evaluation_start(
    data: pd.DataFrame,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
) -> pd.Timestamp:
    """
    Return the first date on which every grid candidate has warm indicators.

    Scoring each candidate from the start of the sample would leave long
    lookbacks in cash for much of the window, rewarding them under
    drawdown/volatility objectives and penalising them under return/Sharpe.
    A common burn-in removes that bias.
    """
    burn_in = max(
        get_lookback_observations(
            strategy_name,
            {name: max(values) for name, values in parameter_grid.items()},
        ),
        get_lookback_observations(strategy_name),
    )

    minimum_scored_observations = 20

    if len(data) < burn_in + minimum_scored_observations:
        raise ValueError(
            f"The sample has {len(data)} observations, but the longest "
            f"lookback in the grid needs {burn_in} for warmup plus "
            f"{minimum_scored_observations} to score. Use a longer sample "
            "or shorter windows."
        )

    return pd.Timestamp(data.index[burn_in])


def _evaluate_parameters(
    data: pd.DataFrame,
    strategy_name: str,
    parameters: dict[str, Any],
    initial_capital: float,
    transaction_cost_bps: float,
    cash_rate: float,
    risk_free_rate: float,
    evaluation_start: pd.Timestamp,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """Run one parameter combination and calculate its research metrics."""
    results = run_strategy_on_window(
        data=data,
        strategy_name=strategy_name,
        evaluation_start=evaluation_start,
        strategy_parameters=parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
    )

    metrics = calculate_performance_metrics(
        returns=results["strategy_return"],
        equity=results["strategy_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    return results, metrics


def optimize_strategy(
    data: pd.DataFrame,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]] | None = None,
    objective: OptimizationObjective = "sharpe_ratio",
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
    risk_free_rate: float = 0.0,
    evaluation_start: pd.Timestamp | None = None,
) -> OptimizationResults:
    """
    Exhaustively evaluate a strategy over a discrete parameter grid.

    This is an in-sample research tool. A high-performing parameter set from
    this function should not be treated as validated until it is evaluated on
    unseen data or with walk-forward analysis.

    Every candidate is scored from the same evaluation_start. When it is not
    supplied, it is placed after the longest lookback in the grid.
    """
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")

    if transaction_cost_bps < 0:
        raise ValueError("Transaction costs cannot be negative.")

    if risk_free_rate <= -1:
        raise ValueError(
            "The annual risk-free rate must be greater than -100%."
        )

    grid = (
        parameter_grid
        if parameter_grid is not None
        else get_optimization_grid(strategy_name)
    )

    _validate_parameter_grid(
        strategy_name=strategy_name,
        parameter_grid=grid,
    )

    default_parameters = get_default_parameters(strategy_name)

    if evaluation_start is None:
        evaluation_start = resolve_evaluation_start(
            data=data,
            strategy_name=strategy_name,
            parameter_grid=grid,
        )
    else:
        evaluation_start = pd.Timestamp(evaluation_start)

    default_results, default_metrics = _evaluate_parameters(
        data=data,
        strategy_name=strategy_name,
        parameters=default_parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
        evaluation_start=evaluation_start,
    )

    default_rebalancing_days, default_turnover = (
        _calculate_activity_statistics(default_results)
    )

    default_metrics = {
        **default_metrics,
        "final_value": float(
            default_results["strategy_equity"].iloc[-1]
        ),
        "rebalancing_days": float(default_rebalancing_days),
        "turnover": default_turnover,
    }

    parameter_names = list(grid)
    parameter_value_lists = [grid[name] for name in parameter_names]

    rows: list[dict[str, Any]] = []

    for values in product(*parameter_value_lists):
        parameters = {
            parameter_name: value
            for parameter_name, value in zip(
                parameter_names,
                values,
                strict=True,
            )
        }

        candidate_parameters = {
            **default_parameters,
            **parameters,
        }

        if not _is_valid_parameter_combination(
            strategy_name=strategy_name,
            parameters=candidate_parameters,
        ):
            continue

        results, metrics = _evaluate_parameters(
            data=data,
            strategy_name=strategy_name,
            parameters=candidate_parameters,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps,
            cash_rate=cash_rate,
            risk_free_rate=risk_free_rate,
            evaluation_start=evaluation_start,
        )

        rebalancing_days, turnover = (
            _calculate_activity_statistics(results)
        )

        row: dict[str, Any] = {
            **candidate_parameters,
            "final_value": float(
                results["strategy_equity"].iloc[-1]
            ),
            "total_return": metrics["total_return"],
            "cagr": metrics["cagr"],
            "annualized_volatility": metrics[
                "annualized_volatility"
            ],
            "sharpe_ratio": metrics["sharpe_ratio"],
            "max_drawdown": metrics["max_drawdown"],
            "calmar_ratio": metrics["calmar_ratio"],
            "rebalancing_days": rebalancing_days,
            "turnover": turnover,
        }

        rows.append(row)

    if not rows:
        raise ValueError(
            "No valid parameter combinations remained after validation."
        )

    optimization_table = pd.DataFrame(rows)

    objective_values = pd.to_numeric(
        optimization_table[objective],
        errors="coerce",
    ).replace([np.inf, -np.inf], np.nan)

    if not objective_values.notna().any():
        raise ValueError(
            "No finite objective values were produced by the "
            "tested parameter combinations."
        )

    ascending = not _objective_is_maximized(objective)

    # A stable sort with turnover as the tie-breaker makes the selected
    # optimum deterministic when several combinations score identically.
    optimization_table = optimization_table.sort_values(
        by=[objective, "turnover"],
        ascending=[ascending, True],
        na_position="last",
        kind="mergesort",
    ).reset_index(drop=True)

    best_row = optimization_table.iloc[0]

    best_parameters: dict[str, int | float] = {}

    for parameter_name in grid:
        value = best_row[parameter_name]

        default_value = default_parameters[
            parameter_name
        ]

        if isinstance(default_value, int):
            best_parameters[parameter_name] = int(value)
        else:
            best_parameters[parameter_name] = float(value)

    best_metrics = {
        "final_value": float(best_row["final_value"]),
        "total_return": float(best_row["total_return"]),
        "cagr": float(best_row["cagr"]),
        "annualized_volatility": float(
            best_row["annualized_volatility"]
        ),
        "sharpe_ratio": float(best_row["sharpe_ratio"]),
        "max_drawdown": float(best_row["max_drawdown"]),
        "calmar_ratio": float(best_row["calmar_ratio"]),
        "rebalancing_days": float(
            best_row["rebalancing_days"]
        ),
        "turnover": float(best_row["turnover"]),
    }

    best_results, _ = _evaluate_parameters(
        data=data,
        strategy_name=strategy_name,
        parameters={**default_parameters, **best_parameters},
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
        evaluation_start=evaluation_start,
    )
    best_returns = best_results["strategy_return"]

    return OptimizationResults(
        strategy_name=strategy_name,
        objective=objective,
        results=optimization_table,
        best_parameters=best_parameters,
        best_metrics=best_metrics,
        default_parameters=default_parameters,
        default_metrics=default_metrics,
        evaluation_start=evaluation_start,
        probabilistic_sharpe_ratio=calculate_probabilistic_sharpe_ratio(
            best_returns,
            risk_free_rate=risk_free_rate,
        ),
        deflated_sharpe_ratio=calculate_deflated_sharpe_ratio(
            best_returns,
            trial_sharpes=optimization_table["sharpe_ratio"],
            risk_free_rate=risk_free_rate,
        ),
    )


def _create_refined_parameter_values(
    strategy_name: str,
    parameter_name: str,
    broad_values: list[Any],
    best_value: Any,
    refinement_points: int,
) -> list[Any]:
    """Create a denser local grid around one broad-search optimum."""
    if refinement_points < 3:
        raise ValueError(
            "Coarse-to-fine refinement requires at least 3 points "
            "per parameter."
        )

    if not broad_values:
        raise ValueError(
            f"Broad values for '{parameter_name}' cannot be empty."
        )

    specification = STRATEGY_METADATA[
        strategy_name
    ]["parameters"][parameter_name]

    parameter_type = str(specification["type"])
    lower_bound = float(specification["min"])
    upper_bound = float(specification["max"])

    numeric_values = sorted(
        {float(value) for value in broad_values}
    )
    best_numeric = float(best_value)

    if len(numeric_values) == 1:
        local_lower = best_numeric
        local_upper = best_numeric
    else:
        nearest_index = min(
            range(len(numeric_values)),
            key=lambda index: abs(
                numeric_values[index] - best_numeric
            ),
        )

        if nearest_index == 0:
            local_lower = numeric_values[0]
            local_upper = numeric_values[1]
        elif nearest_index == len(numeric_values) - 1:
            local_lower = numeric_values[-2]
            local_upper = numeric_values[-1]
        else:
            local_lower = numeric_values[nearest_index - 1]
            local_upper = numeric_values[nearest_index + 1]

    local_lower = max(local_lower, lower_bound)
    local_upper = min(local_upper, upper_bound)

    if local_lower > local_upper:
        local_lower, local_upper = local_upper, local_lower

    if abs(local_upper - local_lower) <= 1e-15:
        candidate_values = [best_numeric]
    else:
        candidate_values = np.linspace(
            local_lower,
            local_upper,
            num=refinement_points,
        ).tolist()

    candidate_values.append(best_numeric)

    if parameter_type == "int":
        refined_values = sorted(
            {
                int(round(value))
                for value in candidate_values
                if lower_bound
                <= int(round(value))
                <= upper_bound
            }
        )
    else:
        refined_values = sorted(
            {
                round(float(value), 12)
                for value in candidate_values
                if lower_bound <= float(value) <= upper_bound
            }
        )

    if not refined_values:
        raise ValueError(
            f"No refined values could be created for "
            f"'{parameter_name}'."
        )

    return refined_values


def create_refined_parameter_grid(
    strategy_name: str,
    broad_parameter_grid: dict[str, list[Any]],
    broad_best_parameters: dict[str, Any],
    refinement_points: int = 5,
) -> dict[str, list[Any]]:
    """Build a local parameter grid around a broad-search optimum."""
    _validate_parameter_grid(
        strategy_name=strategy_name,
        parameter_grid=broad_parameter_grid,
    )

    refined_grid: dict[str, list[Any]] = {}

    for parameter_name, broad_values in (
        broad_parameter_grid.items()
    ):
        if parameter_name not in broad_best_parameters:
            raise ValueError(
                "The broad optimization result is missing "
                f"'{parameter_name}'."
            )

        refined_grid[parameter_name] = (
            _create_refined_parameter_values(
                strategy_name=strategy_name,
                parameter_name=parameter_name,
                broad_values=broad_values,
                best_value=broad_best_parameters[
                    parameter_name
                ],
                refinement_points=refinement_points,
            )
        )

    return refined_grid


def optimize_strategy_coarse_to_fine(
    data: pd.DataFrame,
    strategy_name: str,
    broad_parameter_grid: dict[str, list[Any]] | None = None,
    objective: OptimizationObjective = "sharpe_ratio",
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
    risk_free_rate: float = 0.0,
    refinement_points: int = 5,
) -> CoarseToFineOptimizationResults:
    """Run a broad grid search and then refine around its optimum."""
    broad_grid = (
        broad_parameter_grid
        if broad_parameter_grid is not None
        else get_optimization_grid(strategy_name)
    )

    broad_result = optimize_strategy(
        data=data,
        strategy_name=strategy_name,
        parameter_grid=broad_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
    )

    refined_grid = create_refined_parameter_grid(
        strategy_name=strategy_name,
        broad_parameter_grid=broad_grid,
        broad_best_parameters=broad_result.best_parameters,
        refinement_points=refinement_points,
    )

    refined_result = optimize_strategy(
        data=data,
        strategy_name=strategy_name,
        parameter_grid=refined_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
        evaluation_start=broad_result.evaluation_start,
    )

    return CoarseToFineOptimizationResults(
        broad_result=broad_result,
        refined_result=refined_result,
        broad_parameter_grid=broad_grid,
        refined_parameter_grid=refined_grid,
    )


def calculate_optimization_gain(
    optimized_value: float,
    default_value: float,
    objective: str,
) -> float:
    """
    Measure the improvement of the optimized result over the
    default-parameter result.

    For objectives where larger values are better, the gain is
    optimized minus default.

    For objectives where smaller values are better, such as
    volatility, the gain is default minus optimized.

    Maximum drawdown values are negative, so a less-negative
    optimized drawdown is considered an improvement.
    """
    if objective in {
        "sharpe_ratio",
        "total_return",
        "cagr",
        "max_drawdown",
        "calmar_ratio",
    }:
        return optimized_value - default_value

    if objective == "annualized_volatility":
        return default_value - optimized_value

    raise ValueError(
        f"Unsupported optimization objective '{objective}'."
    )


def calculate_relative_optimization_gain(
    optimized_value: float,
    default_value: float,
    objective: str,
) -> float:
    """
    Calculate optimization improvement relative to the
    magnitude of the default objective value.

    Returns NaN when the default value is zero.
    """
    absolute_gain = calculate_optimization_gain(
        optimized_value=optimized_value,
        default_value=default_value,
        objective=objective,
    )

    if default_value == 0:
        return np.nan

    return absolute_gain / abs(default_value)

def create_parameter_sensitivity_table(
    results: pd.DataFrame,
    row_parameter: str,
    column_parameter: str,
    metric: str,
) -> pd.DataFrame:
    """
    Convert grid-search results into a two-dimensional
    parameter-sensitivity table.

    Rows represent one strategy parameter, columns represent
    another, and cell values contain the selected performance
    metric.
    """
    required_columns = {
        row_parameter,
        column_parameter,
        metric,
    }

    missing_columns = required_columns.difference(
        results.columns
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            "Optimization results are missing required "
            f"columns: {missing_text}."
        )

    sensitivity_table = results.pivot(
        index=row_parameter,
        columns=column_parameter,
        values=metric,
    )

    sensitivity_table = sensitivity_table.sort_index(
        axis=0
    )

    sensitivity_table = sensitivity_table.sort_index(
        axis=1
    )

    return sensitivity_table


def create_parameter_sensitivity_profile(
    results: pd.DataFrame,
    parameter_name: str,
    metric: str,
) -> pd.DataFrame:
    """
    Summarize one parameter's relationship with an optimization metric.

    Each parameter value is evaluated across every valid combination in
    which it appears. The median is the primary sensitivity statistic because
    it is less influenced by one unusually strong combination of the other
    parameters than the maximum would be.
    """
    required_columns = {
        parameter_name,
        metric,
    }

    missing_columns = required_columns.difference(
        results.columns
    )

    if missing_columns:
        missing_text = ", ".join(
            sorted(missing_columns)
        )

        raise ValueError(
            "Optimization results are missing required "
            f"columns: {missing_text}."
        )

    clean_results = results[
        [parameter_name, metric]
    ].copy()

    clean_results[metric] = pd.to_numeric(
        clean_results[metric],
        errors="coerce",
    )

    clean_results = clean_results.replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna(subset=[metric])

    if clean_results.empty:
        raise ValueError(
            "No finite optimization results are available for "
            f"parameter '{parameter_name}' and metric '{metric}'."
        )

    best_aggregation = (
        "min"
        if metric == "annualized_volatility"
        else "max"
    )
    worst_aggregation = (
        "max"
        if metric == "annualized_volatility"
        else "min"
    )

    profile = (
        clean_results
        .groupby(parameter_name, dropna=False)[metric]
        .agg(
            median_objective="median",
            mean_objective="mean",
            best_observed=best_aggregation,
            worst_observed=worst_aggregation,
            combinations="count",
        )
        .reset_index()
        .sort_values(parameter_name)
        .reset_index(drop=True)
    )

    return profile


def create_parameter_sensitivity_summary(
    results: pd.DataFrame,
    parameter_names: list[str],
    metric: str,
    objective: OptimizationObjective,
) -> pd.DataFrame:
    """
    Rank parameters by the spread of their median objective values.

    A larger spread means the selected objective changes more as that
    parameter changes across the tested grid. This is a descriptive
    sensitivity measure, not a causal feature-importance estimate.
    """
    rows: list[dict[str, Any]] = []

    for parameter_name in parameter_names:
        profile = create_parameter_sensitivity_profile(
            results=results,
            parameter_name=parameter_name,
            metric=metric,
        )

        medians = profile["median_objective"].astype(float)

        if medians.empty:
            continue

        median_values = medians.to_numpy(dtype=float)

        if objective == "annualized_volatility":
            best_position = int(np.argmin(median_values))
            worst_position = int(np.argmax(median_values))
        else:
            best_position = int(np.argmax(median_values))
            worst_position = int(np.argmin(median_values))

        best_parameter_value = profile[parameter_name].iloc[
            best_position
        ]
        weakest_parameter_value = profile[parameter_name].iloc[
            worst_position
        ]

        rows.append(
            {
                "parameter": parameter_name,
                "sensitivity_spread": float(
                    median_values.max() - median_values.min()
                ),
                "best_parameter_value": best_parameter_value,
                "best_median_objective": float(
                    median_values[best_position]
                ),
                "weakest_parameter_value": weakest_parameter_value,
                "weakest_median_objective": float(
                    median_values[worst_position]
                ),
                "tested_values": int(len(profile)),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=[
                "parameter",
                "sensitivity_spread",
                "best_parameter_value",
                "best_median_objective",
                "weakest_parameter_value",
                "weakest_median_objective",
                "tested_values",
            ]
        )

    return (
        pd.DataFrame(rows)
        .sort_values(
            "sensitivity_spread",
            ascending=False,
        )
        .reset_index(drop=True)
    )

@dataclass
class OptimizationRobustnessDiagnostics:
    """Summarize in-sample parameter robustness around an optimum."""

    evaluated_combinations: int
    near_optimal_5_count: int
    near_optimal_5_share: float
    near_optimal_10_count: int
    near_optimal_10_share: float
    local_neighbor_count: int
    local_near_optimal_5_count: int
    local_near_optimal_5_share: float
    local_near_optimal_10_count: int
    local_near_optimal_10_share: float
    local_median_relative_degradation: float
    best_to_second_relative_gap: float
    boundary_parameters: list[str]
    robustness_label: str
    selection_risk_label: str
    robust_candidate_parameters: dict[str, Any]
    robust_candidate_objective: float
    robust_candidate_local_median_objective: float
    robust_candidate_relative_gap: float


# Smallest optimum magnitude used as the denominator of relative degradation.
RELATIVE_DEGRADATION_SCALE_FLOOR: dict[str, float] = {
    "sharpe_ratio": 0.5,
    "total_return": 0.05,
    "cagr": 0.02,
    "annualized_volatility": 0.02,
    "max_drawdown": 0.05,
    "calmar_ratio": 0.25,
}


def _calculate_relative_objective_degradation(
    values: np.ndarray,
    best_value: float,
    objective: OptimizationObjective,
) -> np.ndarray:
    """
    Return non-negative objective loss relative to the optimum.

    The scale has an absolute floor per objective. Without it, an optimum
    near zero (a Sharpe of 0.02, or a drawdown of 0% from a strategy that
    barely trades) turns negligible differences into huge relative losses,
    which makes the near-optimal shares and plateau labels meaningless.
    """
    scale = max(
        abs(best_value),
        RELATIVE_DEGRADATION_SCALE_FLOOR.get(objective, 1e-12),
    )

    if objective == "annualized_volatility":
        degradation = values - best_value
    else:
        degradation = best_value - values

    degradation = np.maximum(degradation, 0.0)

    return degradation / scale


def _get_local_parameter_neighborhood(
    results: pd.DataFrame,
    best_parameters: dict[str, Any],
) -> pd.DataFrame:
    """
    Keep combinations at the optimum or one tested grid step away.

    Neighborhoods are defined by tested-value order rather than numeric
    distance, so the method remains meaningful for irregular parameter grids.
    """
    local_results = results.copy()

    for parameter_name, best_value in best_parameters.items():
        if parameter_name not in local_results.columns:
            raise ValueError(
                "Optimization results are missing parameter column "
                f"'{parameter_name}'."
            )

        parameter_values = pd.to_numeric(
            results[parameter_name],
            errors="coerce",
        ).dropna()

        unique_values = sorted(
            {float(value) for value in parameter_values}
        )

        if not unique_values:
            continue

        best_numeric = float(best_value)
        best_index = min(
            range(len(unique_values)),
            key=lambda index: abs(
                unique_values[index] - best_numeric
            ),
        )

        lower_index = max(0, best_index - 1)
        upper_index = min(
            len(unique_values) - 1,
            best_index + 1,
        )

        allowed_values = unique_values[
            lower_index:upper_index + 1
        ]

        numeric_column = pd.to_numeric(
            local_results[parameter_name],
            errors="coerce",
        )

        local_results = local_results[
            numeric_column.isin(allowed_values)
        ]

    return local_results


def _coerce_parameter_set_like_defaults(
    parameters: dict[str, Any],
    default_parameters: dict[str, Any],
) -> dict[str, Any]:
    """Convert candidate parameter values back to the strategy's native types."""
    coerced: dict[str, Any] = {}

    for parameter_name, value in parameters.items():
        default_value = default_parameters.get(parameter_name)

        if isinstance(default_value, int):
            coerced[parameter_name] = int(round(float(value)))
        elif isinstance(default_value, float):
            coerced[parameter_name] = float(value)
        else:
            coerced[parameter_name] = value

    return coerced


def _select_robust_candidate(
    optimization_result: OptimizationResults,
    clean_results: pd.DataFrame,
    relative_degradation: np.ndarray,
) -> tuple[dict[str, Any], float, float, float]:
    """
    Select a stability-oriented parameter set from the near-optimal region.

    Candidates must finish within 10% of the raw optimum. Each candidate is
    scored by the median objective value in its immediate tested-grid
    neighborhood. This favors a strong local plateau over an isolated spike.
    The raw optimum is retained whenever it is also the strongest local choice.
    """
    objective = optimization_result.objective
    candidate_mask = relative_degradation <= 0.10 + 1e-12
    candidates = clean_results.loc[candidate_mask].copy()

    if candidates.empty:
        return (
            dict(optimization_result.best_parameters),
            float(optimization_result.best_metrics[objective]),
            float(optimization_result.best_metrics[objective]),
            0.0,
        )

    parameter_names = list(optimization_result.best_parameters)

    best_candidate_parameters: dict[str, Any] | None = None
    best_candidate_objective = float("nan")
    best_candidate_local_median = float("nan")
    best_candidate_gap = float("nan")

    for _, candidate_row in candidates.iterrows():
        raw_parameters = {
            parameter_name: candidate_row[parameter_name]
            for parameter_name in parameter_names
        }
        candidate_parameters = _coerce_parameter_set_like_defaults(
            parameters=raw_parameters,
            default_parameters=optimization_result.default_parameters,
        )

        local_results = _get_local_parameter_neighborhood(
            results=clean_results,
            best_parameters=candidate_parameters,
        )
        local_values = pd.to_numeric(
            local_results[objective],
            errors="coerce",
        ).replace([np.inf, -np.inf], np.nan).dropna()

        if local_values.empty:
            continue

        local_median = float(local_values.median())
        candidate_objective = float(candidate_row[objective])
        candidate_gap = float(
            _calculate_relative_objective_degradation(
                values=np.array([candidate_objective], dtype=float),
                best_value=float(optimization_result.best_metrics[objective]),
                objective=objective,
            )[0]
        )

        if best_candidate_parameters is None:
            choose_candidate = True
        elif objective == "annualized_volatility":
            choose_candidate = (
                local_median < best_candidate_local_median - 1e-12
                or (
                    np.isclose(local_median, best_candidate_local_median)
                    and candidate_objective < best_candidate_objective
                )
            )
        else:
            choose_candidate = (
                local_median > best_candidate_local_median + 1e-12
                or (
                    np.isclose(local_median, best_candidate_local_median)
                    and candidate_objective > best_candidate_objective
                )
            )

        if choose_candidate:
            best_candidate_parameters = candidate_parameters
            best_candidate_objective = candidate_objective
            best_candidate_local_median = local_median
            best_candidate_gap = candidate_gap

    if best_candidate_parameters is None:
        return (
            dict(optimization_result.best_parameters),
            float(optimization_result.best_metrics[objective]),
            float(optimization_result.best_metrics[objective]),
            0.0,
        )

    return (
        best_candidate_parameters,
        best_candidate_objective,
        best_candidate_local_median,
        best_candidate_gap,
    )


def calculate_optimization_robustness(
    optimization_result: OptimizationResults,
) -> OptimizationRobustnessDiagnostics:
    """
    Diagnose how broad or narrow an in-sample parameter optimum appears.

    These diagnostics describe parameter stability inside the tested grid.
    They do not establish out-of-sample validity and cannot prove or disprove
    overfitting.
    """
    objective = optimization_result.objective
    results = optimization_result.results.copy()

    if objective not in results.columns:
        raise ValueError(
            f"Optimization results do not contain objective '{objective}'."
        )

    objective_values = pd.to_numeric(
        results[objective],
        errors="coerce",
    ).replace(
        [np.inf, -np.inf],
        np.nan,
    )

    finite_mask = objective_values.notna()
    clean_results = results.loc[finite_mask].copy()
    clean_values = objective_values.loc[
        finite_mask
    ].to_numpy(dtype=float)

    evaluated_count = int(len(clean_values))

    if evaluated_count == 0:
        raise ValueError(
            "No finite objective values are available for robustness "
            "analysis."
        )

    best_value = float(
        optimization_result.best_metrics[objective]
    )

    relative_degradation = (
        _calculate_relative_objective_degradation(
            values=clean_values,
            best_value=best_value,
            objective=objective,
        )
    )

    near_5_mask = relative_degradation <= 0.05 + 1e-12
    near_10_mask = relative_degradation <= 0.10 + 1e-12

    near_5_count = int(near_5_mask.sum())
    near_10_count = int(near_10_mask.sum())

    local_results = _get_local_parameter_neighborhood(
        results=clean_results,
        best_parameters=optimization_result.best_parameters,
    )

    local_values = pd.to_numeric(
        local_results[objective],
        errors="coerce",
    ).replace(
        [np.inf, -np.inf],
        np.nan,
    ).dropna().to_numpy(dtype=float)

    local_count = int(len(local_values))

    if local_count > 0:
        local_degradation = (
            _calculate_relative_objective_degradation(
                values=local_values,
                best_value=best_value,
                objective=objective,
            )
        )
        local_near_5_count = int(
            (local_degradation <= 0.05 + 1e-12).sum()
        )
        local_near_10_count = int(
            (local_degradation <= 0.10 + 1e-12).sum()
        )
        local_median_degradation = float(
            np.median(local_degradation)
        )
    else:
        local_near_5_count = 0
        local_near_10_count = 0
        local_median_degradation = np.nan

    local_near_5_share = (
        local_near_5_count / local_count
        if local_count > 0
        else np.nan
    )
    local_near_10_share = (
        local_near_10_count / local_count
        if local_count > 0
        else np.nan
    )

    sorted_degradation = np.sort(relative_degradation)
    if len(sorted_degradation) >= 2:
        second_best_relative_gap = float(
            sorted_degradation[1]
        )
    else:
        second_best_relative_gap = np.nan

    boundary_parameters: list[str] = []

    for parameter_name, best_parameter_value in (
        optimization_result.best_parameters.items()
    ):
        numeric_values = pd.to_numeric(
            clean_results[parameter_name],
            errors="coerce",
        ).dropna()

        if numeric_values.empty:
            continue

        minimum = float(numeric_values.min())
        maximum = float(numeric_values.max())
        best_numeric = float(best_parameter_value)

        if np.isclose(best_numeric, minimum) or np.isclose(
            best_numeric,
            maximum,
        ):
            boundary_parameters.append(parameter_name)

    near_10_share = near_10_count / evaluated_count
    near_5_share = near_5_count / evaluated_count

    if evaluated_count < 5 or local_count < 2:
        robustness_label = "Insufficient evidence"
        selection_risk_label = "Unclear"
    elif (
        local_near_5_share >= 0.60
        and near_10_share >= 0.10
        and local_median_degradation <= 0.05
    ):
        robustness_label = "Broad plateau"
        selection_risk_label = "Lower"
    elif (
        local_near_10_share >= 0.50
        and near_10_share >= 0.05
        and local_median_degradation <= 0.10
    ):
        robustness_label = "Moderate plateau"
        selection_risk_label = "Moderate"
    else:
        robustness_label = "Narrow peak"
        selection_risk_label = "Higher"

    if boundary_parameters and selection_risk_label == "Lower":
        selection_risk_label = "Moderate"

    (
        robust_candidate_parameters,
        robust_candidate_objective,
        robust_candidate_local_median_objective,
        robust_candidate_relative_gap,
    ) = _select_robust_candidate(
        optimization_result=optimization_result,
        clean_results=clean_results,
        relative_degradation=relative_degradation,
    )

    return OptimizationRobustnessDiagnostics(
        evaluated_combinations=evaluated_count,
        near_optimal_5_count=near_5_count,
        near_optimal_5_share=near_5_share,
        near_optimal_10_count=near_10_count,
        near_optimal_10_share=near_10_share,
        local_neighbor_count=local_count,
        local_near_optimal_5_count=local_near_5_count,
        local_near_optimal_5_share=float(local_near_5_share),
        local_near_optimal_10_count=local_near_10_count,
        local_near_optimal_10_share=float(local_near_10_share),
        local_median_relative_degradation=(
            local_median_degradation
        ),
        best_to_second_relative_gap=second_best_relative_gap,
        boundary_parameters=boundary_parameters,
        robustness_label=robustness_label,
        selection_risk_label=selection_risk_label,
        robust_candidate_parameters=robust_candidate_parameters,
        robust_candidate_objective=robust_candidate_objective,
        robust_candidate_local_median_objective=(
            robust_candidate_local_median_objective
        ),
        robust_candidate_relative_gap=robust_candidate_relative_gap,
    )