from dataclasses import dataclass
from typing import Any

import pandas as pd

from backtester import (
    prepare_market_data,
    run_strategy_on_data,
)
from metrics import calculate_performance_metrics
from optimization import (
    OptimizationObjective,
    calculate_optimization_gain,
    calculate_optimization_robustness,
    optimize_strategy,
)
from strategies import (
    STRATEGIES,
    STRATEGY_METADATA,
    get_default_parameters,
    get_optimization_grid,
)


@dataclass
class ComparisonResults:
    """Store the strategy ranking table and detailed backtests."""

    summary: pd.DataFrame
    strategy_results: dict[str, pd.DataFrame]
    benchmark_metrics: dict[str, float]
    use_optimized_parameters: bool = False
    optimization_objective: OptimizationObjective | None = None
    raw_optimization_combinations: int = 0
    valid_optimization_evaluations: int = 0


def _count_raw_grid_combinations(
    parameter_grid: dict[str, list[Any]],
) -> int:
    """Return the Cartesian size of one discrete parameter grid."""
    combinations = 1

    for values in parameter_grid.values():
        combinations *= len(values)

    return combinations


def _format_parameter_value(
    parameter_name: str,
    value: Any,
) -> str:
    """Format one strategy parameter for compact comparison-table display."""
    if isinstance(value, float):
        return f"{value:g}"

    return str(value)


def _format_parameters(
    parameters: dict[str, Any],
) -> str:
    """Create a compact, deterministic parameter description."""
    return " | ".join(
        f"{parameter_name}={_format_parameter_value(parameter_name, value)}"
        for parameter_name, value in parameters.items()
    )


def calculate_optimized_comparison_workload() -> tuple[int, dict[str, int]]:
    """
    Calculate the raw predefined-grid workload for all registered strategies.

    Raw combination counts are intentionally calculated before structural
    validation. The actual number of evaluated combinations may therefore be
    smaller for strategies whose grids contain invalid parameter relationships.
    """
    strategy_counts: dict[str, int] = {}

    for strategy_name in STRATEGIES:
        strategy_counts[strategy_name] = _count_raw_grid_combinations(
            get_optimization_grid(strategy_name)
        )

    return sum(strategy_counts.values()), strategy_counts


