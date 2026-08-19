import pandas as pd


def generate_rsi_signals(
    data: pd.DataFrame,
    window: int = 14,
    entry_threshold: float = 30,
    exit_threshold: float = 55,
) -> pd.DataFrame:
    """
    Generate long-or-cash RSI mean-reversion signals.

    Enter when RSI falls below the entry threshold.
    Exit when RSI rises above the exit threshold.
    """
    if window <= 0:
        raise ValueError("RSI window must be positive.")

    if not 0 <= entry_threshold < exit_threshold <= 100:
        raise ValueError(
            "RSI thresholds must satisfy "
            "0 <= entry < exit <= 100."
        )

    result = data.copy()

    price_change = result["Close"].diff()

    gains = price_change.clip(lower=0)
    losses = -price_change.clip(upper=0)

    average_gain = gains.ewm(
        alpha=1 / window,
        adjust=False,
        min_periods=window,
    ).mean()

    average_loss = losses.ewm(
        alpha=1 / window,
        adjust=False,
        min_periods=window,
    ).mean()

    relative_strength = average_gain / average_loss

    result["rsi"] = (
        100 - 100 / (1 + relative_strength)
    )

    # NaN means maintain the existing position.
    raw_signal = pd.Series(
        pd.NA,
        index=result.index,
        dtype="Float64",
    )

    raw_signal.loc[
        result["rsi"] < entry_threshold
    ] = 1

    raw_signal.loc[
        result["rsi"] > exit_threshold
    ] = 0

    result["signal"] = (
        raw_signal
        .ffill()
        .fillna(0)
        .astype(int)
    )

    return result