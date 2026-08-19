import pandas as pd
import yfinance as yf

from strategies import apply_strategy


def download_data(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Download adjusted historical market data for one ticker.
    """
    downloaded_data = yf.download(
        ticker,
        start=start_date,
        end=end_date,
        auto_adjust=True,
        progress=False,
        multi_level_index=False,
    )

    if downloaded_data is None:
        raise ValueError(
            f"The download failed for ticker '{ticker}'."
        )

    if downloaded_data.empty:
        raise ValueError(
            f"No data was returned for ticker '{ticker}'."
        )

    return downloaded_data


def calculate_returns(data: pd.DataFrame) -> pd.DataFrame:
    """
    Add daily simple returns to a market-data DataFrame.
    """
    result = data.copy()

    result["asset_return"] = result["Close"].pct_change()

    return result


def run_backtest(
    data: pd.DataFrame,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
) -> pd.DataFrame:
    """
    Calculate strategy returns, transaction costs,
    equity curves, and drawdowns.

    Strategies may provide either:

    - signal: binary long-or-cash values;
    - target_position: continuous desired exposure.

    The chosen exposure is shifted by one trading day to
    prevent look-ahead bias.

    Transaction costs are modeled as one-way proportional
    costs on changes in portfolio exposure. Buy and Hold is
    treated as an executable benchmark and pays one initial
    one-way transaction cost when the position is established.
    """
    if initial_capital <= 0:
        raise ValueError("Initial capital must be positive.")

    if transaction_cost_bps < 0:
        raise ValueError(
            "Transaction costs cannot be negative."
        )

    result = data.copy()

    if "target_position" in result.columns:
        desired_position = result["target_position"]
    elif "signal" in result.columns:
        desired_position = result["signal"]
    else:
        raise ValueError(
            "Strategy data must contain either a 'signal' "
            "or 'target_position' column."
        )

    desired_position = (
        desired_position
        .astype(float)
        .fillna(0.0)
    )

    if (desired_position < 0).any():
        raise ValueError(
            "Long-only strategy positions cannot be negative."
        )

    # Today's calculated target becomes tomorrow's position.
    result["position"] = (
        desired_position
        .shift(1)
        .fillna(0.0)
    )

    # For continuous positions, this is one-way portfolio
    # turnover rather than a literal count of full trades.
    result["trade"] = (
        result["position"]
        .diff()
        .abs()
        .fillna(result["position"].abs())
    )

    transaction_cost_rate = (
        transaction_cost_bps / 10_000
    )

    result["gross_strategy_return"] = (
        result["position"]
        * result["asset_return"]
    )

    result["transaction_cost"] = (
        result["trade"]
        * transaction_cost_rate
    )

    result["strategy_return"] = (
        result["gross_strategy_return"]
        - result["transaction_cost"]
    )

    result["strategy_equity"] = (
        initial_capital
        * (
            1
            + result["strategy_return"].fillna(0)
        ).cumprod()
    )

    result["buy_hold_turnover"] = 0.0

    if not result.empty:
        first_index = result.index[0]
        result.loc[
            first_index,
            "buy_hold_turnover",
        ] = 1.0

    result["buy_hold_transaction_cost"] = (
        result["buy_hold_turnover"]
        * transaction_cost_rate
    )

    result["buy_hold_return"] = (
        result["asset_return"].fillna(0.0)
        - result["buy_hold_transaction_cost"]
    )

    result["buy_hold_equity"] = (
        initial_capital
        * (
            1
            + result["buy_hold_return"]
        ).cumprod()
    )

    result["strategy_peak"] = (
        result["strategy_equity"]
        .cummax()
        .clip(lower=initial_capital)
    )

    result["strategy_drawdown"] = (
        result["strategy_equity"]
        / result["strategy_peak"]
        - 1
    )

    result["buy_hold_peak"] = (
        result["buy_hold_equity"]
        .cummax()
        .clip(lower=initial_capital)
    )

    result["buy_hold_drawdown"] = (
        result["buy_hold_equity"]
        / result["buy_hold_peak"]
        - 1
    )

    return result


def prepare_market_data(
    ticker: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    Download market data and calculate asset returns.
    """
    data = download_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return calculate_returns(data)


def run_strategy_on_data(
    data: pd.DataFrame,
    strategy_name: str,
    strategy_parameters: dict | None = None,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
) -> pd.DataFrame:
    """
    Apply one strategy to prepared market data and backtest it.
    """
    strategy_data = apply_strategy(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=strategy_parameters,
    )

    return run_backtest(
        data=strategy_data,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )


def build_backtest(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str = "moving_average",
    strategy_parameters: dict | None = None,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
) -> pd.DataFrame:
    """
    Download data and run one complete strategy backtest.
    """
    data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return run_strategy_on_data(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=strategy_parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )