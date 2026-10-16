import pandas as pd
import pytest

from backtester import run_backtest
from strategies.moving_average import (
    generate_moving_average_signals,
)


def create_sample_data() -> pd.DataFrame:
    """
    Create deterministic price data for unit tests.
    """
    return pd.DataFrame(
        {
            "Close": [
                10.0,
                11.0,
                12.0,
                11.0,
                10.0,
                11.0,
            ],
            "asset_return": [
                0.0,
                0.10,
                12 / 11 - 1,
                11 / 12 - 1,
                10 / 11 - 1,
                0.10,
            ],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=6,
            freq="D",
        ),
    )


def test_generate_signals_creates_expected_columns() -> None:
    data = create_sample_data()

    result = generate_moving_average_signals(
        data=data,
        fast_window=2,
        slow_window=3,
    )

    assert "fast_ma" in result.columns
    assert "slow_ma" in result.columns
    assert "signal" in result.columns


def test_signal_is_binary() -> None:
    data = create_sample_data()

    result = generate_moving_average_signals(
        data=data,
        fast_window=2,
        slow_window=3,
    )

    assert set(result["signal"].unique()).issubset({0, 1})


def test_generate_signals_rejects_invalid_windows() -> None:
    data = create_sample_data()

    with pytest.raises(ValueError):
        generate_moving_average_signals(
            data=data,
            fast_window=5,
            slow_window=3,
        )


def test_position_uses_previous_days_signal() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 1, 1, 0],
            "asset_return": [0.01, 0.02, -0.01, 0.03],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    expected_positions = [0.0, 0.0, 1.0, 1.0]

    assert result["position"].tolist() == expected_positions


def test_strategy_returns_follow_positions() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 1, 1, 0],
            "asset_return": [0.01, 0.02, -0.01, 0.03],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    expected_returns = [0.0, 0.0, -0.01, 0.03]

    assert result["strategy_return"].tolist() == pytest.approx(
        expected_returns
    )


def test_transaction_cost_is_applied_on_position_changes() -> None:
    data = pd.DataFrame(
        {
            "signal": [1, 1, 0, 0],
            "asset_return": [0.0, 0.0, 0.0, 0.0],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=10,
    )

    assert result["trade"].tolist() == pytest.approx(
        [0.0, 1.0, 0.0, 1.0]
    )

    assert result["transaction_cost"].tolist() == pytest.approx(
        [0.0, 0.001, 0.0, 0.001]
    )


def test_buy_and_hold_pays_initial_one_way_transaction_cost() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 0, 0],
            "asset_return": [0.0, 0.0, 0.0],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=10,
    )

    assert result["buy_hold_turnover"].tolist() == pytest.approx(
        [1.0, 0.0, 0.0]
    )
    assert result["buy_hold_transaction_cost"].tolist() == pytest.approx(
        [0.001, 0.0, 0.0]
    )
    assert result["buy_hold_return"].tolist() == pytest.approx(
        [-0.001, 0.0, 0.0]
    )
    assert result["buy_hold_equity"].iloc[0] == pytest.approx(
        9_990.0
    )
    assert result["buy_hold_drawdown"].iloc[0] == pytest.approx(
        -0.001
    )


def test_continuous_position_changes_measure_turnover_magnitude() -> None:
    data = pd.DataFrame(
        {
            "target_position": [0.25, 0.50, 0.55, 0.40],
            "asset_return": [0.0, 0.0, 0.0, 0.0],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    assert result["position"].tolist() == pytest.approx(
        [0.0, 0.25, 0.50, 0.55]
    )
    assert result["trade"].tolist() == pytest.approx(
        [0.0, 0.25, 0.25, 0.05]
    )


def test_invalid_initial_capital_is_rejected() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 1],
            "asset_return": [0.0, 0.01],
        }
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            initial_capital=0,
            transaction_cost_bps=0,
        )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            initial_capital=-1,
            transaction_cost_bps=0,
        )


def test_negative_transaction_cost_is_rejected() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 1],
            "asset_return": [0.0, 0.01],
        }
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            initial_capital=10_000,
            transaction_cost_bps=-1,
        )


