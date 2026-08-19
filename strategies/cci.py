import pandas as pd


def generate_cci_signals(
    data: pd.DataFrame,
    window: int = 20,
    entry_threshold: float = -100.0,
    exit_threshold: float = 0.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash CCI mean-reversion signals.

    Enter when CCI falls below the entry threshold.
    Exit when CCI reverts to or above the exit threshold.
    """
    if window <= 1:
        raise ValueError(
            "The CCI window must be greater than one."
        )

    if entry_threshold >= exit_threshold:
        raise ValueError(
            "The CCI entry threshold must be smaller "
            "than the exit threshold."
        )

    result = data.copy()

    result["typical_price"] = (
        result["High"]
        + result["Low"]
        + result["Close"]
    ) / 3

    result["cci_average"] = (
        result["typical_price"]
        .rolling(window=window)
        .mean()
    )

    mean_deviation = (
        result["typical_price"]
        .rolling(window=window)
        .apply(
            lambda values: (
                abs(values - values.mean())
            ).mean(),
            raw=True,
        )
    )

    result["cci"] = (
        result["typical_price"]
        - result["cci_average"]
    ) / (
        0.015
        * mean_deviation.replace(0, pd.NA)
    )

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["cci"] < entry_threshold
    ] = 1

    raw_signal.loc[
        result["cci"] >= exit_threshold
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result