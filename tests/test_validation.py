import numpy as np
import pandas as pd
import pytest

from validation import (
    _build_continuous_stitched_strategy_returns,
    build_validation_summary,
    calculate_out_of_sample_degradation,
    validate_strategy_out_of_sample,
    validate_strategy_walk_forward,
)


def create_market_data(
    number_of_rows: int = 900,
) -> pd.DataFrame:
    """Create deterministic synthetic OHLC data for validation tests."""
    index = pd.date_range(
        start="2020-01-01",
        periods=number_of_rows,
        freq="B",
    )

    time = np.arange(number_of_rows)

    close = (
        100
        + 0.05 * time
        + 8 * np.sin(time / 20)
        + 2 * np.sin(time / 5)
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


def test_validation_uses_strict_train_test_split() -> None:
    data = create_market_data()
    split_date = data.index[600]

    result = validate_strategy_out_of_sample(
        data=data,
        strategy_name="moving_average",
        split_date=split_date,
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        transaction_cost_bps=0,
    )

    assert (
        result.default.training_results.index
        < split_date
    ).all()
    assert (
        result.default.test_results.index
        >= split_date
    ).all()


def test_validation_freezes_optimized_parameters() -> None:
    data = create_market_data()
    split_date = data.index[600]

    result = validate_strategy_out_of_sample(
        data=data,
        strategy_name="moving_average",
        split_date=split_date,
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        transaction_cost_bps=0,
    )

    assert (
        result.optimized.parameters
        == result.optimization_result.best_parameters
    )
    assert (
        result.robust_candidate.parameters
        == result.robustness.robust_candidate_parameters
    )


def test_test_equity_is_rebased_to_validation_capital() -> None:
    data = create_market_data()
    split_date = data.index[600]

    initial_capital = 10_000.0

    result = validate_strategy_out_of_sample(
        data=data,
        strategy_name="moving_average",
        split_date=split_date,
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_capital=initial_capital,
        transaction_cost_bps=0,
    )

    first_test_equity = float(
        result.optimized.test_results[
            "strategy_equity"
        ].iloc[0]
    )

    assert first_test_equity > 0
    assert first_test_equity < initial_capital * 1.2
    assert first_test_equity > initial_capital * 0.8


def test_validation_summary_contains_all_parameter_sets() -> None:
    data = create_market_data()
    split_date = data.index[600]

    result = validate_strategy_out_of_sample(
        data=data,
        strategy_name="moving_average",
        split_date=split_date,
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        transaction_cost_bps=0,
    )

    summary = build_validation_summary(result)

    assert set(summary["parameter_set"]) == {
        "Default parameters",
        "Raw optimum",
        "Robust candidate",
        "Buy and Hold",
    }


def test_higher_is_better_oos_degradation() -> None:
    absolute, relative = calculate_out_of_sample_degradation(
        training_value=1.0,
        test_value=0.8,
        objective="sharpe_ratio",
    )

    assert absolute == pytest.approx(0.2)
    assert relative == pytest.approx(0.2)


def test_lower_is_better_oos_degradation() -> None:
    absolute, relative = calculate_out_of_sample_degradation(
        training_value=0.15,
        test_value=0.18,
        objective="annualized_volatility",
    )

    assert absolute == pytest.approx(0.03)
    assert relative == pytest.approx(0.20)


def test_validation_rejects_empty_side_of_split() -> None:
    data = create_market_data()

    with pytest.raises(ValueError):
        validate_strategy_out_of_sample(
            data=data,
            strategy_name="moving_average",
            split_date=data.index[0],
            parameter_grid={
                "fast_window": [10],
                "slow_window": [30],
            },
        )


def create_walk_forward_market_data() -> pd.DataFrame:
    """Create a longer sample so multiple complete calendar folds exist."""
    return create_market_data(number_of_rows=1600)


def test_walk_forward_creates_multiple_non_overlapping_test_folds() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert len(result.folds) >= 2

    for previous, current in zip(
        result.folds,
        result.folds[1:],
    ):
        assert previous.test_end < current.test_start
        assert previous.training_start == current.training_start
        assert current.training_end > previous.training_end


def test_walk_forward_never_uses_test_data_for_parameter_selection() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    for fold in result.folds:
        split_date = fold.validation.split_date

        assert (
            fold.validation.default.training_results.index
            < split_date
        ).all()
        assert (
            fold.validation.default.test_results.index
            >= split_date
        ).all()


def test_walk_forward_records_parameter_history() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert len(result.parameter_history) == len(result.folds)
    assert {
        "raw_fast_window",
        "raw_slow_window",
        "robust_fast_window",
        "robust_slow_window",
    }.issubset(result.parameter_history.columns)


def test_walk_forward_stitched_equity_uses_only_test_dates() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    expected_test_dates = pd.Index([])
    for fold in result.folds:
        expected_test_dates = expected_test_dates.append(
            fold.validation.optimized.test_results.index
        )

    expected_test_dates = expected_test_dates.drop_duplicates().sort_values()

    assert result.stitched_equity_curves.index.equals(
        expected_test_dates
    )
    assert result.stitched_equity_curves.notna().all().all()


def test_walk_forward_aggregate_summary_contains_all_parameter_sets() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert set(result.aggregate_summary["parameter_set"]) == {
        "Default parameters",
        "Raw optimum",
        "Robust candidate",
        "Buy and Hold",
    }


def test_walk_forward_rejects_sample_too_short_for_initial_training() -> None:
    data = create_market_data(number_of_rows=200)

    with pytest.raises(ValueError):
        validate_strategy_walk_forward(
            data=data,
            strategy_name="moving_average",
            parameter_grid={
                "fast_window": [10],
                "slow_window": [30],
            },
            initial_training_years=2,
            test_window_years=1,
        )


def test_walk_forward_keeps_complete_final_trading_year() -> None:
    """Keep a final fold when only weekend/holiday calendar days are absent."""
    data = create_market_data(number_of_rows=1565)

    # Re-index the deterministic observations onto business days spanning
    # 2020 through the final trading day of 2025. This mirrors a download
    # whose requested exclusive end date is 2026-01-01.
    data = data.iloc[:1565].copy()
    data.index = pd.bdate_range(
        start="2020-01-02",
        periods=len(data),
    )

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert len(result.folds) >= 4
    assert result.folds[3].test_start.year == 2025



def test_rolling_walk_forward_uses_fixed_length_training_windows() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        training_window_type="rolling",
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert result.training_window_type == "rolling"
    assert len(result.folds) >= 2

    for previous, current in zip(
        result.folds,
        result.folds[1:],
    ):
        assert current.training_start > previous.training_start
        assert current.training_end > previous.training_end
        assert previous.test_end < current.test_start

    sample_start = pd.Timestamp(data.index[0]).normalize()

    for fold in result.folds:
        nominal_test_start = sample_start + pd.DateOffset(
            years=2 + (fold.fold - 1)
        )
        nominal_training_start = (
            nominal_test_start - pd.DateOffset(years=2)
        )

        # Rolling windows are anchored to the nominal calendar fold boundary,
        # not the first trading observation in the test fold. For example, a
        # nominal 2022-01-01 test boundary may have its first test observation
        # on 2022-01-03 while the two-year training window still correctly
        # begins at the first trading observation on/after 2020-01-01.
        assert fold.training_start >= nominal_training_start
        assert fold.training_start <= nominal_training_start + pd.Timedelta(days=7)
        assert fold.training_end < fold.test_start


def test_expanding_walk_forward_remains_default_mode() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    assert result.training_window_type == "expanding"
    first_training_start = result.folds[0].training_start
    assert all(
        fold.training_start == first_training_start
        for fold in result.folds
    )


def test_walk_forward_rejects_unknown_training_window_type() -> None:
    data = create_walk_forward_market_data()

    with pytest.raises(ValueError):
        validate_strategy_walk_forward(
            data=data,
            strategy_name="moving_average",
            parameter_grid={
                "fast_window": [10],
                "slow_window": [30],
            },
            training_window_type="unknown",  # type: ignore[arg-type]
            initial_training_years=2,
            test_window_years=1,
            transaction_cost_bps=0,
        )


def _make_stitched_fold_results(
    positions: list[float],
    gross_returns: list[float] | None = None,
    start: str = "2026-01-01",
) -> pd.DataFrame:
    """Create minimal fold results for stitched-boundary transaction-cost tests."""
    if gross_returns is None:
        gross_returns = [0.0] * len(positions)

    index = pd.date_range(
        start=start,
        periods=len(positions),
        freq="B",
    )

    return pd.DataFrame(
        {
            "position": positions,
            "gross_strategy_return": gross_returns,
            "strategy_return": gross_returns,
        },
        index=index,
    )


def test_stitched_strategy_keeps_same_exposure_without_rebuy_cost() -> None:
    first_fold = _make_stitched_fold_results(
        positions=[1.0, 1.0],
        start="2026-01-01",
    )
    second_fold = _make_stitched_fold_results(
        positions=[1.0, 1.0],
        start="2026-01-05",
    )

    returns = _build_continuous_stitched_strategy_returns(
        fold_results=[first_fold, second_fold],
        transaction_cost_bps=10,
    )

    assert returns.iloc[0] == pytest.approx(-0.001)
    assert returns.iloc[2] == pytest.approx(0.0)


def test_stitched_strategy_charges_actual_boundary_position_change() -> None:
    first_fold = _make_stitched_fold_results(
        positions=[1.0, 1.0],
        start="2026-01-01",
    )
    second_fold = _make_stitched_fold_results(
        positions=[0.0, 0.0],
        start="2026-01-05",
    )

    returns = _build_continuous_stitched_strategy_returns(
        fold_results=[first_fold, second_fold],
        transaction_cost_bps=10,
    )

    assert returns.iloc[0] == pytest.approx(-0.001)
    assert returns.iloc[2] == pytest.approx(-0.001)


def test_stitched_strategy_handles_fractional_boundary_turnover() -> None:
    first_fold = _make_stitched_fold_results(
        positions=[0.4, 0.4],
        start="2026-01-01",
    )
    second_fold = _make_stitched_fold_results(
        positions=[0.7, 0.7],
        start="2026-01-05",
    )
    third_fold = _make_stitched_fold_results(
        positions=[0.3, 0.3],
        start="2026-01-07",
    )

    returns = _build_continuous_stitched_strategy_returns(
        fold_results=[first_fold, second_fold, third_fold],
        transaction_cost_bps=10,
    )

    assert returns.iloc[0] == pytest.approx(-0.0004)
    assert returns.iloc[2] == pytest.approx(-0.0003)
    assert returns.iloc[4] == pytest.approx(-0.0004)


def test_stitched_boundary_keeps_first_day_gross_return() -> None:
    first_fold = _make_stitched_fold_results(
        positions=[0.5, 0.5],
        gross_returns=[0.01, 0.02],
        start="2026-01-01",
    )
    second_fold = _make_stitched_fold_results(
        positions=[0.8, 0.8],
        gross_returns=[0.03, -0.01],
        start="2026-01-05",
    )

    returns = _build_continuous_stitched_strategy_returns(
        fold_results=[first_fold, second_fold],
        transaction_cost_bps=10,
    )

    assert returns.iloc[0] == pytest.approx(0.01 - 0.0005)
    assert returns.iloc[2] == pytest.approx(0.03 - 0.0003)


def test_walk_forward_stitched_buy_and_hold_pays_one_initial_cost() -> None:
    data = create_walk_forward_market_data()

    result_without_cost = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    result_with_cost = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=10,
    )

    first_without_cost = float(
        result_without_cost.stitched_equity_curves[
            "Buy and Hold"
        ].iloc[0]
    )
    first_with_cost = float(
        result_with_cost.stitched_equity_curves[
            "Buy and Hold"
        ].iloc[0]
    )

    assert first_with_cost == pytest.approx(
        first_without_cost - 10.0
    )


def test_walk_forward_volatility_aggregate_best_and_worst_direction() -> None:
    data = create_walk_forward_market_data()

    result = validate_strategy_walk_forward(
        data=data,
        strategy_name="moving_average",
        parameter_grid={
            "fast_window": [10, 20],
            "slow_window": [30, 50],
        },
        objective="annualized_volatility",
        initial_training_years=2,
        test_window_years=1,
        transaction_cost_bps=0,
    )

    summary = result.aggregate_summary.set_index(
        "parameter_set"
    )

    for parameter_set in summary.index:
        row = summary.loc[parameter_set]
        assert row["best_test_objective"] <= row[
            "worst_test_objective"
        ]