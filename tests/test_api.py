"""Offline tests for the FastAPI backend (api/). Market data is synthetic."""

from __future__ import annotations

import json
import math
import zlib

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

import backtester
from api import cache
from api.main import app
from api.serialize import frame_to_rows, metrics_to_json, to_jsonable, to_timeseries


def _synthetic_ohlc(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Deterministic prices: a shared random walk plus a mean-reverting,
    ticker-specific residual, so every pair is (noisily) cointegrated."""
    if ticker.upper().startswith("BAD"):
        raise ValueError(f"No data was returned for ticker '{ticker}'.")

    full_index = pd.bdate_range("2010-01-01", "2030-12-31")
    common = np.random.default_rng(7).normal(0.0004, 0.011, len(full_index)).cumsum()

    seed = zlib.crc32(ticker.upper().encode())
    rng = np.random.default_rng(seed)
    residual = np.zeros(len(full_index))
    shocks = rng.normal(0.0, 0.01, len(full_index))
    for row in range(1, len(full_index)):
        residual[row] = 0.9 * residual[row - 1] + shocks[row]
    loading = 0.8 + (seed % 5) / 10
    level = 3.0 + (seed % 7) / 3
    close = np.exp(level + loading * common + residual)

    frame = pd.DataFrame(
        {
            "Open": close * (1 + rng.normal(0, 0.002, len(full_index))),
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": 1_000_000.0,
        },
        index=full_index,
    )
    window = frame.loc[
        (frame.index >= pd.Timestamp(start_date))
        & (frame.index < pd.Timestamp(end_date))
    ]
    if window.empty:
        raise ValueError(f"No data was returned for ticker '{ticker}'.")
    return window.copy()


@pytest.fixture(autouse=True)
def offline_market_data(monkeypatch):
    calls: list[tuple[str, str, str]] = []

    def fake_download(ticker, start_date, end_date):
        calls.append((ticker, start_date, end_date))
        return _synthetic_ohlc(ticker, start_date, end_date)

    monkeypatch.setattr(backtester, "download_data", fake_download)
    cache.install()
    cache.clear()
    yield calls
    cache.clear()


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


MARKET = {
    "ticker": "TEST",
    "start_date": "2018-01-01",
    "end_date": "2021-12-31",
    "initial_capital": 10_000,
    "transaction_cost_bps": 10,
    "risk_free_rate": 0.02,
}
PAIRS = {"start_date": "2017-01-01", "end_date": "2021-12-31", "borrow_fee": 0.01}
METRIC_KEYS = {
    "total_return",
    "cagr",
    "annualized_volatility",
    "sharpe_ratio",
    "max_drawdown",
    "calmar_ratio",
}


def _strict_json(response) -> dict:
    """Parse with NaN/Infinity disallowed, as a browser's JSON.parse would."""

    def reject(token):
        raise AssertionError(f"Non-standard JSON constant {token!r} in response")

    return json.loads(response.text, parse_constant=reject)


def _assert_timeseries(series: dict, required: set[str] = frozenset()) -> None:
    assert set(series) == {"dates", "columns"}
    assert required <= set(series["columns"]), set(series["columns"])
    for values in series["columns"].values():
        assert len(values) == len(series["dates"])
    if series["dates"]:
        pd.Timestamp(series["dates"][0])
        assert len(series["dates"][0]) == 10


# --------------------------------------------------------------------------
# Serialization helpers
# --------------------------------------------------------------------------


def test_serialization_maps_non_finite_to_null() -> None:
    frame = pd.DataFrame(
        {"a": [1.0, np.nan, np.inf], "b": [np.int64(2), np.int64(3), np.int64(4)]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    series = to_timeseries(frame)
    assert series["dates"] == ["2024-01-01", "2024-01-02", "2024-01-03"]
    assert series["columns"]["a"] == [1.0, None, None]
    assert series["columns"]["b"] == [2.0, 3.0, 4.0]

    rows = frame_to_rows(frame.assign(when=frame.index, flag=np.bool_(True)))
    assert rows[1]["a"] is None and rows[2]["a"] is None
    assert rows[0]["when"] == "2024-01-01" and rows[0]["flag"] is True
    assert isinstance(rows[0]["b"], int)

    payload = to_jsonable(
        {"x": np.float64("nan"), "y": [np.float32(1.5), pd.NaT], "z": -np.inf}
    )
    assert payload == {"x": None, "y": [1.5, None], "z": None}
    json.dumps(payload, allow_nan=False)

    metrics = metrics_to_json({"sharpe_ratio": np.nan, "turnover": 3})
    assert set(METRIC_KEYS) <= set(metrics) and metrics["sharpe_ratio"] is None
    assert metrics["turnover"] == 3.0


# --------------------------------------------------------------------------
# Meta / health
# --------------------------------------------------------------------------


def test_health(client) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_meta_shape(client) -> None:
    body = _strict_json(client.get("/api/meta"))
    assert set(body) == {
        "strategies",
        "objectives",
        "pairs_methods",
        "universe_presets",
    }
    assert len(body["strategies"]) == 15

    ma = next(item for item in body["strategies"] if item["key"] == "moving_average")
    for field in (
        "display_name",
        "family",
        "subtype",
        "features",
        "signal_style",
        "best_suited_for",
        "description",
        "thesis",
        "favorable_environment",
        "unfavorable_environment",
        "main_risks",
        "optimization_notes",
        "validation_focus",
        "related_strategies",
        "parameters",
        "default_grid",
        "grid_size",
    ):
        assert field in ma
    assert ma["parameters"]["fast_window"]["type"] == "int"
    assert {"label", "default", "min", "max", "step"} <= set(
        ma["parameters"]["fast_window"]
    )
    assert ma["grid_size"] == 64

    vtm = next(
        item
        for item in body["strategies"]
        if item["key"] == "volatility_targeted_momentum"
    )
    assert any(spec.get("format") == "percent" for spec in vtm["parameters"].values())

    objectives = {item["key"]: item for item in body["objectives"]}
    assert set(objectives) == METRIC_KEYS
    assert objectives["annualized_volatility"]["higher_is_better"] is False
    assert [m["key"] for m in body["pairs_methods"]] == [
        "distance",
        "cointegration",
        "kalman",
    ]
    assert "Beverages & snacks" in body["universe_presets"]


# --------------------------------------------------------------------------
# Single-asset research
# --------------------------------------------------------------------------


def test_backtest_returns_series_overlays_and_oscillators(client) -> None:
    response = client.post(
        "/api/backtest",
        json={**MARKET, "strategy": "bollinger", "parameters": {"window": 25}},
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert body["strategy"] == "bollinger"
    assert body["parameters"] == {"window": 25, "number_of_std": 2.0}
    assert {"rebalancing_days", "turnover", "average_exposure", "final_value"} <= set(
        body["metrics"]
    )
    assert METRIC_KEYS <= set(body["benchmark_metrics"])

    _assert_timeseries(
        body["series"],
        {
            "close",
            "position",
            "strategy_equity",
            "buy_hold_equity",
            "strategy_drawdown",
            "buy_hold_drawdown",
        },
    )
    _assert_timeseries(
        body["overlays"], {"bollinger_middle", "bollinger_upper", "bollinger_lower"}
    )
    assert "signal" not in body["overlays"]["columns"]
    assert body["oscillators"]["columns"] == {}


def test_backtest_classifies_oscillators(client) -> None:
    body = _strict_json(
        client.post("/api/backtest", json={**MARKET, "strategy": "adx"})
    )
    assert "adx_trend_average" in body["overlays"]["columns"]
    assert {"adx", "plus_di", "minus_di"} <= set(body["oscillators"]["columns"])


def test_backtest_never_trading_serialises_nan_as_null(client) -> None:
    response = client.post(
        "/api/backtest",
        json={
            **MARKET,
            "risk_free_rate": 0.0,
            "strategy": "momentum",
            "parameters": {"threshold": 5.0},
        },
    )
    assert response.status_code == 200, response.text
    assert "NaN" not in response.text and "Infinity" not in response.text
    body = _strict_json(response)
    assert body["metrics"]["sharpe_ratio"] is None
    assert body["metrics"]["calmar_ratio"] is None
    # The indicator warm-up rows are null, not NaN.
    assert body["oscillators"]["columns"]["momentum_return"][0] is None


def test_market_data_is_cached(client, offline_market_data) -> None:
    for _ in range(3):
        assert (
            client.post("/api/backtest", json={**MARKET, "strategy": "ema"}).status_code
            == 200
        )
    assert len(offline_market_data) == 1


def test_compare(client) -> None:
    response = client.post("/api/compare", json=MARKET)
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert body["in_sample"] is False
    keys = {row["strategy"] for row in body["rows"]}
    assert "moving_average" in keys and len(keys) == 16  # 15 strategies + buy_and_hold
    row = body["rows"][0]
    for column in (
        "strategy",
        "display_name",
        "family",
        "parameters",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "calmar_ratio",
        "trades",
        "turnover",
        "average_exposure",
        "return_rank",
        "cagr_rank",
        "sharpe_rank",
        "volatility_rank",
        "drawdown_rank",
    ):
        assert column in row
    assert isinstance(row["parameters"], str)
    assert METRIC_KEYS <= set(body["benchmark"])
    _assert_timeseries(body["equity"], {"moving_average", "rsi", "buy_hold"})
    assert len(body["equity"]["columns"]) == 16


def test_optimize_predefined(client) -> None:
    response = client.post(
        "/api/optimize",
        json={**MARKET, "strategy": "moving_average", "objective": "sharpe_ratio"},
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert body["objective"] == "sharpe_ratio"
    assert body["combinations_tested"] == len(body["results"]) > 0
    pd.Timestamp(body["evaluation_start"])
    assert set(body["best_parameters"]) == {"fast_window", "slow_window"}
    assert body["default_parameters"] == {"fast_window": 20, "slow_window": 50}
    assert METRIC_KEYS <= set(body["best_metrics"])
    assert "robustness_label" in body["robustness"]
    assert isinstance(body["robustness"]["robust_candidate_parameters"], dict)
    assert isinstance(body["robustness"]["boundary_parameters"], list)

    sharpe = [
        row["sharpe_ratio"]
        for row in body["results"]
        if row["sharpe_ratio"] is not None
    ]
    assert sharpe == sorted(sharpe, reverse=True)

    heatmap = body["heatmap"]
    assert {heatmap["x_parameter"], heatmap["y_parameter"]} == {
        "fast_window",
        "slow_window",
    }
    assert len(heatmap["z"]) == len(heatmap["y_values"])
    assert all(len(row) == len(heatmap["x_values"]) for row in heatmap["z"])
    best = max(value for row in heatmap["z"] for value in row if value is not None)
    assert best == pytest.approx(body["best_metrics"]["sharpe_ratio"])

    assert set(body["profiles"]) == {"fast_window", "slow_window"}
    point = body["profiles"]["fast_window"][0]
    assert set(point) == {"value", "best", "median"}
    assert "stages" not in body


def test_optimize_custom_grid_and_single_parameter(client) -> None:
    body = _strict_json(
        client.post(
            "/api/optimize",
            json={
                **MARKET,
                "strategy": "rsi",
                "objective": "annualized_volatility",
                "mode": "custom",
                "grid": {
                    "window": [10, 14],
                    "entry_threshold": [25, 30, 35],
                    "exit_threshold": [60],
                },
            },
        )
    )
    assert body["combinations_tested"] == 6
    # exit_threshold has one value, so the heatmap uses the other two.
    assert {body["heatmap"]["x_parameter"], body["heatmap"]["y_parameter"]} == {
        "window",
        "entry_threshold",
    }
    assert body["best_parameters"]["window"] in (10, 14)

    single = _strict_json(
        client.post(
            "/api/optimize",
            json={
                **MARKET,
                "strategy": "momentum",
                "mode": "custom",
                "grid": {"lookback_window": [20, 60]},
            },
        )
    )
    assert single["heatmap"] is None
    assert [p["value"] for p in single["profiles"]["lookback_window"]] == [20, 60]


def test_optimize_coarse_to_fine(client) -> None:
    body = _strict_json(
        client.post(
            "/api/optimize",
            json={
                **MARKET,
                "strategy": "moving_average",
                "mode": "coarse_to_fine",
                "grid": {"fast_window": [10, 30], "slow_window": [60, 120]},
                "refinement_points": 3,
            },
        )
    )
    stages = body["stages"]
    assert stages["broad_combinations"] == 4
    assert (
        body["combinations_tested"]
        == stages["broad_combinations"] + stages["refined_combinations"]
    )
    assert set(stages["refined_grid"]) == {"fast_window", "slow_window"}


def test_optimize_rejects_oversized_or_invalid_grids(client) -> None:
    oversized = client.post(
        "/api/optimize",
        json={
            **MARKET,
            "strategy": "moving_average",
            "mode": "custom",
            "grid": {
                "fast_window": list(range(2, 102)),
                "slow_window": list(range(110, 170)),
            },
        },
    )
    assert oversized.status_code == 422
    assert "6,000" in oversized.json()["detail"]

    missing = client.post(
        "/api/optimize", json={**MARKET, "strategy": "ema", "mode": "custom"}
    )
    assert missing.status_code == 422 and "grid" in missing.json()["detail"]

    unknown = client.post(
        "/api/optimize",
        json={**MARKET, "strategy": "ema", "mode": "custom", "grid": {"speed": [1, 2]}},
    )
    assert unknown.status_code == 422 and "speed" in unknown.json()["detail"]


def test_validate_split(client) -> None:
    response = client.post(
        "/api/validate/split",
        json={
            **MARKET,
            "strategy": "moving_average",
            "split_date": "2020-06-01",
            "grid": {"fast_window": [10, 20], "slow_window": [50, 100]},
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert body["split_date"] == "2020-06-01"
    pd.Timestamp(body["training_evaluation_start"])
    assert isinstance(body["robustness_label"], str)
    assert [item["label"] for item in body["parameter_sets"]] == [
        "Default parameters",
        "Raw optimum",
        "Robust candidate",
    ]
    assert METRIC_KEYS <= set(body["parameter_sets"][1]["test_metrics"])
    assert set(body["benchmark"]) == {"training_metrics", "test_metrics"}
    assert len(body["summary"]) == 4
    _assert_timeseries(
        body["test_equity"],
        {"Default parameters", "Raw optimum", "Robust candidate", "buy_hold"},
    )
    assert body["test_equity"]["dates"][0] >= "2020-06-01"


def test_validate_walk_forward(client) -> None:
    response = client.post(
        "/api/validate/walk-forward",
        json={
            **MARKET,
            "strategy": "momentum",
            "window_type": "rolling",
            "initial_training_years": 2,
            "test_window_years": 1,
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert len(body["folds"]) == 2
    assert body["folds"][0]["test_start"].startswith("2020-01")
    assert len(body["parameter_history"]) == 2
    assert [row["parameter_set"] for row in body["aggregate"]][-1] == "Buy and Hold"
    _assert_timeseries(body["stitched_equity"], {"Raw optimum", "buy_hold"})


# --------------------------------------------------------------------------
# Pairs
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "params", "beta_column"),
    [
        ("distance", {"entry_zscore": 1.5, "trading_months": 6}, None),
        (
            "cointegration",
            {"maximum_cointegration_pvalue": 0.5, "require_qualification": False},
            "hedge_beta",
        ),
        ("kalman", {"warmup_window": 100, "zscore_window": 40}, "dynamic_beta"),
    ],
)
def test_pairs_research(client, method, params, beta_column) -> None:
    response = client.post(
        "/api/pairs/research",
        json={
            **PAIRS,
            "method": method,
            "ticker_a": "aaa",
            "ticker_b": "BBB",
            "params": params,
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)

    assert body["method"] == method
    assert (body["ticker_a"], body["ticker_b"]) == ("AAA", "BBB")
    assert METRIC_KEYS <= set(body["metrics"]) and METRIC_KEYS <= set(
        body["benchmark_metrics"]
    )
    assert -1 <= body["return_correlation"] <= 1
    required = {
        "normalized_a",
        "normalized_b",
        "spread",
        "spread_zscore",
        "pair_position",
        "strategy_equity",
        "benchmark_equity",
        "strategy_drawdown",
    }
    if beta_column:
        required.add(beta_column)
    _assert_timeseries(body["series"], required)
    assert body["series"]["columns"]["normalized_a"][0] == pytest.approx(1.0)
    if method == "kalman":
        assert "hedge_beta" in body["series"]["columns"]

    assert isinstance(body["trades"], list) and body["diagnostics"]
    assert sum(body["exit_reasons"].values()) == len(body["trades"])
    if body["trades"]:
        pd.Timestamp(body["trades"][0]["entry_date"])


def test_pairs_research_rejects_bad_params(client) -> None:
    unknown = client.post(
        "/api/pairs/research",
        json={
            **PAIRS,
            "method": "distance",
            "ticker_a": "AAA",
            "ticker_b": "BBB",
            "params": {"warmup_window": 10},
        },
    )
    assert unknown.status_code == 422 and "warmup_window" in unknown.json()["detail"]

    not_int = client.post(
        "/api/pairs/research",
        json={
            **PAIRS,
            "method": "distance",
            "ticker_a": "AAA",
            "ticker_b": "BBB",
            "params": {"maximum_holding_days": 2.5},
        },
    )
    assert not_int.status_code == 422

    same = client.post(
        "/api/pairs/research",
        json={**PAIRS, "method": "distance", "ticker_a": "AAA", "ticker_b": "aaa"},
    )
    assert same.status_code == 422


def test_pairs_sensitivity(client) -> None:
    response = client.post(
        "/api/pairs/sensitivity",
        json={
            **PAIRS,
            "start_date": "2019-01-01",
            "method": "kalman",
            "ticker_a": "AAA",
            "ticker_b": "BBB",
            "params": {"warmup_window": 60},
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)
    assert body["rows"][-1]["parameter"] == "FINAL COMBINED SET"
    assert "entry_zscore" in body["recommended_params"]
    assert "ticker_a" not in body["recommended_params"]


@pytest.mark.parametrize("method", ["distance", "cointegration", "kalman"])
def test_pairs_discover(client, method) -> None:
    response = client.post(
        "/api/pairs/discover",
        json={
            **PAIRS,
            "method": method,
            "tickers": ["AAA", "BBB", "CCC", "DDD", "BADX"],
            "formation_years": 2,
            "top_n": 3,
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)
    assert body["selection_start"] == "2017-01-01"
    assert body["selection_end"] == "2019-01-01"
    assert 0 < len(body["rows"]) <= 3
    assert {"asset_a", "asset_b"} <= set(body["rows"][0])
    assert all("BADX" not in (row["asset_a"], row["asset_b"]) for row in body["rows"])


def test_pairs_portfolio(client) -> None:
    response = client.post(
        "/api/pairs/portfolio",
        json={
            **PAIRS,
            "method": "distance",
            "tickers": ["AAA", "BBB", "CCC"],
            "top_n": 2,
            "params": {"entry_zscore": 1.5},
        },
    )
    assert response.status_code == 200, response.text
    body = _strict_json(response)
    assert body["selection_end"] == "2019-01-01"
    assert len(body["discovery"]) == 2
    assert {row["pair"] for row in body["pair_summary"]} <= {
        f"{row['asset_a']}/{row['asset_b']}" for row in body["discovery"]
    }
    assert METRIC_KEYS <= set(body["metrics"])
    _assert_timeseries(body["series"], {"portfolio_equity", "portfolio_drawdown"})
    assert any(name.startswith("equity::") for name in body["series"]["columns"])
    assert body["series"]["dates"][0] >= "2019-01-01"


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "fragment"),
    [
        ({**MARKET, "strategy": "nope"}, "Unknown strategy"),
        ({**MARKET, "strategy": "ema", "end_date": "2017-01-01"}, "end_date"),
        (
            {**MARKET, "strategy": "ema", "transaction_cost_bps": -1},
            "transaction_cost_bps",
        ),
        ({**MARKET, "strategy": "ema", "ticker": "AA PL"}, "ticker"),
        (
            {**MARKET, "strategy": "ema", "parameters": {"fast_window": 2.5}},
            "whole number",
        ),
        (
            {**MARKET, "strategy": "ema", "parameters": {"fast_window": 100000}},
            "between",
        ),
        ({**MARKET, "strategy": "ema", "parameters": {"bogus": 3}}, "bogus"),
        # A research ValueError from the core (fast window must be below slow).
        (
            {
                **MARKET,
                "strategy": "moving_average",
                "parameters": {"fast_window": 100, "slow_window": 50},
            },
            "window",
        ),
    ],
)
def test_bad_input_returns_422_with_string_detail(client, payload, fragment) -> None:
    response = client.post("/api/backtest", json=payload)
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert isinstance(detail, str) and fragment in detail


def test_sample_too_short_is_422(client) -> None:
    response = client.post(
        "/api/optimize",
        json={**MARKET, "start_date": "2021-10-01", "strategy": "moving_average"},
    )
    assert response.status_code == 422
    assert "observations" in response.json()["detail"]


def test_download_failure_is_502(client) -> None:
    response = client.post(
        "/api/backtest", json={**MARKET, "ticker": "BADTICK", "strategy": "ema"}
    )
    assert response.status_code == 502
    assert "No data was returned" in response.json()["detail"]

    pairs = client.post(
        "/api/pairs/research",
        json={**PAIRS, "method": "distance", "ticker_a": "AAA", "ticker_b": "BADB"},
    )
    assert pairs.status_code == 502

    universe = client.post(
        "/api/pairs/discover",
        json={**PAIRS, "method": "distance", "tickers": ["AAA", "BAD1", "BAD2"]},
    )
    assert universe.status_code == 502


def test_unknown_api_path_is_json_404(client) -> None:
    response = client.get("/api/does-not-exist")
    assert response.status_code == 404
    assert "detail" in response.json()


def test_responses_are_finite_json(client) -> None:
    """Spot check: no NaN/inf leaks through a typical response."""
    body = _strict_json(
        client.post("/api/backtest", json={**MARKET, "strategy": "macd"})
    )

    def walk(value):
        if isinstance(value, float):
            assert math.isfinite(value)
        elif isinstance(value, dict):
            for item in value.values():
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    walk(body)
