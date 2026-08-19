import pandas as pd
import pytest

from optimization import (
    OptimizationResults,
    calculate_optimization_robustness,
)


def _make_result(values: list[float]) -> OptimizationResults:
    rows = []
    index = 0
    for fast in [10, 20, 30]:
        for slow in [40, 50, 60]:
            rows.append(
                {
                    "fast_window": fast,
                    "slow_window": slow,
                    "sharpe_ratio": values[index],
                }
            )
            index += 1

    results = pd.DataFrame(rows).sort_values(
        "sharpe_ratio",
        ascending=False,
    ).reset_index(drop=True)

    best = results.iloc[0]

    return OptimizationResults(
        strategy_name="moving_average",
        objective="sharpe_ratio",
        results=results,
        best_parameters={
            "fast_window": int(best["fast_window"]),
            "slow_window": int(best["slow_window"]),
        },
        best_metrics={"sharpe_ratio": float(best["sharpe_ratio"])},
        default_parameters={
            "fast_window": 20,
            "slow_window": 50,
        },
        default_metrics={"sharpe_ratio": 0.80},
    )


def test_robustness_detects_broad_plateau() -> None:
    result = _make_result(
        [
            0.96, 0.97, 0.95,
            0.98, 1.00, 0.97,
            0.95, 0.96, 0.94,
        ]
    )

    diagnostics = calculate_optimization_robustness(result)

    assert diagnostics.robustness_label == "Broad plateau"
    assert diagnostics.local_near_optimal_5_share >= 0.60
    assert diagnostics.near_optimal_10_share >= 0.10


def test_robustness_detects_narrow_peak() -> None:
    result = _make_result(
        [
            0.50, 0.55, 0.52,
            0.58, 1.00, 0.57,
            0.51, 0.54, 0.50,
        ]
    )

    diagnostics = calculate_optimization_robustness(result)

    assert diagnostics.robustness_label == "Narrow peak"
    assert diagnostics.selection_risk_label == "Higher"


def test_robustness_flags_boundary_optimum() -> None:
    result = _make_result(
        [
            1.00, 0.80, 0.75,
            0.70, 0.65, 0.60,
            0.55, 0.50, 0.45,
        ]
    )

    diagnostics = calculate_optimization_robustness(result)

    assert "fast_window" in diagnostics.boundary_parameters
    assert "slow_window" in diagnostics.boundary_parameters


def test_robustness_supports_minimized_volatility() -> None:
    results = pd.DataFrame(
        {
            "window": [10, 20, 30, 40, 50],
            "annualized_volatility": [
                0.20,
                0.18,
                0.15,
                0.16,
                0.19,
            ],
        }
    ).sort_values(
        "annualized_volatility",
        ascending=True,
    ).reset_index(drop=True)

    result = OptimizationResults(
        strategy_name="momentum",
        objective="annualized_volatility",
        results=results,
        best_parameters={"window": 30},
        best_metrics={"annualized_volatility": 0.15},
        default_parameters={"window": 20},
        default_metrics={"annualized_volatility": 0.18},
    )

    diagnostics = calculate_optimization_robustness(result)

    assert diagnostics.near_optimal_10_count == 2
    assert diagnostics.local_neighbor_count == 3
    assert diagnostics.local_median_relative_degradation == pytest.approx(
        (0.01 / 0.15)
    )


def test_robust_candidate_can_prefer_stable_near_optimal_region() -> None:
    rows = []

    for fast in [10, 20, 30, 40, 50]:
        for slow in [60, 70, 80, 90, 100]:
            value = 0.40

            if fast in {30, 40, 50} and slow in {80, 90, 100}:
                value = 0.94

            if fast == 40 and slow == 90:
                value = 0.96

            if fast == 20 and slow == 70:
                value = 1.00

            rows.append(
                {
                    "fast_window": fast,
                    "slow_window": slow,
                    "sharpe_ratio": value,
                }
            )

    results = pd.DataFrame(rows).sort_values(
        "sharpe_ratio",
        ascending=False,
    ).reset_index(drop=True)

    result = OptimizationResults(
        strategy_name="moving_average",
        objective="sharpe_ratio",
        results=results,
        best_parameters={
            "fast_window": 20,
            "slow_window": 70,
        },
        best_metrics={"sharpe_ratio": 1.00},
        default_parameters={
            "fast_window": 20,
            "slow_window": 50,
        },
        default_metrics={"sharpe_ratio": 0.50},
    )

    diagnostics = calculate_optimization_robustness(result)

    assert diagnostics.robust_candidate_parameters == {
        "fast_window": 40,
        "slow_window": 90,
    }
    assert diagnostics.robust_candidate_objective == pytest.approx(0.96)
    assert diagnostics.robust_candidate_relative_gap == pytest.approx(0.04)


def test_robust_candidate_can_be_boundary_when_its_neighborhood_is_best() -> None:
    results = pd.DataFrame(
        {
            "lookback_window": [10, 20, 30, 40, 50],
            "sharpe_ratio": [0.96, 0.94, 0.93, 0.60, 0.50],
        }
    ).sort_values(
        "sharpe_ratio",
        ascending=False,
    ).reset_index(drop=True)

    result = OptimizationResults(
        strategy_name="momentum",
        objective="sharpe_ratio",
        results=results,
        best_parameters={"lookback_window": 10},
        best_metrics={"sharpe_ratio": 0.96},
        default_parameters={"lookback_window": 60},
        default_metrics={"sharpe_ratio": 0.70},
    )

    diagnostics = calculate_optimization_robustness(result)

    assert diagnostics.boundary_parameters == ["lookback_window"]
    assert diagnostics.robust_candidate_parameters == {
        "lookback_window": 10,
    }
    assert diagnostics.robust_candidate_objective == pytest.approx(0.96)