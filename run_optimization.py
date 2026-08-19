import plotly.express as px

from backtester import prepare_market_data
from optimization import (
    calculate_optimization_gain,
    calculate_relative_optimization_gain,
    create_parameter_sensitivity_table,
    optimize_strategy,
)


def main() -> None:
    objective = "sharpe_ratio"

    data = prepare_market_data(
        ticker="AAPL",
        start_date="2020-01-01",
        end_date="2026-01-01",
    )

    result = optimize_strategy(
        data=data,
        strategy_name="donchian",
        objective=objective,
        initial_capital=10_000,
        transaction_cost_bps=10,
        risk_free_rate=0.0,
    )

    print("\nBest parameters")
    print(result.best_parameters)

    print("\nBest metrics")
    for metric_name, value in result.best_metrics.items():
        print(f"{metric_name}: {value}")

    print("\nDefault parameters")
    print(result.default_parameters)

    print("\nDefault metrics")
    for metric_name, value in result.default_metrics.items():
        print(f"{metric_name}: {value}")

    optimized_objective = result.best_metrics[objective]
    default_objective = result.default_metrics[objective]

    optimization_gain = calculate_optimization_gain(
        optimized_value=optimized_objective,
        default_value=default_objective,
        objective=objective,
    )

    relative_gain = calculate_relative_optimization_gain(
        optimized_value=optimized_objective,
        default_value=default_objective,
        objective=objective,
    )

    print("\nOptimization gain")
    print(f"Objective: {objective}")
    print(f"Default value: {default_objective:.4f}")
    print(f"Optimized value: {optimized_objective:.4f}")
    print(f"Absolute improvement: {optimization_gain:+.4f}")
    print(f"Relative improvement: {relative_gain:+.2%}")

    print("\nTop 10 parameter combinations")

    columns_to_display = [
        "entry_window",
        "exit_window",
        "final_value",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "rebalancing_days",
        "turnover",
    ]

    print(
        result.results[
            columns_to_display
        ]
        .head(10)
        .to_string(index=False)
    )

    table = create_parameter_sensitivity_table(
        results=result.results,
        row_parameter="entry_window",
        column_parameter="exit_window",
        metric=objective,
    )

    print("\nSharpe-ratio sensitivity table")
    print(
        table.to_string(
            float_format=lambda value: f"{value:.3f}"
        )
    )

    heatmap = px.imshow(
        table,
        text_auto=True,
        aspect="auto",
        labels={
            "x": "Exit window",
            "y": "Entry window",
            "color": "Sharpe ratio",
        },
        title=(
            "AAPL Donchian Parameter Sensitivity "
            "— Sharpe Ratio"
        ),
    )

    heatmap.update_traces(
        texttemplate="%{z:.2f}"
    )

    heatmap.show()


if __name__ == "__main__":
    main()