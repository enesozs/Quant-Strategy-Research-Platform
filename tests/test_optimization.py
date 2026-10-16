import numpy as np
import pandas as pd
import pytest

from backtester import calculate_returns, run_strategy_on_data, run_strategy_on_window
from optimization import (
    calculate_optimization_gain,
    calculate_relative_optimization_gain,
    create_parameter_sensitivity_profile,
    create_parameter_sensitivity_table,
    create_refined_parameter_grid,
    optimize_strategy,
)


def create_market_data(
    number_of_rows: int = 700,
) -> pd.DataFrame:
    """Create deterministic synthetic OHLC data for optimizer tests."""
    index = pd.date_range(
        start="2020-01-01",
        periods=number_of_rows,
        freq="B",
    )

    time = np.arange(number_of_rows)

    close = (
        100
        + 0.06 * time
        + 10 * np.sin(time / 25)
        + 2 * np.sin(time / 6)
    )

    data = pd.DataFrame(
        {
            "Open": close - 0.25,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )

    data["asset_return"] = data["Close"].pct_change()

    return data


def test_optimizer_returns_all_valid_combinations() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        transaction_cost_bps=0,
    )

    assert len(result.results) == 4
    assert result.objective == "sharpe_ratio"
    assert set(result.best_parameters) == {
        "fast_window",
        "slow_window",
    }


def test_optimizer_rejects_invalid_window_combinations() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [20, 50],
            "slow_window": [30, 50],
        },
        transaction_cost_bps=0,
    )

    assert len(result.results) == 2

    assert (
        result.results["fast_window"]
        < result.results["slow_window"]
    ).all()


def test_optimizer_sorts_sharpe_descending() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="momentum",
        parameter_grid={
            "lookback_window": [20, 60, 120],
            "threshold": [0.0],
        },
        objective="sharpe_ratio",
        transaction_cost_bps=0,
    )

    sharpe = result.results["sharpe_ratio"].dropna()

    assert sharpe.is_monotonic_decreasing


def test_optimizer_sorts_volatility_ascending() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="momentum",
        parameter_grid={
            "lookback_window": [20, 60, 120],
            "threshold": [0.0],
        },
        objective="annualized_volatility",
        transaction_cost_bps=0,
    )

    volatility = result.results[
        "annualized_volatility"
    ].dropna()

    assert volatility.is_monotonic_increasing


def test_optimizer_sorts_max_drawdown_descending() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="momentum",
        parameter_grid={
            "lookback_window": [20, 60, 120],
            "threshold": [0.0],
        },
        objective="max_drawdown",
        transaction_cost_bps=0,
    )

    drawdown = result.results["max_drawdown"].dropna()

    assert drawdown.is_monotonic_decreasing


def test_optimizer_reports_turnover_and_rebalancing_days() -> None:
    data = create_market_data()

    result = optimize_strategy(
        data=data,
        strategy_name="volatility_targeted_momentum",
        parameter_grid={
            "momentum_window": [60],
            "volatility_window": [20],
            "target_volatility": [0.15],
            "maximum_exposure": [1.0],
            "momentum_threshold": [0.0],
        },
        transaction_cost_bps=10,
    )

    assert "rebalancing_days" in result.results.columns
    assert "turnover" in result.results.columns
    assert result.results["rebalancing_days"].iloc[0] >= 0
    assert result.results["turnover"].iloc[0] >= 0


def test_optimizer_rejects_unknown_parameters() -> None:
    data = create_market_data()

    with pytest.raises(ValueError):
        optimize_strategy(
            data=data,
            strategy_name="momentum",
            parameter_grid={
                "not_a_parameter": [1, 2, 3],
            },
        )


