from comparison import (
    compare_all_strategies,
    get_comparison_leaders,
)


def main() -> None:
    comparison = compare_all_strategies(
        ticker="AAPL",
        start_date="2020-01-01",
        end_date="2026-01-01",
        initial_capital=10_000,
        transaction_cost_bps=10,
        risk_free_rate=0.0,
    )

    display_table = comparison.summary.copy()

    display_table["final_value"] = display_table[
        "final_value"
    ].map(lambda value: f"${value:,.2f}")

    percentage_columns = [
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    ]

    for column in percentage_columns:
        display_table[column] = display_table[column].map(
            lambda value: f"{value:.2%}"
        )

    display_table["sharpe_ratio"] = display_table[
        "sharpe_ratio"
    ].map(lambda value: f"{value:.2f}")

    print(display_table.to_string(index=False))

    leaders = get_comparison_leaders(
        comparison.summary
    )

    print("\nComparison leaders")
    print(
        f"Highest return: "
        f"{leaders['highest_return']}"
    )
    print(
        f"Highest Sharpe ratio: "
        f"{leaders['highest_sharpe']}"
    )
    print(
        f"Lowest volatility: "
        f"{leaders['lowest_volatility']}"
    )
    print(
        f"Smallest drawdown: "
        f"{leaders['smallest_drawdown']}"
    )
    print(
        f"Most active: "
        f"{leaders['most_active']}"
    )
    print(
        f"Least active: "
        f"{leaders['least_active']}"
    )


if __name__ == "__main__":
    main()