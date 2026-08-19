import pandas as pd


def generate_momentum_signals(
    data: pd.DataFrame,
    lookback_window: int = 60,
    threshold: float = 0.0,
) -> pd.DataFrame:
    """
    Generate long-or-cash price-momentum signals.

    Hold the asset when its lookback-period return exceeds
    the selected threshold.
    """
    if lookback_window <= 0:
        raise ValueError(
            "Momentum lookback window must be positive."
        )

    result = data.copy()

    result["momentum_return"] = (
        result["Close"]
        .pct_change(periods=lookback_window)
    )

    result["signal"] = (
        result["momentum_return"] > threshold
    ).astype(int)

    return result