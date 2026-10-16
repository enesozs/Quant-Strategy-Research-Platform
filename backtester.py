import numpy as np
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


TRADING_DAYS_PER_YEAR = 252


def _daily_rate(annual_rate: float) -> float:
    return (1 + annual_rate) ** (1 / TRADING_DAYS_PER_YEAR) - 1


def run_backtest(
    data: pd.DataFrame,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
    financing_spread: float = 0.01,
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

    Capital not invested in the asset earns cash_rate (annual). Exposure
    above 100% is borrowed at cash_rate plus financing_spread. Both are
    part of the gross return, so costs remain the only deduction.
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

    if cash_rate <= -1:
        raise ValueError("The cash rate must be greater than -100%.")

    cash_weight = 1.0 - result["position"]
    daily_cash_rate = _daily_rate(cash_rate)
    daily_borrow_rate = _daily_rate(cash_rate + financing_spread)

    # No time has elapsed on the first observation (its asset return is
    # undefined), so it earns nothing.
    result["cash_return"] = (
        cash_weight.clip(lower=0.0) * daily_cash_rate
        + cash_weight.clip(upper=0.0) * daily_borrow_rate
    ).where(result["asset_return"].notna())

    result["gross_strategy_return"] = (
        result["position"]
        * result["asset_return"]
        + result["cash_return"]
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
    cash_rate: float = 0.0,
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
        cash_rate=cash_rate,
    )


def run_strategy_on_window(
    data: pd.DataFrame,
    strategy_name: str,
    evaluation_start: pd.Timestamp,
    strategy_parameters: dict | None = None,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
) -> pd.DataFrame:
    """
    Backtest a strategy over the rows on or after evaluation_start, with
    indicators warmed up on every earlier row of data.

    The portfolio starts flat on the last observation before
    evaluation_start, so the first evaluated day can hold the position
    signalled by that observation and pays its entry cost. Only rows on or
    after evaluation_start are returned.
    """
    strategy_data = apply_strategy(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=strategy_parameters,
    )

    evaluation_start = pd.Timestamp(evaluation_start)
    first_location = int(
        strategy_data.index.searchsorted(evaluation_start, side="left")
    )

    if first_location >= len(strategy_data):
        raise ValueError(
            "No observations are available on or after the evaluation start."
        )

    if first_location == 0:
        raise ValueError(
            "At least one observation before the evaluation start is "
            "required so the first evaluated position has no look-ahead."
        )

    window = strategy_data.iloc[first_location - 1:].copy()

    # Both the strategy and Buy and Hold enter at the context row's close,
    # so neither may earn that row's own return.
    window.iloc[0, window.columns.get_loc("asset_return")] = np.nan

    results = run_backtest(
        data=window,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
    )

    return results.iloc[1:].copy()


def build_backtest(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str = "moving_average",
    strategy_parameters: dict | None = None,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
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
        cash_rate=cash_rate,
    )