def compare_all_strategies(
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    risk_free_rate: float = 0.0,
    use_optimized_parameters: bool = False,
    optimization_objective: OptimizationObjective = "sharpe_ratio",
) -> ComparisonResults:
    """
    Run every registered strategy on the same market data.

    When use_optimized_parameters is enabled, every active strategy is first
    optimized independently on its predefined research grid using the same
    in-sample period and objective. This mode is deliberately bounded to the
    predefined grids; Custom and Coarse-to-Fine searches remain Optimization
    Lab tools because applying them automatically across every strategy would
    materially increase both computational load and selection bias.
    """
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    strategy_results: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict[str, Any]] = []

    benchmark_results: pd.DataFrame | None = None
    raw_optimization_combinations = 0
    valid_optimization_evaluations = 0

    for strategy_name in STRATEGIES:
        default_parameters = get_default_parameters(strategy_name)
        parameters = default_parameters

        optimization_evaluations = 0
        default_objective_value = float("nan")
        optimized_objective_value = float("nan")
        optimization_gain = float("nan")
        optimization_robustness = "Not optimized"
        robust_candidate_parameters = "Not optimized"

        if use_optimized_parameters:
            parameter_grid = get_optimization_grid(strategy_name)
            raw_optimization_combinations += _count_raw_grid_combinations(
                parameter_grid
            )

            optimization_result = optimize_strategy(
                data=market_data,
                strategy_name=strategy_name,
                parameter_grid=parameter_grid,
                objective=optimization_objective,
                initial_capital=initial_capital,
                transaction_cost_bps=transaction_cost_bps,
                risk_free_rate=risk_free_rate,
            )

            parameters = optimization_result.best_parameters
            optimization_evaluations = len(optimization_result.results)
            valid_optimization_evaluations += optimization_evaluations

            default_objective_value = float(
                optimization_result.default_metrics[
                    optimization_objective
                ]
            )
            optimized_objective_value = float(
                optimization_result.best_metrics[
                    optimization_objective
                ]
            )
            optimization_gain = calculate_optimization_gain(
                optimized_value=optimized_objective_value,
                default_value=default_objective_value,
                objective=optimization_objective,
            )

            robustness = calculate_optimization_robustness(
                optimization_result
            )
            optimization_robustness = robustness.robustness_label
            robust_candidate_parameters = _format_parameters(
                robustness.robust_candidate_parameters
            )

        results = run_strategy_on_data(
            data=market_data,
            strategy_name=strategy_name,
            strategy_parameters=parameters,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps,
        )

        metrics = calculate_performance_metrics(
            returns=results["strategy_return"],
            equity=results["strategy_equity"],
            risk_free_rate=risk_free_rate,
            initial_value=initial_capital,
        )

        strategy_results[strategy_name] = results
        metadata = STRATEGY_METADATA[strategy_name]

        position_changes = (
            results["position"]
            .diff()
            .abs()
            .fillna(results["position"].abs())
        )

        number_of_position_changes = int(
            (position_changes > 0).sum()
        )
        total_turnover = float(position_changes.sum())
        average_exposure = float(
            results["position"].astype(float).mean()
        )

        summary_rows.append(
            {
                "strategy_key": strategy_name,
                "strategy": metadata["display_name"],
                "family": metadata["family"],
                "features": ", ".join(
                    metadata.get("features", [])
                ),
                "parameters": _format_parameters(parameters),
                "optimization_evaluations": optimization_evaluations,
                "default_objective": default_objective_value,
                "optimized_objective": optimized_objective_value,
                "optimization_gain": optimization_gain,
                "optimization_robustness": optimization_robustness,
                "robust_candidate_parameters": robust_candidate_parameters,
                "final_value": results[
                    "strategy_equity"
                ].iloc[-1],
                "total_return": metrics["total_return"],
                "cagr": metrics["cagr"],
                "annualized_volatility": metrics[
                    "annualized_volatility"
                ],
                "sharpe_ratio": metrics["sharpe_ratio"],
                "max_drawdown": metrics["max_drawdown"],
                "trades": number_of_position_changes,
                "turnover": total_turnover,
                "average_exposure": average_exposure,
            }
        )

        if benchmark_results is None:
            benchmark_results = results

    if benchmark_results is None:
        raise ValueError(
            "At least one registered strategy is required for comparison."
        )

    benchmark_equity = benchmark_results["buy_hold_equity"]

    benchmark_metrics = calculate_performance_metrics(
        returns=benchmark_results["buy_hold_return"],
        equity=benchmark_equity,
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    benchmark_rebalancing_days = int(
        (benchmark_results["buy_hold_turnover"] > 0).sum()
    )
    benchmark_turnover = float(
        benchmark_results["buy_hold_turnover"].sum()
    )

    summary_rows.append(
        {
            "strategy_key": "buy_and_hold",
            "strategy": "Buy and Hold",
            "family": "Benchmark",
            "features": "",
            "parameters": "Not applicable",
            "optimization_evaluations": 0,
            "default_objective": float("nan"),
            "optimized_objective": float("nan"),
            "optimization_gain": float("nan"),
            "optimization_robustness": "Not applicable",
            "robust_candidate_parameters": "Not applicable",
            "final_value": benchmark_equity.iloc[-1],
            "total_return": benchmark_metrics["total_return"],
            "cagr": benchmark_metrics["cagr"],
            "annualized_volatility": benchmark_metrics[
                "annualized_volatility"
            ],
            "sharpe_ratio": benchmark_metrics["sharpe_ratio"],
            "max_drawdown": benchmark_metrics["max_drawdown"],
            "trades": benchmark_rebalancing_days,
            "turnover": benchmark_turnover,
            "average_exposure": 1.0,
        }
    )

    summary = pd.DataFrame(summary_rows)
    summary = add_strategy_rankings(summary)
    summary = summary.sort_values(
        by="sharpe_rank",
        ascending=True,
    ).reset_index(drop=True)

    return ComparisonResults(
        summary=summary,
        strategy_results=strategy_results,
        benchmark_metrics=benchmark_metrics,
        use_optimized_parameters=use_optimized_parameters,
        optimization_objective=(
            optimization_objective
            if use_optimized_parameters
            else None
        ),
        raw_optimization_combinations=raw_optimization_combinations,
        valid_optimization_evaluations=valid_optimization_evaluations,
    )


def add_strategy_rankings(
    summary: pd.DataFrame,
) -> pd.DataFrame:
    """Add rankings for return, risk-adjusted return, volatility, and drawdown."""
    result = summary.copy()

    result["return_rank"] = (
        result["total_return"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    result["cagr_rank"] = (
        result["cagr"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    result["sharpe_rank"] = (
        result["sharpe_ratio"]
        .rank(method="min", ascending=False)
        .astype(int)
    )
    result["volatility_rank"] = (
        result["annualized_volatility"]
        .rank(method="min", ascending=True)
        .astype(int)
    )
    result["drawdown_rank"] = (
        result["max_drawdown"]
        .rank(method="min", ascending=False)
        .astype(int)
    )

    return result


def get_comparison_leaders(
    summary: pd.DataFrame,
) -> dict[str, str]:
    """Identify the leading strategy for each main metric."""
    highest_return_row = summary.loc[
        summary["total_return"].idxmax()
    ]
    highest_sharpe_row = summary.loc[
        summary["sharpe_ratio"].idxmax()
    ]
    lowest_volatility_row = summary.loc[
        summary["annualized_volatility"].idxmin()
    ]
    smallest_drawdown_row = summary.loc[
        summary["max_drawdown"].idxmax()
    ]

    strategy_only = summary[
        summary["family"] != "Benchmark"
    ]

    highest_turnover_row = strategy_only.loc[
        strategy_only["turnover"].idxmax()
    ]
    lowest_turnover_row = strategy_only.loc[
        strategy_only["turnover"].idxmin()
    ]
    most_rebalancing_row = strategy_only.loc[
        strategy_only["trades"].idxmax()
    ]

    return {
        "highest_return": str(highest_return_row["strategy"]),
        "highest_sharpe": str(highest_sharpe_row["strategy"]),
        "lowest_volatility": str(
            lowest_volatility_row["strategy"]
        ),
        "smallest_drawdown": str(
            smallest_drawdown_row["strategy"]
        ),
        "highest_turnover": str(
            highest_turnover_row["strategy"]
        ),
        "lowest_turnover": str(
            lowest_turnover_row["strategy"]
        ),
        "most_rebalancing": str(
            most_rebalancing_row["strategy"]
        ),
        # Backward-compatible aliases retained so any external
        # code using the old keys does not break unexpectedly.
        "most_active": str(
            highest_turnover_row["strategy"]
        ),
        "least_active": str(
            lowest_turnover_row["strategy"]
        ),
    }