import numpy as np
import pandas as pd
import pytest

from pairs_trading_cointegration import analyze_cointegration_formation
from pairs_trading_core import (
    extract_trades,
    generate_stateful_signal,
    run_weighted_pair_backtest,
)
from pairs_trading_distance import _relationship_break_series
from pairs_trading_dynamic import calculate_kalman_relationship


def create_cointegrated_data(number_of_rows: int = 800) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    index = pd.date_range("2020-01-01", periods=number_of_rows, freq="B")
    innovations = rng.normal(0.0004, 0.008, number_of_rows)
    log_b = 4.0 + np.cumsum(innovations)

    residual = np.zeros(number_of_rows, dtype=float)
    for row in range(1, number_of_rows):
        residual[row] = 0.82 * residual[row - 1] + rng.normal(0.0, 0.012)

    log_a = 0.35 + 1.15 * log_b + residual
    price_a = np.exp(log_a)
    price_b = np.exp(log_b)

    data = pd.DataFrame(
        {
            "price_a": price_a,
            "price_b": price_b,
            "log_price_a": log_a,
            "log_price_b": log_b,
        },
        index=index,
    )
    data["return_a"] = data["price_a"].pct_change()
    data["return_b"] = data["price_b"].pct_change()
    return data


def test_positive_deviation_shorts_spread() -> None:
    zscore = pd.Series(
        [0.0, 2.5, 1.0, 0.2],
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    result = generate_stateful_signal(zscore, 2.0, 0.5, 4.0, 60)
    assert result["pair_signal"].tolist() == pytest.approx(
        [0.0, -1.0, -1.0, 0.0]
    )


def test_relationship_break_forces_exit() -> None:
    index = pd.date_range("2026-01-01", periods=4, freq="D")
    zscore = pd.Series([0.0, 2.5, 2.2, 2.0], index=index)
    broken = pd.Series([False, False, True, False], index=index)
    result = generate_stateful_signal(
        zscore,
        2.0,
        0.5,
        4.0,
        60,
        relationship_broken=broken,
    )
    assert result["pair_signal"].tolist() == pytest.approx([0.0, -1.0, 0.0, 0.0])
    assert result["exit_reason"].iloc[2] == "relationship_break"


def test_backtest_executes_weights_next_day() -> None:
    data = pd.DataFrame(
        {
            "pair_signal": [0.0, -1.0, -1.0, 0.0],
            "return_a": [0.0, 0.0, -0.02, 0.0],
            "return_b": [0.0, 0.0, 0.02, 0.0],
        },
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    desired_a = pd.Series([0.0, -0.5, -0.5, 0.0], index=data.index)
    desired_b = pd.Series([0.0, 0.5, 0.5, 0.0], index=data.index)
    result = run_weighted_pair_backtest(
        data,
        desired_a,
        desired_b,
        initial_capital=10_000,
        transaction_cost_bps=0,
    )
    assert result["weight_a"].tolist() == pytest.approx([0.0, 0.0, -0.5, -0.5])
    assert result["weight_b"].tolist() == pytest.approx([0.0, 0.0, 0.5, 0.5])


def test_short_spread_profits_on_convergence() -> None:
    data = pd.DataFrame(
        {
            "pair_signal": [0.0, -1.0, -1.0, 0.0],
            "return_a": [0.0, 0.0, -0.02, 0.0],
            "return_b": [0.0, 0.0, 0.02, 0.0],
        },
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    result = run_weighted_pair_backtest(
        data,
        pd.Series([0.0, -0.5, -0.5, 0.0], index=data.index),
        pd.Series([0.0, 0.5, 0.5, 0.0], index=data.index),
        transaction_cost_bps=0,
    )
    assert result["gross_strategy_return"].iloc[2] == pytest.approx(0.02)


def test_cointegration_adf_is_diagnostic_not_mandatory() -> None:
    data = create_cointegrated_data()
    diagnostics = analyze_cointegration_formation(
        formation_data=data.iloc[:600],
        maximum_cointegration_pvalue=0.10,
        adf_reference_pvalue=1e-12,
        minimum_half_life_days=1.0,
        maximum_half_life_days=100.0,
        minimum_mean_crossings=2,
    )
    assert diagnostics.cointegration_pvalue < 0.10
    assert diagnostics.adf_supportive is False
    assert diagnostics.qualified


def test_kalman_relationship_uses_prior_state_for_current_zscore() -> None:
    data = create_cointegrated_data(260)
    original = calculate_kalman_relationship(data, warmup_window=60)

    modified = data.copy()
    values = modified["log_price_a"].to_numpy(dtype=float, copy=True)
    values[200] += 5.0
    modified["log_price_a"] = values
    changed = calculate_kalman_relationship(modified, warmup_window=60)

    # The beta used to predict observation 200 is formed before observing y_100.
    assert changed["dynamic_beta"].iloc[200] == pytest.approx(
        original["dynamic_beta"].iloc[200]
    )
    assert abs(changed["spread_zscore"].iloc[200]) > abs(
        original["spread_zscore"].iloc[200]
    )


def test_relationship_break_detects_large_mean_shift() -> None:
    index = pd.date_range("2026-01-01", periods=30, freq="D")
    trading = pd.DataFrame(
        {
            "return_a": np.linspace(0.001, 0.003, 30),
            "return_b": np.linspace(0.001, 0.003, 30),
        },
        index=index,
    )
    spread = pd.Series(
        [0.0] * 10 + [0.5] * 20,
        index=index,
        dtype=float,
    )
    result = _relationship_break_series(
        trading=trading,
        spread=spread,
        formation_spread_mean=0.0,
        formation_spread_std=0.1,
        recent_window=5,
        maximum_recent_volatility_ratio=10.0,
        maximum_recent_mean_shift_z=2.0,
        minimum_recent_return_correlation=-1.0,
    )
    assert result["relationship_broken"].iloc[-1]


def test_backtest_does_not_modify_input() -> None:
    data = pd.DataFrame(
        {
            "pair_signal": [0.0, 1.0, 0.0],
            "return_a": [0.0, 0.01, 0.0],
            "return_b": [0.0, -0.01, 0.0],
        }
    )
    original = data.copy(deep=True)
    run_weighted_pair_backtest(
        data,
        pd.Series([0.0, 0.5, 0.0], index=data.index),
        pd.Series([0.0, -0.5, 0.0], index=data.index),
        transaction_cost_bps=0,
    )
    pd.testing.assert_frame_equal(data, original)


def test_entry_is_skipped_when_deviation_is_already_beyond_stop() -> None:
    zscore = pd.Series(
        [0.0, 4.5, 3.0, 0.2],
        index=pd.date_range("2026-01-01", periods=4, freq="D"),
    )
    result = generate_stateful_signal(zscore, 2.0, 0.5, 4.0, 60)
    # 4.5 is past the stop, so the first entry is the later 3.0 reading.
    assert result["pair_signal"].tolist() == pytest.approx(
        [0.0, 0.0, -1.0, 0.0]
    )


def test_trades_report_exit_reason_and_include_exit_cost() -> None:
    index = pd.date_range("2026-01-01", periods=6, freq="D")
    zscore = pd.Series([0.0, 2.5, 1.5, 0.2, 0.0, 0.0], index=index)
    signals = generate_stateful_signal(zscore, 2.0, 0.5, 4.0, 60)
    data = pd.DataFrame(
        {
            "spread_zscore": zscore,
            "pair_signal": signals["pair_signal"],
            "exit_reason": signals["exit_reason"],
            "return_a": 0.0,
            "return_b": 0.0,
        },
        index=index,
    )
    tested = run_weighted_pair_backtest(
        data,
        -0.5 * data["pair_signal"],
        0.5 * data["pair_signal"],
        transaction_cost_bps=10,
        liquidate_at_end=False,
    )

    trades = extract_trades(tested, "A", "B")

    assert len(trades) == 1
    assert trades["exit_reason"].iloc[0] == "convergence"
    # Entry and exit each turn over both legs: 2 x 1.0 x 10 bps.
    assert trades["transaction_cost"].iloc[0] == pytest.approx(0.002)
    assert trades["net_pair_return"].iloc[0] == pytest.approx(-0.002)


def test_kalman_zscore_is_calibrated_to_realised_spread() -> None:
    data = create_cointegrated_data(800)
    modeled = calculate_kalman_relationship(
        data,
        warmup_window=120,
        zscore_window=60,
    )
    zscore = modeled["spread_zscore"].dropna()

    # A z-score of 2 should mean roughly two standard deviations.
    assert 0.8 < zscore.std() < 1.5
    assert modeled["dynamic_beta"].dropna().between(0.8, 1.5).all()


def test_discovery_ranks_only_on_opening_formation_window(monkeypatch) -> None:
    import pairs_trading_discovery

    data = create_cointegrated_data(800)
    universe = {
        "AAA": pd.DataFrame(
            {
                "price": data["price_a"],
                "log_price": data["log_price_a"],
                "return": data["return_a"],
            }
        ),
        "BBB": pd.DataFrame(
            {
                "price": data["price_b"],
                "log_price": data["log_price_b"],
                "return": data["return_b"],
            }
        ),
    }
    monkeypatch.setattr(
        pairs_trading_discovery,
        "prepare_universe_data",
        lambda tickers, start_date, end_date: universe,
    )

    result = pairs_trading_discovery.discover_pairs(
        ["AAA", "BBB"],
        "2020-01-01",
        "2023-01-01",
        method=pairs_trading_discovery.METHOD_COINTEGRATION,
        formation_years=1,
    )

    one_year = len(data.loc["2020-01-01":"2020-12-31"])
    assert result["observations"].iloc[0] == one_year
    assert "bonferroni_pvalue" in result.columns


def test_pairs_carry_pays_borrow_fee_and_earns_cash_on_idle_capital() -> None:
    index = pd.date_range("2026-01-01", periods=3, freq="D")
    data = pd.DataFrame(
        {"return_a": [np.nan, 0.0, 0.0], "return_b": [np.nan, 0.0, 0.0]},
        index=index,
    )
    weight = pd.Series([0.5, 0.5, 0.5], index=index)

    result = run_weighted_pair_backtest(
        data,
        weight,
        -weight,
        transaction_cost_bps=0,
        liquidate_at_end=False,
        cash_rate=0.04,
        borrow_fee=0.01,
    )

    expected = 0.5 * (1.04 ** (1 / 252) - 1) - 0.5 * (1.01 ** (1 / 252) - 1)
    assert result["gross_strategy_return"].iloc[2] == pytest.approx(expected)


def test_pairs_portfolio_trades_only_after_selection_window(monkeypatch) -> None:
    import pairs_trading_core
    import pairs_trading_discovery
    import pairs_trading_portfolio

    data = create_cointegrated_data(1000)
    selection = pd.DataFrame({"asset_a": ["AAA"], "asset_b": ["BBB"]})
    monkeypatch.setattr(
        pairs_trading_portfolio,
        "discover_pairs",
        lambda **kwargs: selection,
    )
    for module in ("pairs_trading_cointegration", "pairs_trading_distance"):
        monkeypatch.setattr(
            __import__(module),
            "prepare_pair_data",
            lambda *args, **kwargs: data.copy(),
        )

    result = pairs_trading_portfolio.build_pairs_portfolio(
        ["AAA", "BBB"],
        "2020-01-01",
        "2024-01-01",
        method=pairs_trading_core.METHOD_COINTEGRATION,
        top_n=1,
        formation_years=1,
    )

    assert result.portfolio.index[0] >= pd.Timestamp("2021-01-01")
    assert list(result.pair_results) == ["AAA/BBB"]
    assert pairs_trading_discovery.UNIVERSE_PRESETS
