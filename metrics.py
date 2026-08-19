import numpy as np
import pandas as pd


TRADING_DAYS_PER_YEAR = 252


def calculate_total_return(
    equity: pd.Series,
    initial_value: float | None = None,
) -> float:
    """
    Calculate the total return over the complete period.

    initial_value may be supplied when the first observed equity
    value already reflects an initial transaction cost.
    """
    if equity.empty:
        raise ValueError("Equity series cannot be empty.")

    starting_value = (
        float(initial_value)
        if initial_value is not None
        else float(equity.iloc[0])
    )

    if starting_value <= 0:
        raise ValueError("Initial equity value must be positive.")

    return float(equity.iloc[-1]) / starting_value - 1


def calculate_cagr(
    equity: pd.Series,
    initial_value: float | None = None,
) -> float:
    """
    Calculate compound annual growth rate.

    initial_value may be supplied when the first observed equity
    value already reflects an initial transaction cost.
    """
    if equity.empty:
        raise ValueError("Equity series cannot be empty.")

    number_of_days = (equity.index[-1] - equity.index[0]).days

    if number_of_days <= 0:
        raise ValueError(
            "The equity series must cover more than one date."
        )

    number_of_years = number_of_days / 365.25

    starting_value = (
        float(initial_value)
        if initial_value is not None
        else float(equity.iloc[0])
    )

    if starting_value <= 0:
        raise ValueError("Initial equity value must be positive.")

    return (
        float(equity.iloc[-1]) / starting_value
    ) ** (1 / number_of_years) - 1


def calculate_annualized_volatility(
    returns: pd.Series,
) -> float:
    """
    Calculate annualized volatility from daily returns.
    """
    clean_returns = returns.dropna()

    if clean_returns.empty:
        raise ValueError("Returns series cannot be empty.")

    return (
        clean_returns.std(ddof=1)
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> float:
    """
    Calculate the annualized Sharpe ratio.

    risk_free_rate is expressed as an annual decimal rate.
    For example, 0.03 means 3%.
    """
    clean_returns = returns.dropna()

    if clean_returns.empty:
        raise ValueError("Returns series cannot be empty.")

    daily_risk_free_rate = (
        (1 + risk_free_rate)
        ** (1 / TRADING_DAYS_PER_YEAR)
        - 1
    )

    excess_returns = clean_returns - daily_risk_free_rate

    daily_volatility = excess_returns.std(ddof=1)

    if np.isclose(daily_volatility, 0.0):
        return np.nan

    return (
        excess_returns.mean()
        / daily_volatility
        * np.sqrt(TRADING_DAYS_PER_YEAR)
    )


def calculate_max_drawdown(
    equity: pd.Series,
    initial_value: float | None = None,
) -> float:
    """
    Calculate the largest peak-to-trough decline.

    initial_value may be supplied so an initial transaction cost
    is included in drawdown relative to starting capital.
    """
    if equity.empty:
        raise ValueError("Equity series cannot be empty.")

    running_peak = equity.cummax()

    if initial_value is not None:
        running_peak = running_peak.clip(
            lower=float(initial_value)
        )

    drawdown = equity / running_peak - 1

    return drawdown.min()


def calculate_performance_metrics(
    returns: pd.Series,
    equity: pd.Series,
    risk_free_rate: float = 0.0,
    initial_value: float | None = None,
) -> dict[str, float]:
    """
    Calculate the main performance metrics for a strategy.
    """
    return {
        "total_return": calculate_total_return(
            equity,
            initial_value=initial_value,
        ),
        "cagr": calculate_cagr(
            equity,
            initial_value=initial_value,
        ),
        "annualized_volatility": calculate_annualized_volatility(
            returns
        ),
        "sharpe_ratio": calculate_sharpe_ratio(
            returns,
            risk_free_rate=risk_free_rate,
        ),
        "max_drawdown": calculate_max_drawdown(
            equity,
            initial_value=initial_value,
        ),
    }