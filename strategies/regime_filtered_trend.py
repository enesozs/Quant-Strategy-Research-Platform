import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def generate_regime_filtered_trend_signals(
    data: pd.DataFrame,
    trend_window: int = 100,
    volatility_window: int = 20,
    maximum_volatility: float = 0.35,
) -> pd.DataFrame:
    """
    Generate long-or-cash trend signals with a volatility filter.

    Hold the asset when:

    1. price is above its rolling trend average; and
    2. annualized realized volatility is below a threshold.
    """
    if trend_window <= 1:
        raise ValueError(
            "The trend window must be greater than one."
        )

    if volatility_window <= 1:
        raise ValueError(
            "The volatility window must be greater than one."
        )

    if maximum_volatility <= 0:
        raise ValueError(
            "Maximum volatility must be positive."
        )

    result = data.copy()

    result["regime_trend_average"] = (
        result["Close"]
        .rolling(window=trend_window)
        .mean()
    )

    result["realized_volatility"] = (
        result["asset_return"]
        .rolling(window=volatility_window)
        .std()
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    trend_condition = (
        result["Close"]
        > result["regime_trend_average"]
    )

    volatility_condition = (
        result["realized_volatility"]
        <= maximum_volatility
    )

    result["signal"] = (
        trend_condition
        & volatility_condition
    ).astype(int)

    return result