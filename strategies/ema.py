import pandas as pd


def generate_ema_signals(
    data: pd.DataFrame,
    fast_window: int = 12,
    slow_window: int = 26,
) -> pd.DataFrame:
    """
    Generate long-or-cash exponential moving-average signals.
    """
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("EMA windows must be positive.")

    if fast_window >= slow_window:
        raise ValueError(
            "The fast EMA window must be smaller "
            "than the slow EMA window."
        )

    result = data.copy()

    result["fast_ema"] = (
        result["Close"]
        .ewm(
            span=fast_window,
            adjust=False,
        )
        .mean()
    )

    result["slow_ema"] = (
        result["Close"]
        .ewm(
            span=slow_window,
            adjust=False,
        )
        .mean()
    )

    result["signal"] = (
        result["fast_ema"] > result["slow_ema"]
    ).astype(int)

    return result