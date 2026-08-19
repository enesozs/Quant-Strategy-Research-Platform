import pandas as pd


def generate_adx_signals(
    data: pd.DataFrame,
    adx_window: int = 14,
    trend_window: int = 50,
    adx_threshold: float = 25.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash ADX-filtered trend signals.

    Hold the asset when:
    1. price is above its rolling trend average; and
    2. ADX indicates a sufficiently strong trend.
    """
    if adx_window <= 1:
        raise ValueError(
            "The ADX window must be greater than one."
        )

    if trend_window <= 1:
        raise ValueError(
            "The trend window must be greater than one."
        )

    if not 0 <= adx_threshold <= 100:
        raise ValueError(
            "The ADX threshold must be between 0 and 100."
        )

    result = data.copy()

    previous_close = result["Close"].shift(1)

    upward_move = result["High"].diff()
    downward_move = -result["Low"].diff()

    plus_dm = upward_move.where(
        (upward_move > downward_move)
        & (upward_move > 0),
        0.0,
    )

    minus_dm = downward_move.where(
        (downward_move > upward_move)
        & (downward_move > 0),
        0.0,
    )

    true_range_components = pd.concat(
        [
            result["High"] - result["Low"],
            (result["High"] - previous_close).abs(),
            (result["Low"] - previous_close).abs(),
        ],
        axis=1,
    )

    true_range = true_range_components.max(axis=1)

    average_true_range = true_range.ewm(
        alpha=1 / adx_window,
        adjust=False,
        min_periods=adx_window,
    ).mean()

    smoothed_plus_dm = plus_dm.ewm(
        alpha=1 / adx_window,
        adjust=False,
        min_periods=adx_window,
    ).mean()

    smoothed_minus_dm = minus_dm.ewm(
        alpha=1 / adx_window,
        adjust=False,
        min_periods=adx_window,
    ).mean()

    result["plus_di"] = (
        100 * smoothed_plus_dm / average_true_range
    )

    result["minus_di"] = (
        100 * smoothed_minus_dm / average_true_range
    )

    directional_index = (
        100
        * (
            result["plus_di"]
            - result["minus_di"]
        ).abs()
        / (
            result["plus_di"]
            + result["minus_di"]
        ).replace(0, pd.NA)
    )

    result["adx"] = directional_index.ewm(
        alpha=1 / adx_window,
        adjust=False,
        min_periods=adx_window,
    ).mean()

    result["adx_trend_average"] = (
        result["Close"]
        .rolling(window=trend_window)
        .mean()
    )

    result["signal"] = (
        (
            result["Close"]
            > result["adx_trend_average"]
        )
        & (
            result["adx"]
            >= adx_threshold
        )
        & (
            result["plus_di"]
            > result["minus_di"]
        )
    ).astype(int)

    return result