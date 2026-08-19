import numpy as np
import pandas as pd
import pytest

from metrics import (
    TRADING_DAYS_PER_YEAR,
    calculate_annualized_volatility,
    calculate_cagr,
    calculate_max_drawdown,
    calculate_performance_metrics,
    calculate_sharpe_ratio,
    calculate_total_return,
)


def test_total_return() -> None:
    equity = pd.Series(
        [10_000.0, 11_000.0, 12_000.0],
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = calculate_total_return(equity)

    assert result == pytest.approx(0.20)


def test_total_return_uses_supplied_initial_value() -> None:
    equity = pd.Series(
        [9_990.0, 10_500.0, 11_000.0],
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = calculate_total_return(
        equity,
        initial_value=10_000.0,
    )

    assert result == pytest.approx(0.10)


def test_cagr_uses_calendar_time() -> None:
    equity = pd.Series(
        [10_000.0, 12_100.0],
        index=pd.to_datetime(
            [
                "2024-01-01",
                "2024-12-31",
            ]
        ),
    )

    result = calculate_cagr(equity)

    number_of_years = 365 / 365.25
    expected = (12_100 / 10_000) ** (
        1 / number_of_years
    ) - 1

    assert result == pytest.approx(expected)


def test_cagr_uses_supplied_initial_value() -> None:
    equity = pd.Series(
        [9_990.0, 11_000.0],
        index=pd.to_datetime(
            [
                "2024-01-01",
                "2024-12-31",
            ]
        ),
    )

    result = calculate_cagr(
        equity,
        initial_value=10_000.0,
    )

    number_of_years = 365 / 365.25
    expected = (11_000 / 10_000) ** (
        1 / number_of_years
    ) - 1

    assert result == pytest.approx(expected)


def test_annualized_volatility() -> None:
    returns = pd.Series(
        [0.01, -0.02, 0.03, 0.00]
    )

    result = calculate_annualized_volatility(
        returns
    )

    expected = (
        returns.std(ddof=1)
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    assert result == pytest.approx(expected)


def test_sharpe_ratio() -> None:
    returns = pd.Series(
        [0.01, -0.005, 0.015, 0.002]
    )

    result = calculate_sharpe_ratio(
        returns,
        risk_free_rate=0.0,
    )

    expected = (
        returns.mean()
        / returns.std(ddof=1)
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    assert result == pytest.approx(expected)


def test_sharpe_ratio_uses_nonzero_risk_free_rate() -> None:
    returns = pd.Series(
        [0.01, 0.004, -0.002, 0.012]
    )
    risk_free_rate = 0.05

    result = calculate_sharpe_ratio(
        returns,
        risk_free_rate=risk_free_rate,
    )

    daily_risk_free_rate = (
        (1 + risk_free_rate)
        ** (1 / TRADING_DAYS_PER_YEAR)
        - 1
    )

    excess_returns = (
        returns - daily_risk_free_rate
    )

    expected = (
        excess_returns.mean()
        / excess_returns.std(ddof=1)
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    assert result == pytest.approx(expected)


def test_zero_volatility_sharpe_returns_nan() -> None:
    returns = pd.Series(
        [0.01, 0.01, 0.01, 0.01]
    )

    result = calculate_sharpe_ratio(returns)

    assert np.isnan(result)


def test_max_drawdown() -> None:
    equity = pd.Series(
        [100.0, 120.0, 90.0, 110.0],
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    result = calculate_max_drawdown(equity)

    assert result == pytest.approx(-0.25)


def test_max_drawdown_respects_initial_value() -> None:
    equity = pd.Series(
        [9_990.0, 10_050.0, 9_800.0],
        index=pd.date_range(
            start="2026-01-01",
            periods=3,
            freq="D",
        ),
    )

    result = calculate_max_drawdown(
        equity,
        initial_value=10_000.0,
    )

    expected = 9_800 / 10_050 - 1

    assert result == pytest.approx(expected)


def test_empty_equity_is_rejected() -> None:
    empty_equity = pd.Series(
        dtype=float
    )

    with pytest.raises(ValueError):
        calculate_total_return(empty_equity)

    with pytest.raises(ValueError):
        calculate_cagr(empty_equity)

    with pytest.raises(ValueError):
        calculate_max_drawdown(empty_equity)


def test_empty_returns_are_rejected() -> None:
    empty_returns = pd.Series(
        dtype=float
    )

    with pytest.raises(ValueError):
        calculate_annualized_volatility(
            empty_returns
        )

    with pytest.raises(ValueError):
        calculate_sharpe_ratio(
            empty_returns
        )


def test_nonpositive_initial_value_is_rejected() -> None:
    equity = pd.Series(
        [100.0, 110.0],
        index=pd.date_range(
            start="2026-01-01",
            periods=2,
            freq="D",
        ),
    )

    with pytest.raises(ValueError):
        calculate_total_return(
            equity,
            initial_value=0.0,
        )

    with pytest.raises(ValueError):
        calculate_cagr(
            equity,
            initial_value=-1.0,
        )


def test_performance_metrics_returns_all_expected_metrics() -> None:
    returns = pd.Series(
        [0.0, 0.01, -0.005, 0.02],
        index=pd.date_range(
            start="2026-01-01",
            periods=4,
            freq="D",
        ),
    )

    equity = pd.Series(
        [10_000.0, 10_100.0, 10_049.5, 10_250.49],
        index=returns.index,
    )

    result = calculate_performance_metrics(
        returns=returns,
        equity=equity,
        risk_free_rate=0.0,
        initial_value=10_000.0,
    )

    assert set(result) == {
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
    }