import pandas as pd


def generate_stochastic_signals(
    data: pd.DataFrame,
    window: int = 14,
    entry_threshold: float = 20,
    exit_threshold: float = 80,
) -> pd.DataFrame:
    """
    Generate long-or-cash stochastic mean-reversion signals.

    Enter when the stochastic oscillator falls below the
    entry threshold. Exit when it rises above the exit threshold.
    """
    if window <= 1:
        raise ValueError(
            "The stochastic window must be greater than one."
        )

    if not 0 <= entry_threshold < exit_threshold <= 100:
        raise ValueError(
            "Thresholds must satisfy "
            "0 <= entry < exit <= 100."
        )

    result = data.copy()

    rolling_low = (
        result["Low"]
        .rolling(window=window)
        .min()
    )

    rolling_high = (
        result["High"]
        .rolling(window=window)
        .max()
    )

    price_range = rolling_high - rolling_low

    result["stochastic_k"] = (
        100
        * (result["Close"] - rolling_low)
        / price_range.replace(0, pd.NA)
    )

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["stochastic_k"] < entry_threshold
    ] = 1

    raw_signal.loc[
        result["stochastic_k"] > exit_threshold
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result