def test_missing_signal_and_target_position_is_rejected() -> None:
    data = pd.DataFrame(
        {
            "asset_return": [0.0, 0.01],
        }
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            initial_capital=10_000,
            transaction_cost_bps=0,
        )


def test_negative_exposure_is_rejected() -> None:
    data = pd.DataFrame(
        {
            "target_position": [0.0, -0.25, 0.50],
            "asset_return": [0.0, 0.01, 0.02],
        }
    )

    with pytest.raises(ValueError):
        run_backtest(
            data=data,
            initial_capital=10_000,
            transaction_cost_bps=0,
        )


def test_target_position_takes_precedence_over_signal() -> None:
    data = pd.DataFrame(
        {
            "signal": [1, 1, 1],
            "target_position": [0.0, 0.50, 0.50],
            "asset_return": [0.0, 0.10, 0.10],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    assert result["position"].tolist() == pytest.approx(
        [0.0, 0.0, 0.50]
    )


def test_continuous_turnover_cost_scales_with_position_change() -> None:
    data = pd.DataFrame(
        {
            "target_position": [0.25, 0.50, 0.55, 0.40],
            "asset_return": [0.0, 0.0, 0.0, 0.0],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=10,
    )

    assert result["transaction_cost"].tolist() == pytest.approx(
        [0.0, 0.00025, 0.00025, 0.00005]
    )


def test_strategy_equity_compounds_strategy_returns() -> None:
    data = pd.DataFrame(
        {
            "signal": [1, 1, 1],
            "asset_return": [0.0, 0.10, -0.05],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    assert result["strategy_return"].tolist() == pytest.approx(
        [0.0, 0.10, -0.05]
    )

    assert result["strategy_equity"].tolist() == pytest.approx(
        [10_000.0, 11_000.0, 10_450.0]
    )


def test_buy_and_hold_equity_compounds_asset_returns() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 0, 0],
            "asset_return": [0.0, 0.10, -0.05],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    assert result["buy_hold_return"].tolist() == pytest.approx(
        [0.0, 0.10, -0.05]
    )

    assert result["buy_hold_equity"].tolist() == pytest.approx(
        [10_000.0, 11_000.0, 10_450.0]
    )


def test_fractional_exposure_produces_proportional_return() -> None:
    data = pd.DataFrame(
        {
            "target_position": [0.50, 0.50, 0.50],
            "asset_return": [0.0, 0.10, -0.20],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )

    assert result["position"].tolist() == pytest.approx(
        [0.0, 0.50, 0.50]
    )

    assert result["gross_strategy_return"].tolist() == pytest.approx(
        [0.0, 0.05, -0.10]
    )


def test_run_backtest_does_not_modify_original_data() -> None:
    data = pd.DataFrame(
        {
            "signal": [0, 1, 1],
            "asset_return": [0.0, 0.01, -0.02],
        },
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )
    original = data.copy(deep=True)

    run_backtest(
        data=data,
        initial_capital=10_000,
        transaction_cost_bps=10,
    )

    pd.testing.assert_frame_equal(
        data,
        original,
    )

def test_idle_cash_earns_the_cash_rate() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    data = pd.DataFrame(
        {"asset_return": [float("nan"), 0.01, 0.01], "signal": [0, 0, 0]},
        index=index,
    )

    result = run_backtest(data, transaction_cost_bps=0, cash_rate=0.05)

    daily = 1.05 ** (1 / 252) - 1
    assert result["strategy_equity"].iloc[0] == pytest.approx(10_000)
    assert result["strategy_return"].iloc[1] == pytest.approx(daily)


def test_leverage_pays_cash_rate_plus_financing_spread() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    data = pd.DataFrame(
        {
            "asset_return": [float("nan"), 0.0, 0.0],
            "target_position": [1.5, 1.5, 1.5],
        },
        index=index,
    )

    result = run_backtest(
        data,
        transaction_cost_bps=0,
        cash_rate=0.03,
        financing_spread=0.01,
    )

    borrow = 1.04 ** (1 / 252) - 1
    assert result["gross_strategy_return"].iloc[1] == pytest.approx(-0.5 * borrow)