def test_optimizer_rejects_all_nonfinite_objective_values() -> None:
    index = pd.date_range(
        start="2020-01-01",
        periods=300,
        freq="B",
    )
    close = np.full(len(index), 100.0)

    data = pd.DataFrame(
        {
            "Open": close,
            "High": close,
            "Low": close,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )
    data["asset_return"] = data["Close"].pct_change()

    with pytest.raises(
        ValueError,
        match="No finite objective values",
    ):
        optimize_strategy(
            data=data,
            strategy_name="momentum",
            parameter_grid={
                "lookback_window": [20, 60],
                "threshold": [0.0],
            },
            objective="sharpe_ratio",
            transaction_cost_bps=0,
        )


def test_optimization_gain_for_higher_is_better() -> None:
    gain = calculate_optimization_gain(
        optimized_value=1.10,
        default_value=0.90,
        objective="sharpe_ratio",
    )

    assert gain == pytest.approx(0.20)


def test_optimization_gain_for_lower_volatility() -> None:
    gain = calculate_optimization_gain(
        optimized_value=0.15,
        default_value=0.20,
        objective="annualized_volatility",
    )

    assert gain == pytest.approx(0.05)


def test_optimization_gain_for_drawdown() -> None:
    gain = calculate_optimization_gain(
        optimized_value=-0.20,
        default_value=-0.30,
        objective="max_drawdown",
    )

    assert gain == pytest.approx(0.10)


def test_relative_optimization_gain() -> None:
    gain = calculate_relative_optimization_gain(
        optimized_value=1.20,
        default_value=1.00,
        objective="sharpe_ratio",
    )

    assert gain == pytest.approx(0.20)


def test_relative_gain_returns_nan_for_zero_default() -> None:
    gain = calculate_relative_optimization_gain(
        optimized_value=0.10,
        default_value=0.0,
        objective="total_return",
    )

    assert np.isnan(gain)


def test_create_parameter_sensitivity_table() -> None:
    results = pd.DataFrame(
        {
            "entry_window": [
                20,
                20,
                50,
                50,
            ],
            "exit_window": [
                5,
                10,
                5,
                10,
            ],
            "sharpe_ratio": [
                0.70,
                0.80,
                0.90,
                1.00,
            ],
        }
    )

    table = create_parameter_sensitivity_table(
        results=results,
        row_parameter="entry_window",
        column_parameter="exit_window",
        metric="sharpe_ratio",
    )

    assert table.loc[20, 5] == pytest.approx(
        0.70
    )

    assert table.loc[50, 10] == pytest.approx(
        1.00
    )


def test_sensitivity_table_rejects_missing_columns() -> None:
    results = pd.DataFrame(
        {
            "entry_window": [20],
            "sharpe_ratio": [0.70],
        }
    )

    with pytest.raises(ValueError):
        create_parameter_sensitivity_table(
            results=results,
            row_parameter="entry_window",
            column_parameter="exit_window",
            metric="sharpe_ratio",
        )


def test_sensitivity_profile_uses_lower_volatility_as_best() -> None:
    results = pd.DataFrame(
        {
            "window": [10, 10, 20, 20],
            "annualized_volatility": [
                0.20,
                0.22,
                0.15,
                0.18,
            ],
        }
    )

    profile = create_parameter_sensitivity_profile(
        results=results,
        parameter_name="window",
        metric="annualized_volatility",
    )

    row_10 = profile.loc[
        profile["window"] == 10
    ].iloc[0]
    row_20 = profile.loc[
        profile["window"] == 20
    ].iloc[0]

    assert row_10["best_observed"] == pytest.approx(0.20)
    assert row_10["worst_observed"] == pytest.approx(0.22)
    assert row_20["best_observed"] == pytest.approx(0.15)
    assert row_20["worst_observed"] == pytest.approx(0.18)


def test_refined_integer_grid_retains_broad_optimum_and_bounds() -> None:
    refined = create_refined_parameter_grid(
        strategy_name="moving_average",
        broad_parameter_grid={
            "fast_window": [10, 20, 40],
            "slow_window": [50, 100, 200],
        },
        broad_best_parameters={
            "fast_window": 20,
            "slow_window": 100,
        },
        refinement_points=5,
    )

    assert 20 in refined["fast_window"]
    assert 100 in refined["slow_window"]
    assert all(
        isinstance(value, int)
        for value in refined["fast_window"]
    )
    assert all(
        isinstance(value, int)
        for value in refined["slow_window"]
    )
    assert min(refined["fast_window"]) >= 1
    assert max(refined["fast_window"]) <= 500
    assert min(refined["slow_window"]) >= 2
    assert max(refined["slow_window"]) <= 500

def test_candidates_are_scored_after_a_common_burn_in() -> None:
    data = calculate_returns(create_market_data())
    grid = {"fast_window": [5, 20], "slow_window": [50, 200]}

    result = optimize_strategy(
        data=data,
        strategy_name="moving_average",
        parameter_grid=grid,
    )

    # The 200-day slow window needs 200 rows before its first signal, so
    # nothing may be scored earlier than that.
    assert result.evaluation_start >= data.index[200]


def test_burn_in_removes_cold_start_cash_drag() -> None:
    data = calculate_returns(create_market_data())
    evaluation_start = data.index[300]

    warm = run_strategy_on_window(
        data=data,
        strategy_name="moving_average",
        evaluation_start=evaluation_start,
        strategy_parameters={"fast_window": 20, "slow_window": 200},
    )
    full = run_strategy_on_data(
        data=data,
        strategy_name="moving_average",
        strategy_parameters={"fast_window": 20, "slow_window": 200},
    )

    assert warm.index[0] == evaluation_start
    # Positions after the first day match an uninterrupted backtest.
    pd.testing.assert_series_equal(
        warm["position"].iloc[1:],
        full.loc[evaluation_start:, "position"].iloc[1:],
    )
    # Buy and Hold enters at the prior close, so it earns only the first
    # evaluated day's return less its entry cost.
    expected = 10_000 * (1 - 0.001) * (1 + data.loc[evaluation_start, "asset_return"])
    assert warm["buy_hold_equity"].iloc[0] == pytest.approx(expected)


def test_near_zero_optimum_does_not_explode_relative_degradation() -> None:
    from optimization import _calculate_relative_objective_degradation

    degradation = _calculate_relative_objective_degradation(
        values=np.array([0.02, 0.018]),
        best_value=0.02,
        objective="sharpe_ratio",
    )

    # A Sharpe difference of 0.002 is noise, not a 10% degradation.
    assert degradation[1] < 0.01
