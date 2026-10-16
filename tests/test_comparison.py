import numpy as np
import pandas as pd

from comparison import (
    add_strategy_rankings,
    get_comparison_leaders,
)


def create_sample_summary() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "strategy": [
                "Strategy A",
                "Strategy B",
                "Strategy C",
            ],
            "family": [
                "Trend Following",
                "Benchmark",
                "Mean Reversion",
            ],
            "total_return": [
                0.50,
                0.80,
                0.30,
            ],
            "cagr": [
                0.10,
                0.15,
                0.07,
            ],
            "annualized_volatility": [
                0.20,
                0.35,
                0.12,
            ],
            "sharpe_ratio": [
                0.70,
                0.65,
                0.90,
            ],
            "max_drawdown": [
                -0.25,
                -0.40,
                -0.15,
            ],
            "trades": [
                20,
                1,
                10,
            ],
            "turnover": [
                8.0,
                1.0,
                12.0,
            ],
        }
    )


def test_add_strategy_rankings() -> None:
    summary = create_sample_summary()

    result = add_strategy_rankings(summary)

    strategy_c = result[
        result["strategy"] == "Strategy C"
    ].iloc[0]

    assert strategy_c["sharpe_rank"] == 1
    assert strategy_c["volatility_rank"] == 1
    assert strategy_c["drawdown_rank"] == 1


def test_get_comparison_leaders() -> None:
    summary = create_sample_summary()

    leaders = get_comparison_leaders(summary)

    assert leaders["highest_return"] == "Strategy B"
    assert leaders["highest_sharpe"] == "Strategy C"
    assert leaders["lowest_volatility"] == "Strategy C"
    assert leaders["smallest_drawdown"] == "Strategy C"
    assert leaders["highest_turnover"] == "Strategy C"
    assert leaders["lowest_turnover"] == "Strategy A"
    assert leaders["most_rebalancing"] == "Strategy A"

    assert leaders["most_active"] == "Strategy C"
    assert leaders["least_active"] == "Strategy A"

def test_rankings_tolerate_undefined_sharpe_ratio() -> None:
    summary = pd.DataFrame(
        {
            "total_return": [0.0, 0.2],
            "cagr": [0.0, 0.1],
            "sharpe_ratio": [np.nan, 1.0],
            "annualized_volatility": [0.0, 0.2],
            "max_drawdown": [0.0, -0.1],
        }
    )

    ranked = add_strategy_rankings(summary)

    assert ranked["sharpe_rank"].tolist() == [2, 1]
