import pandas as pd


def generate_macd_signals(
    data: pd.DataFrame,
    fast_window: int = 12,
    slow_window: int = 26,
    signal_window: int = 9,
) -> pd.DataFrame:
    """
    Generate long-or-cash MACD crossover signals.
    """
    if min(
        fast_window,
        slow_window,
        signal_window,
    ) <= 0:
        raise ValueError("MACD windows must be positive.")

    if fast_window >= slow_window:
        raise ValueError(
            "The fast MACD window must be smaller "
            "than the slow window."
        )

    result = data.copy()

    result["macd_fast_ema"] = (
        result["Close"]
        .ewm(
            span=fast_window,
            adjust=False,
        )
        .mean()
    )

    result["macd_slow_ema"] = (
        result["Close"]
        .ewm(
            span=slow_window,
            adjust=False,
        )
        .mean()
    )

    result["macd"] = (
        result["macd_fast_ema"]
        - result["macd_slow_ema"]
    )

    result["macd_signal_line"] = (
        result["macd"]
        .ewm(
            span=signal_window,
            adjust=False,
        )
        .mean()
    )

    result["macd_histogram"] = (
        result["macd"]
        - result["macd_signal_line"]
    )

    result["signal"] = (
        result["macd"]
        > result["macd_signal_line"]
    ).astype(int)

    return result