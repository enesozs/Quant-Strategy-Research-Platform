import pandas as pd


def generate_moving_average_signals(
    data: pd.DataFrame,
    fast_window: int = 20,
    slow_window: int = 50,
) -> pd.DataFrame:
    """
    Generate long-or-cash simple moving-average crossover signals.
    """
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("Moving-average windows must be positive.")

    if fast_window >= slow_window:
        raise ValueError(
            "The fast window must be smaller than the slow window."
        )

    result = data.copy()

    result["fast_ma"] = (
        result["Close"]
        .rolling(window=fast_window)
        .mean()
    )

    result["slow_ma"] = (
        result["Close"]
        .rolling(window=slow_window)
        .mean()
    )

    result["signal"] = (
        result["fast_ma"] > result["slow_ma"]
    ).astype(int)

    return result