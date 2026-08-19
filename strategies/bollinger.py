import pandas as pd


def generate_bollinger_signals(
    data: pd.DataFrame,
    window: int = 20,
    number_of_std: float = 2.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash Bollinger-band mean-reversion signals.

    Enter below the lower band.
    Exit when price returns to the middle band.
    """
    if window <= 1:
        raise ValueError(
            "Bollinger window must be greater than one."
        )

    if number_of_std <= 0:
        raise ValueError(
            "The standard-deviation multiplier must be positive."
        )

    result = data.copy()

    result["bollinger_middle"] = (
        result["Close"]
        .rolling(window=window)
        .mean()
    )

    rolling_std = (
        result["Close"]
        .rolling(window=window)
        .std()
    )

    result["bollinger_upper"] = (
        result["bollinger_middle"]
        + number_of_std * rolling_std
    )

    result["bollinger_lower"] = (
        result["bollinger_middle"]
        - number_of_std * rolling_std
    )

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["Close"] < result["bollinger_lower"]
    ] = 1

    raw_signal.loc[
        result["Close"] >= result["bollinger_middle"]
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result