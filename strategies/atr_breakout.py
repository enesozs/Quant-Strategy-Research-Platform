import pandas as pd


def generate_atr_breakout_signals(
    data: pd.DataFrame,
    atr_window: int = 14,
    trend_window: int = 20,
    atr_multiplier: float = 1.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash volatility-adjusted breakout signals.

    Enter when price rises above the previous rolling mean plus
    an ATR multiple. Exit when price falls below the previous
    rolling mean.
    """
    if atr_window <= 1 or trend_window <= 1:
        raise ValueError(
            "ATR and trend windows must be greater than one."
        )

    if atr_multiplier <= 0:
        raise ValueError(
            "The ATR multiplier must be positive."
        )

    result = data.copy()

    previous_close = result["Close"].shift(1)

    true_range_components = pd.concat(
        [
            result["High"] - result["Low"],
            (result["High"] - previous_close).abs(),
            (result["Low"] - previous_close).abs(),
        ],
        axis=1,
    )

    result["true_range"] = (
        true_range_components.max(axis=1)
    )

    result["atr"] = (
        result["true_range"]
        .rolling(window=atr_window)
        .mean()
    )

    result["atr_trend_mean"] = (
        result["Close"]
        .rolling(window=trend_window)
        .mean()
        .shift(1)
    )

    result["atr_entry_level"] = (
        result["atr_trend_mean"]
        + atr_multiplier * result["atr"].shift(1)
    )

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["Close"] > result["atr_entry_level"]
    ] = 1

    raw_signal.loc[
        result["Close"] < result["atr_trend_mean"]
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result