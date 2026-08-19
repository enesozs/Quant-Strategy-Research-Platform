import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def generate_volatility_targeted_momentum_signals(
    data: pd.DataFrame,
    momentum_window: int = 60,
    volatility_window: int = 20,
    target_volatility: float = 0.15,
    maximum_exposure: float = 1.0,
    momentum_threshold: float = 0.0,
) -> pd.DataFrame:
    """
    Generate momentum signals with volatility-targeted exposure.

    Exposure is positive only when momentum exceeds the selected
    threshold. Its size is scaled inversely with realized
    volatility and capped at maximum_exposure.
    """
    if momentum_window <= 1:
        raise ValueError(
            "The momentum window must be greater than one."
        )

    if volatility_window <= 1:
        raise ValueError(
            "The volatility window must be greater than one."
        )

    if target_volatility <= 0:
        raise ValueError(
            "Target volatility must be positive."
        )

    if maximum_exposure <= 0:
        raise ValueError(
            "Maximum exposure must be positive."
        )

    result = data.copy()

    result["momentum_return"] = (
        result["Close"]
        .pct_change(periods=momentum_window)
    )

    result["realized_volatility"] = (
        result["asset_return"]
        .rolling(window=volatility_window)
        .std()
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )

    volatility_scaler = (
        target_volatility
        / result["realized_volatility"]
    )

    result["volatility_scaled_exposure"] = (
        volatility_scaler
        .replace([np.inf, -np.inf], np.nan)
        .clip(
            lower=0.0,
            upper=maximum_exposure,
        )
        .fillna(0.0)
    )

    momentum_is_positive = (
        result["momentum_return"]
        > momentum_threshold
    )

    result["target_position"] = (
        result["volatility_scaled_exposure"]
        .where(momentum_is_positive, 0.0)
    )

    # Retain a binary signal for strategy summaries and tests.
    result["signal"] = (
        result["target_position"] > 0
    ).astype(int)

    return result