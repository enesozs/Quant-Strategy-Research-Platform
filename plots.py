import matplotlib.pyplot as plt
import pandas as pd


def plot_price_and_moving_averages(
    results: pd.DataFrame,
    ticker: str,
) -> None:
    """
    Plot the stock price and moving averages.
    """
    plt.figure(figsize=(12, 6))

    plt.plot(
        results.index,
        results["Close"],
        label="Adjusted close",
    )

    plt.plot(
        results.index,
        results["fast_ma"],
        label="Fast moving average",
    )

    plt.plot(
        results.index,
        results["slow_ma"],
        label="Slow moving average",
    )

    plt.title(f"{ticker} Moving-Average Strategy")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


def plot_equity_curves(
    results: pd.DataFrame,
) -> None:
    """
    Compare strategy and buy-and-hold portfolio values.
    """
    plt.figure(figsize=(12, 6))

    plt.plot(
        results.index,
        results["strategy_equity"],
        label="Strategy",
    )

    plt.plot(
        results.index,
        results["buy_hold_equity"],
        label="Buy and hold",
    )

    plt.title("Portfolio Value")
    plt.xlabel("Date")
    plt.ylabel("Portfolio value")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()


def plot_drawdowns(
    results: pd.DataFrame,
) -> None:
    """
    Compare strategy and buy-and-hold drawdowns.
    """
    plt.figure(figsize=(12, 6))

    plt.plot(
        results.index,
        results["strategy_drawdown"],
        label="Strategy",
    )

    plt.plot(
        results.index,
        results["buy_hold_drawdown"],
        label="Buy and hold",
    )

    plt.title("Drawdown")
    plt.xlabel("Date")
    plt.ylabel("Drawdown")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_trading_signals(
    results: pd.DataFrame,
    ticker: str,
) -> None:
    """
    Plot the stock price with strategy entry and exit markers.
    """
    entries = results[
        results["position"].diff() == 1
    ]

    exits = results[
        results["position"].diff() == -1
    ]

    plt.figure(figsize=(12, 6))

    plt.plot(
        results.index,
        results["Close"],
        label="Adjusted close",
    )

    plt.scatter(
        entries.index,
        entries["Close"],
        marker="^",
        s=80,
        label="Buy",
    )

    plt.scatter(
        exits.index,
        exits["Close"],
        marker="v",
        s=80,
        label="Sell",
    )

    plt.title(f"{ticker} Trading Signals")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    plt.show()