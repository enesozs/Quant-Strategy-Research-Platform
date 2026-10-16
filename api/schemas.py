"""Pydantic v2 request models for the API (see api/CONTRACT.md)."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from strategies import STRATEGIES

Objective = Literal[
    "sharpe_ratio",
    "total_return",
    "cagr",
    "annualized_volatility",
    "max_drawdown",
    "calmar_ratio",
]
PairsMethod = Literal["distance", "cointegration", "kalman"]

MAX_GRID_COMBINATIONS = 5_000

_TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-^=]{1,20}$")

Ticker = Annotated[str, Field(min_length=1, max_length=20)]
ParameterValue = Annotated[float, Field(allow_inf_nan=False)]
PairsParamValue = float | int | bool | str | None


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not _TICKER_PATTERN.match(ticker):
        raise ValueError(
            f"'{value}' is not a valid ticker symbol (letters, digits, '.', '-', '^', '=')."
        )
    return ticker


class _Request(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Assumptions(_Request):
    start_date: dt.date
    end_date: dt.date
    initial_capital: float = Field(default=10_000, gt=0, le=1e12)
    transaction_cost_bps: float = Field(default=10, ge=0, le=1_000)
    risk_free_rate: float = Field(default=0.0, ge=-0.5, le=1.0)
    cash_earns_risk_free: bool = True

    @model_validator(mode="after")
    def _check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date must be after start_date.")
        if self.start_date < dt.date(1950, 1, 1):
            raise ValueError("start_date must be on or after 1950-01-01.")
        return self

    @property
    def cash_rate(self) -> float:
        return self.risk_free_rate if self.cash_earns_risk_free else 0.0

    @property
    def start(self) -> str:
        return self.start_date.isoformat()

    @property
    def end(self) -> str:
        return self.end_date.isoformat()


class MarketRequest(Assumptions):
    ticker: Ticker

    @field_validator("ticker")
    @classmethod
    def _ticker(cls, value: str) -> str:
        return normalize_ticker(value)


class _StrategyRequest(MarketRequest):
    strategy: str

    @field_validator("strategy")
    @classmethod
    def _strategy(cls, value: str) -> str:
        if value not in STRATEGIES:
            available = ", ".join(sorted(STRATEGIES))
            raise ValueError(f"Unknown strategy '{value}'. Available: {available}.")
        return value


Grid = dict[str, Annotated[list[ParameterValue], Field(min_length=1, max_length=500)]]


class BacktestRequest(_StrategyRequest):
    parameters: dict[str, ParameterValue] | None = None


class CompareRequest(MarketRequest):
    use_optimized_parameters: bool = False
    objective: Objective = "sharpe_ratio"


class OptimizeRequest(_StrategyRequest):
    objective: Objective = "sharpe_ratio"
    mode: Literal["predefined", "custom", "coarse_to_fine"] = "predefined"
    grid: Grid | None = None
    refinement_points: int = Field(default=5, ge=3, le=15)

    @model_validator(mode="after")
    def _grid_required(self):
        if self.mode == "custom" and not self.grid:
            raise ValueError("A grid is required when mode is 'custom'.")
        return self


class ValidateSplitRequest(_StrategyRequest):
    objective: Objective = "sharpe_ratio"
    split_date: dt.date
    grid: Grid | None = None

    @model_validator(mode="after")
    def _split_inside(self):
        if not self.start_date < self.split_date < self.end_date:
            raise ValueError(
                "split_date must fall strictly between start_date and end_date."
            )
        return self


class WalkForwardRequest(_StrategyRequest):
    objective: Objective = "sharpe_ratio"
    window_type: Literal["expanding", "rolling"] = "expanding"
    initial_training_years: int = Field(default=2, ge=1, le=30)
    test_window_years: int = Field(default=1, ge=1, le=10)


class PairsAssumptions(Assumptions):
    borrow_fee: float = Field(default=0.0, ge=0.0, le=1.0)


class PairsResearchRequest(PairsAssumptions):
    method: PairsMethod
    ticker_a: Ticker
    ticker_b: Ticker
    params: dict[str, PairsParamValue] | None = None

    @field_validator("ticker_a", "ticker_b")
    @classmethod
    def _ticker(cls, value: str) -> str:
        return normalize_ticker(value)

    @model_validator(mode="after")
    def _distinct(self):
        if self.ticker_a == self.ticker_b:
            raise ValueError("Pairs trading requires two different tickers.")
        return self


class PairsUniverseRequest(PairsAssumptions):
    method: PairsMethod
    tickers: Annotated[list[Ticker], Field(min_length=2, max_length=40)]
    formation_years: int = Field(default=2, ge=1, le=10)
    top_n: int | None = Field(default=None, ge=1, le=50)
    params: dict[str, PairsParamValue] | None = None

    @field_validator("tickers")
    @classmethod
    def _tickers(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            ticker = normalize_ticker(value)
            if ticker not in cleaned:
                cleaned.append(ticker)
        if len(cleaned) < 2:
            raise ValueError("At least two distinct tickers are required.")
        return cleaned
