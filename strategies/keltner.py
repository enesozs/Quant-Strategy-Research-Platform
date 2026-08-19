import pandas as pd


def generate_keltner_signals(
    data: pd.DataFrame,
    ema_window: int = 20,
    atr_window: int = 14,
    atr_multiplier: float = 2.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash Keltner Channel breakout signals.

    Enter when price closes above the previous upper channel.
    Exit when price closes below the previous middle channel.
    """
    if ema_window <= 1:
        raise ValueError(
            "The EMA window must be greater than one."
        )

    if atr_window <= 1:
        raise ValueError(
            "The ATR window must be greater than one."
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

    result["keltner_true_range"] = (
        true_range_components.max(axis=1)
    )

    result["keltner_atr"] = (
        result["keltner_true_range"]
        .ewm(
            alpha=1 / atr_window,
            adjust=False,
            min_periods=atr_window,
        )
        .mean()
    )

    result["keltner_middle"] = (
        result["Close"]
        .ewm(
            span=ema_window,
            adjust=False,
            min_periods=ema_window,
        )
        .mean()
    )

    result["keltner_upper"] = (
        result["keltner_middle"]
        + atr_multiplier * result["keltner_atr"]
    )

    result["keltner_lower"] = (
        result["keltner_middle"]
        - atr_multiplier * result["keltner_atr"]
    )

    # Use yesterday's channel values for today's decision.
    previous_upper = result["keltner_upper"].shift(1)
    previous_middle = result["keltner_middle"].shift(1)

    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["Close"] > previous_upper
    ] = 1

    raw_signal.loc[
        result["Close"] < previous_middle
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result