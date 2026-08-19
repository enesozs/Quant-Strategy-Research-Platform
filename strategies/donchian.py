import pandas as pd


def generate_donchian_signals(
    data: pd.DataFrame,
    entry_window: int = 50,
    exit_window: int = 20,
) -> pd.DataFrame:
    """
    Generate long-or-cash Donchian-channel breakout signals.

    Enter when price exceeds the previous entry-window high.
    Exit when price falls below the previous exit-window low.
    """
    if entry_window <= 0 or exit_window <= 0:
        raise ValueError(
            "Donchian windows must be positive."
        )

    result = data.copy()

    # Shift by one day so today's price is not included in
    # the level used to determine today's breakout.
    result["donchian_entry_high"] = (
        result["High"]
        .rolling(window=entry_window)
        .max()
        .shift(1)
    )

    result["donchian_exit_low"] = (
        result["Low"]
        .rolling(window=exit_window)
        .min()
        .shift(1)
    )

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["Close"] > result["donchian_entry_high"]
    ] = 1

    raw_signal.loc[
        result["Close"] < result["donchian_exit_low"]
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result