import pandas as pd


def generate_multi_timeframe_trend_signals(
    data: pd.DataFrame,
    daily_window: int = 50,
    weekly_window: int = 20,
) -> pd.DataFrame:
    """
    Generate long-or-cash multi-timeframe trend signals.

    Hold the asset only when:

    1. daily close is above its daily moving average; and
    2. the most recently completed weekly close is above its
       weekly moving average.
    """
    if daily_window <= 1:
        raise ValueError(
            "The daily window must be greater than one."
        )

    if weekly_window <= 1:
        raise ValueError(
            "The weekly window must be greater than one."
        )

    result = data.copy()

    result["daily_trend_average"] = (
        result["Close"]
        .rolling(window=daily_window)
        .mean()
    )

    weekly_close = (
        result["Close"]
        .resample("W-FRI")
        .last()
    )

    weekly_average = (
        weekly_close
        .rolling(window=weekly_window)
        .mean()
    )

    weekly_trend = (
        weekly_close > weekly_average
    )

    # Align the most recently completed weekly signal with
    # each daily observation.
    result["weekly_trend_signal"] = (
        weekly_trend
        .reindex(result.index, method="ffill")
        .fillna(False)
        .astype(int)
    )

    result["weekly_close"] = (
        weekly_close
        .reindex(result.index, method="ffill")
    )

    result["weekly_trend_average"] = (
        weekly_average
        .reindex(result.index, method="ffill")
    )

    daily_trend = (
        result["Close"]
        > result["daily_trend_average"]
    )

    result["signal"] = (
        daily_trend
        & result["weekly_trend_signal"].astype(bool)
    ).astype(int)

    return result