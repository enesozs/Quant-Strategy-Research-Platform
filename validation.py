from dataclasses import dataclass
from typing import Any, Literal

import numpy as np
import pandas as pd

from backtester import run_backtest, run_strategy_on_window
from metrics import calculate_performance_metrics
from optimization import (
    RELATIVE_DEGRADATION_SCALE_FLOOR,
    OptimizationObjective,
    OptimizationResults,
    OptimizationRobustnessDiagnostics,
    calculate_optimization_robustness,
    optimize_strategy,
)
from strategies import get_default_parameters


@dataclass
class ParameterSetValidation:
    """Store in-sample and out-of-sample results for one parameter set."""

    label: str
    parameters: dict[str, Any]
    training_results: pd.DataFrame
    test_results: pd.DataFrame
    training_metrics: dict[str, float]
    test_metrics: dict[str, float]


@dataclass
class ValidationResults:
    """Store a complete single-split out-of-sample validation study."""

    strategy_name: str
    objective: OptimizationObjective
    split_date: pd.Timestamp
    optimization_result: OptimizationResults
    robustness: OptimizationRobustnessDiagnostics
    default: ParameterSetValidation
    optimized: ParameterSetValidation
    robust_candidate: ParameterSetValidation
    benchmark_training_metrics: dict[str, float]
    benchmark_test_metrics: dict[str, float]
    benchmark_test_results: pd.DataFrame
    test_equity_curves: pd.DataFrame


def _calculate_metrics(
    results: pd.DataFrame,
    initial_capital: float,
    risk_free_rate: float,
) -> dict[str, float]:
    """Calculate the standard strategy metrics for a backtest result."""
    metrics = calculate_performance_metrics(
        returns=results["strategy_return"],
        equity=results["strategy_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    metrics["final_value"] = float(
        results["strategy_equity"].iloc[-1]
    )

    metrics["rebalancing_days"] = float(
        (results["trade"].astype(float) > 0).sum()
    )
    metrics["turnover"] = float(
        results["trade"].astype(float).sum()
    )

    return metrics


def _calculate_benchmark_metrics(
    results: pd.DataFrame,
    initial_capital: float,
    risk_free_rate: float,
) -> dict[str, float]:
    """Calculate benchmark metrics from a backtest result."""
    metrics = calculate_performance_metrics(
        returns=results["buy_hold_return"],
        equity=results["buy_hold_equity"],
        risk_free_rate=risk_free_rate,
        initial_value=initial_capital,
    )

    metrics["final_value"] = float(
        results["buy_hold_equity"].iloc[-1]
    )
    metrics["rebalancing_days"] = float(
        (results["buy_hold_turnover"].astype(float) > 0).sum()
    )
    metrics["turnover"] = float(
        results["buy_hold_turnover"].astype(float).sum()
    )

    return metrics


def _evaluate_training_parameters(
    training_data: pd.DataFrame,
    strategy_name: str,
    parameters: dict[str, Any],
    training_evaluation_start: pd.Timestamp,
    initial_capital: float,
    transaction_cost_bps: float,
    cash_rate: float,
    risk_free_rate: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Evaluate one fixed parameter set over the scored part of the training
    sample, using the same warmed-up window as the optimizer.
    """
    results = run_strategy_on_window(
        data=training_data,
        strategy_name=strategy_name,
        evaluation_start=training_evaluation_start,
        strategy_parameters=parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
    )

    metrics = _calculate_metrics(
        results=results,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
    )

    return results, metrics


def _evaluate_test_parameters_with_history(
    full_data: pd.DataFrame,
    strategy_name: str,
    parameters: dict[str, Any],
    split_date: pd.Timestamp,
    initial_capital: float,
    transaction_cost_bps: float,
    cash_rate: float,
    risk_free_rate: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """
    Evaluate one frozen parameter set on the test sample.

    Signals and indicators are calculated on the complete historical data so
    the first out-of-sample observation can use information available before
    the split. The actual backtest is then restarted from zero exposure one
    trading day before the test sample, so test-period capital starts from the
    selected initial capital and pays the appropriate initial entry cost.
    """
    test_results = run_strategy_on_window(
        data=full_data,
        strategy_name=strategy_name,
        evaluation_start=split_date,
        strategy_parameters=parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
    )

    metrics = _calculate_metrics(
        results=test_results,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
    )

    return test_results, metrics


def _evaluate_parameter_set(
    full_data: pd.DataFrame,
    training_data: pd.DataFrame,
    strategy_name: str,
    label: str,
    parameters: dict[str, Any],
    split_date: pd.Timestamp,
    training_evaluation_start: pd.Timestamp,
    initial_capital: float,
    transaction_cost_bps: float,
    cash_rate: float,
    risk_free_rate: float,
) -> ParameterSetValidation:
    """Evaluate the same frozen parameter set in training and test samples."""
    training_results, training_metrics = (
        _evaluate_training_parameters(
            training_data=training_data,
            strategy_name=strategy_name,
            parameters=parameters,
            training_evaluation_start=training_evaluation_start,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps,
            cash_rate=cash_rate,
            risk_free_rate=risk_free_rate,
        )
    )

    test_results, test_metrics = (
        _evaluate_test_parameters_with_history(
            full_data=full_data,
            strategy_name=strategy_name,
            parameters=parameters,
            split_date=split_date,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps,
            cash_rate=cash_rate,
            risk_free_rate=risk_free_rate,
        )
    )

    return ParameterSetValidation(
        label=label,
        parameters=dict(parameters),
        training_results=training_results,
        test_results=test_results,
        training_metrics=training_metrics,
        test_metrics=test_metrics,
    )


def _build_test_equity_curves(
    default: ParameterSetValidation,
    optimized: ParameterSetValidation,
    robust_candidate: ParameterSetValidation,
    benchmark_test_results: pd.DataFrame,
) -> pd.DataFrame:
    """Combine test-period equity curves for plotting."""
    curves = pd.DataFrame(
        index=optimized.test_results.index
    )

    curves["Default parameters"] = default.test_results[
        "strategy_equity"
    ]
    curves["Raw optimum"] = optimized.test_results[
        "strategy_equity"
    ]
    curves["Robust candidate"] = robust_candidate.test_results[
        "strategy_equity"
    ]
    curves["Buy and Hold"] = benchmark_test_results[
        "buy_hold_equity"
    ]

    return curves


def calculate_out_of_sample_degradation(
    training_value: float,
    test_value: float,
    objective: OptimizationObjective,
) -> tuple[float, float]:
    """
    Measure how much the selected objective deteriorates out of sample.

    Positive values represent deterioration. Negative values mean the test
    sample improved relative to the training sample.

    The relative value is scaled by the training magnitude with the same
    per-objective floor as the optimizer's robustness diagnostics, so a
    training Sharpe near zero cannot turn a small change into a
    thousands-of-percent "degradation".
    """
    if objective == "annualized_volatility":
        absolute_degradation = test_value - training_value
    else:
        absolute_degradation = training_value - test_value

    scale = max(
        abs(training_value),
        RELATIVE_DEGRADATION_SCALE_FLOOR.get(objective, 0.0),
    )

    if not np.isfinite(scale) or scale == 0:
        relative_degradation = np.nan
    else:
        relative_degradation = absolute_degradation / scale

    return (
        float(absolute_degradation),
        float(relative_degradation),
    )


def build_validation_summary(
    validation: ValidationResults,
) -> pd.DataFrame:
    """Create a compact train-versus-test comparison table."""
    rows: list[dict[str, Any]] = []

    for parameter_set in (
        validation.default,
        validation.optimized,
        validation.robust_candidate,
    ):
        train_objective = float(
            parameter_set.training_metrics[validation.objective]
        )
        test_objective = float(
            parameter_set.test_metrics[validation.objective]
        )
        absolute_degradation, relative_degradation = (
            calculate_out_of_sample_degradation(
                training_value=train_objective,
                test_value=test_objective,
                objective=validation.objective,
            )
        )

        rows.append(
            {
                "parameter_set": parameter_set.label,
                "training_objective": train_objective,
                "test_objective": test_objective,
                "absolute_oos_degradation": absolute_degradation,
                "relative_oos_degradation": relative_degradation,
                "test_final_value": parameter_set.test_metrics[
                    "final_value"
                ],
                "test_total_return": parameter_set.test_metrics[
                    "total_return"
                ],
                "test_cagr": parameter_set.test_metrics["cagr"],
                "test_annualized_volatility": (
                    parameter_set.test_metrics[
                        "annualized_volatility"
                    ]
                ),
                "test_sharpe_ratio": parameter_set.test_metrics[
                    "sharpe_ratio"
                ],
                "test_max_drawdown": parameter_set.test_metrics[
                    "max_drawdown"
                ],
                "test_calmar_ratio": parameter_set.test_metrics[
                    "calmar_ratio"
                ],
                "test_rebalancing_days": parameter_set.test_metrics[
                    "rebalancing_days"
                ],
                "test_turnover": parameter_set.test_metrics[
                    "turnover"
                ],
            }
        )

    benchmark_train_objective = float(
        validation.benchmark_training_metrics[validation.objective]
    )
    benchmark_test_objective = float(
        validation.benchmark_test_metrics[validation.objective]
    )
    benchmark_absolute_degradation, benchmark_relative_degradation = (
        calculate_out_of_sample_degradation(
            training_value=benchmark_train_objective,
            test_value=benchmark_test_objective,
            objective=validation.objective,
        )
    )

    rows.append(
        {
            "parameter_set": "Buy and Hold",
            "training_objective": benchmark_train_objective,
            "test_objective": benchmark_test_objective,
            "absolute_oos_degradation": benchmark_absolute_degradation,
            "relative_oos_degradation": benchmark_relative_degradation,
            "test_final_value": validation.benchmark_test_metrics[
                "final_value"
            ],
            "test_total_return": validation.benchmark_test_metrics[
                "total_return"
            ],
            "test_cagr": validation.benchmark_test_metrics["cagr"],
            "test_annualized_volatility": (
                validation.benchmark_test_metrics[
                    "annualized_volatility"
                ]
            ),
            "test_sharpe_ratio": validation.benchmark_test_metrics[
                "sharpe_ratio"
            ],
            "test_max_drawdown": validation.benchmark_test_metrics[
                "max_drawdown"
            ],
            "test_calmar_ratio": validation.benchmark_test_metrics[
                "calmar_ratio"
            ],
            "test_rebalancing_days": validation.benchmark_test_metrics[
                "rebalancing_days"
            ],
            "test_turnover": validation.benchmark_test_metrics[
                "turnover"
            ],
        }
    )

    return pd.DataFrame(rows)


def validate_strategy_out_of_sample(
    data: pd.DataFrame,
    strategy_name: str,
    split_date: str | pd.Timestamp,
    parameter_grid: dict[str, list[Any]] | None = None,
    objective: OptimizationObjective = "sharpe_ratio",
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
    risk_free_rate: float = 0.0,
) -> ValidationResults:
    """
    Optimize on the training sample and evaluate frozen parameters on test data.

    The split is strict: observations before split_date form the training
    sample, while observations on or after split_date form the out-of-sample
    test. No test-period performance is used to select the optimized or robust
    parameter sets.
    """
    if data.empty:
        raise ValueError("Market data cannot be empty.")

    if not data.index.is_monotonic_increasing:
        data = data.sort_index()

    split_timestamp = pd.Timestamp(split_date)

    training_data = data.loc[
        data.index < split_timestamp
    ].copy()
    test_data = data.loc[
        data.index >= split_timestamp
    ].copy()

    if training_data.empty:
        raise ValueError(
            "The validation split leaves no observations in the training "
            "sample."
        )

    if test_data.empty:
        raise ValueError(
            "The validation split leaves no observations in the test sample."
        )

    if len(training_data) < 2:
        raise ValueError(
            "The training sample must contain at least two observations."
        )

    optimization_result = optimize_strategy(
        data=training_data,
        strategy_name=strategy_name,
        parameter_grid=parameter_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
    )

    robustness = calculate_optimization_robustness(
        optimization_result
    )

    default_parameters = get_default_parameters(strategy_name)
    optimized_parameters = optimization_result.best_parameters
    robust_parameters = robustness.robust_candidate_parameters

    default_validation = _evaluate_parameter_set(
        full_data=data,
        training_data=training_data,
        strategy_name=strategy_name,
        label="Default parameters",
        parameters=default_parameters,
        split_date=split_timestamp,
        training_evaluation_start=optimization_result.evaluation_start,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
    )

    optimized_validation = _evaluate_parameter_set(
        full_data=data,
        training_data=training_data,
        strategy_name=strategy_name,
        label="Raw optimum",
        parameters=optimized_parameters,
        split_date=split_timestamp,
        training_evaluation_start=optimization_result.evaluation_start,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
    )

    robust_validation = _evaluate_parameter_set(
        full_data=data,
        training_data=training_data,
        strategy_name=strategy_name,
        label="Robust candidate",
        parameters=robust_parameters,
        split_date=split_timestamp,
        training_evaluation_start=optimization_result.evaluation_start,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
        risk_free_rate=risk_free_rate,
    )

    benchmark_training_metrics = _calculate_benchmark_metrics(
        results=default_validation.training_results,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
    )

    benchmark_test_data = test_data.copy()
    benchmark_test_data["signal"] = 0.0
    benchmark_test_results = run_backtest(
        data=benchmark_test_data,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        cash_rate=cash_rate,
    )
    benchmark_test_metrics = _calculate_benchmark_metrics(
        results=benchmark_test_results,
        initial_capital=initial_capital,
        risk_free_rate=risk_free_rate,
    )

    test_equity_curves = _build_test_equity_curves(
        default=default_validation,
        optimized=optimized_validation,
        robust_candidate=robust_validation,
        benchmark_test_results=benchmark_test_results,
    )

    return ValidationResults(
        strategy_name=strategy_name,
        objective=objective,
        split_date=split_timestamp,
        optimization_result=optimization_result,
        robustness=robustness,
        default=default_validation,
        optimized=optimized_validation,
        robust_candidate=robust_validation,
        benchmark_training_metrics=benchmark_training_metrics,
        benchmark_test_metrics=benchmark_test_metrics,
        benchmark_test_results=benchmark_test_results,
        test_equity_curves=test_equity_curves,
    )


WalkForwardWindowType = Literal["expanding", "rolling"]


@dataclass
class WalkForwardFold:
    """Store one walk-forward validation fold."""

    fold: int
    training_start: pd.Timestamp
    training_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp
    validation: ValidationResults


@dataclass
class WalkForwardResults:
    """Store a complete walk-forward validation study."""

    strategy_name: str
    objective: OptimizationObjective
    training_window_type: WalkForwardWindowType
    initial_training_years: int
    test_window_years: int
    folds: list[WalkForwardFold]
    fold_summary: pd.DataFrame
    parameter_history: pd.DataFrame
    stitched_equity_curves: pd.DataFrame
    aggregate_summary: pd.DataFrame


def _objective_is_better(
    candidate: float,
    reference: float,
    objective: OptimizationObjective,
) -> bool:
    """Return whether candidate is better than reference for the objective."""
    if np.isnan(candidate) or np.isnan(reference):
        return False

    if objective == "annualized_volatility":
        return candidate < reference

    return candidate > reference


def _build_walk_forward_fold_summary(
    folds: list[WalkForwardFold],
    objective: OptimizationObjective,
) -> pd.DataFrame:
    """Create one row per walk-forward test fold."""
    rows: list[dict[str, Any]] = []

    for fold in folds:
        validation = fold.validation

        default_train = float(
            validation.default.training_metrics[objective]
        )
        default_test = float(
            validation.default.test_metrics[objective]
        )
        raw_train = float(
            validation.optimized.training_metrics[objective]
        )
        raw_test = float(
            validation.optimized.test_metrics[objective]
        )
        robust_train = float(
            validation.robust_candidate.training_metrics[objective]
        )
        robust_test = float(
            validation.robust_candidate.test_metrics[objective]
        )
        benchmark_test = float(
            validation.benchmark_test_metrics[objective]
        )

        raw_abs, raw_rel = calculate_out_of_sample_degradation(
            training_value=raw_train,
            test_value=raw_test,
            objective=objective,
        )
        robust_abs, robust_rel = calculate_out_of_sample_degradation(
            training_value=robust_train,
            test_value=robust_test,
            objective=objective,
        )

        rows.append(
            {
                "fold": fold.fold,
                "training_start": fold.training_start,
                "training_end": fold.training_end,
                "test_start": fold.test_start,
                "test_end": fold.test_end,
                "training_robustness": (
                    validation.robustness.robustness_label
                ),
                "default_training_objective": default_train,
                "default_test_objective": default_test,
                "raw_training_objective": raw_train,
                "raw_test_objective": raw_test,
                "robust_training_objective": robust_train,
                "robust_test_objective": robust_test,
                "benchmark_test_objective": benchmark_test,
                "raw_absolute_oos_degradation": raw_abs,
                "raw_relative_oos_degradation": raw_rel,
                "robust_absolute_oos_degradation": robust_abs,
                "robust_relative_oos_degradation": robust_rel,
                "raw_beats_default": _objective_is_better(
                    raw_test,
                    default_test,
                    objective,
                ),
                "robust_beats_default": _objective_is_better(
                    robust_test,
                    default_test,
                    objective,
                ),
                "robust_beats_raw": _objective_is_better(
                    robust_test,
                    raw_test,
                    objective,
                ),
            }
        )

    return pd.DataFrame(rows)


def _build_walk_forward_parameter_history(
    folds: list[WalkForwardFold],
) -> pd.DataFrame:
    """Record the raw and stability-oriented parameters chosen in each fold."""
    rows: list[dict[str, Any]] = []

    for fold in folds:
        validation = fold.validation
        row: dict[str, Any] = {
            "fold": fold.fold,
            "training_end": fold.training_end,
            "test_start": fold.test_start,
            "test_end": fold.test_end,
            "training_robustness": validation.robustness.robustness_label,
        }

        for name, value in validation.optimized.parameters.items():
            row[f"raw_{name}"] = value

        for name, value in validation.robust_candidate.parameters.items():
            row[f"robust_{name}"] = value

        rows.append(row)

    return pd.DataFrame(rows)


def _compound_stitched_returns(
    returns: pd.Series,
    initial_capital: float,
) -> pd.Series:
    """Compound a chronologically ordered return series from initial capital."""
    clean_returns = (
        returns.astype(float)
        .sort_index()
        .loc[lambda series: ~series.index.duplicated(keep="first")]
        .fillna(0.0)
    )

    return initial_capital * (1.0 + clean_returns).cumprod()


def _build_continuous_stitched_strategy_returns(
    fold_results: list[pd.DataFrame],
    transaction_cost_bps: float,
) -> pd.Series:
    """
    Join fold-level strategy returns into one continuous executable series.

    Each fold-level validation backtest intentionally starts from zero exposure
    so its isolated test metrics are rebased and comparable. For the stitched
    walk-forward portfolio, however, exposure carries across fold boundaries.
    The first return of each fold therefore replaces the isolated zero-to-new
    position cost with the actual one-way transition cost from the preceding
    fold's final position to the new fold's first realized position.
    """
    if not fold_results:
        return pd.Series(dtype=float)

    transaction_cost_rate = transaction_cost_bps / 10_000
    adjusted_returns: list[pd.Series] = []
    previous_position = 0.0

    for results in fold_results:
        if results.empty:
            continue

        required_columns = {
            "strategy_return",
            "gross_strategy_return",
            "position",
        }
        missing_columns = required_columns - set(results.columns)

        if missing_columns:
            raise ValueError(
                "Walk-forward fold results are missing required columns: "
                f"{sorted(missing_columns)}"
            )

        fold_returns = results["strategy_return"].astype(float).copy()
        first_index = fold_returns.index[0]
        first_position = float(results["position"].iloc[0])
        first_gross_return = float(
            results["gross_strategy_return"].iloc[0]
        )

        transition_turnover = abs(
            first_position - previous_position
        )
        fold_returns.loc[first_index] = (
            first_gross_return
            - transition_turnover * transaction_cost_rate
        )

        adjusted_returns.append(fold_returns)
        previous_position = float(results["position"].iloc[-1])

    if not adjusted_returns:
        return pd.Series(dtype=float)

    return pd.concat(adjusted_returns)


def _build_walk_forward_stitched_equity(
    folds: list[WalkForwardFold],
    initial_capital: float,
    transaction_cost_bps: float,
) -> pd.DataFrame:
    """Compound only out-of-sample fold returns into continuous equity curves."""
    default_returns = _build_continuous_stitched_strategy_returns(
        [fold.validation.default.test_results for fold in folds],
        transaction_cost_bps=transaction_cost_bps,
    )
    raw_returns = _build_continuous_stitched_strategy_returns(
        [fold.validation.optimized.test_results for fold in folds],
        transaction_cost_bps=transaction_cost_bps,
    )
    robust_returns = _build_continuous_stitched_strategy_returns(
        [fold.validation.robust_candidate.test_results for fold in folds],
        transaction_cost_bps=transaction_cost_bps,
    )

    benchmark_asset_returns = pd.concat(
        [
            fold.validation.benchmark_test_results["asset_return"]
            for fold in folds
        ]
    ).astype(float)
    benchmark_asset_returns = benchmark_asset_returns.sort_index()
    benchmark_asset_returns = benchmark_asset_returns.loc[
        ~benchmark_asset_returns.index.duplicated(keep="first")
    ].fillna(0.0)

    if not benchmark_asset_returns.empty:
        benchmark_asset_returns = benchmark_asset_returns.copy()
        first_index = benchmark_asset_returns.index[0]
        benchmark_asset_returns.loc[first_index] -= (
            transaction_cost_bps / 10_000
        )

    curves = pd.DataFrame(
        {
            "Default parameters": _compound_stitched_returns(
                default_returns,
                initial_capital,
            ),
            "Raw optimum": _compound_stitched_returns(
                raw_returns,
                initial_capital,
            ),
            "Robust candidate": _compound_stitched_returns(
                robust_returns,
                initial_capital,
            ),
            "Buy and Hold": _compound_stitched_returns(
                benchmark_asset_returns,
                initial_capital,
            ),
        }
    )

    return curves.sort_index()


def _build_walk_forward_aggregate_summary(
    folds: list[WalkForwardFold],
    fold_summary: pd.DataFrame,
    stitched_equity_curves: pd.DataFrame,
    objective: OptimizationObjective,
    initial_capital: float,
) -> pd.DataFrame:
    """Summarize repeated out-of-sample performance across all folds."""
    rows: list[dict[str, Any]] = []

    parameter_sets = {
        "Default parameters": "default_test_objective",
        "Raw optimum": "raw_test_objective",
        "Robust candidate": "robust_test_objective",
        "Buy and Hold": "benchmark_test_objective",
    }

    for label, column in parameter_sets.items():
        values = fold_summary[column].astype(float)
        equity = stitched_equity_curves[label].dropna()

        if equity.empty:
            stitched_total_return = np.nan
            stitched_cagr = np.nan
            stitched_max_drawdown = np.nan
        else:
            stitched_total_return = float(
                equity.iloc[-1] / initial_capital - 1
            )
            number_of_days = (equity.index[-1] - equity.index[0]).days
            if number_of_days > 0:
                years = number_of_days / 365.25
                stitched_cagr = float(
                    (equity.iloc[-1] / initial_capital) ** (1 / years) - 1
                )
            else:
                stitched_cagr = np.nan

            stitched_peak = equity.cummax().clip(lower=initial_capital)
            stitched_max_drawdown = float(
                (equity / stitched_peak - 1).min()
            )

        if label == "Raw optimum":
            beats_default_share = float(
                fold_summary["raw_beats_default"].mean()
            )
        elif label == "Robust candidate":
            beats_default_share = float(
                fold_summary["robust_beats_default"].mean()
            )
        elif label == "Default parameters":
            beats_default_share = np.nan
        else:
            default_values = fold_summary[
                "default_test_objective"
            ].astype(float)
            comparisons = [
                _objective_is_better(candidate, reference, objective)
                for candidate, reference in zip(values, default_values)
            ]
            beats_default_share = float(np.mean(comparisons))

        rows.append(
            {
                "parameter_set": label,
                "folds": len(folds),
                "median_test_objective": float(values.median()),
                "mean_test_objective": float(values.mean()),
                "worst_test_objective": (
                    float(values.max())
                    if objective == "annualized_volatility"
                    else float(values.min())
                ),
                "best_test_objective": (
                    float(values.min())
                    if objective == "annualized_volatility"
                    else float(values.max())
                ),
                "beats_default_share": beats_default_share,
                "stitched_final_value": (
                    float(equity.iloc[-1]) if not equity.empty else np.nan
                ),
                "stitched_total_return": stitched_total_return,
                "stitched_cagr": stitched_cagr,
                "stitched_max_drawdown": stitched_max_drawdown,
            }
        )

    return pd.DataFrame(rows)


def validate_strategy_walk_forward(
    data: pd.DataFrame,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]] | None = None,
    objective: OptimizationObjective = "sharpe_ratio",
    training_window_type: WalkForwardWindowType = "expanding",
    initial_training_years: int = 2,
    test_window_years: int = 1,
    initial_capital: float = 10_000,
    transaction_cost_bps: float = 10,
    cash_rate: float = 0.0,
    risk_free_rate: float = 0.0,
) -> WalkForwardResults:
    """
    Run expanding- or rolling-window walk-forward validation.

    Each fold optimizes only on observations before that fold's test start.
    The selected raw and stability-oriented parameters are then frozen and
    evaluated on the immediately following unseen test window. Expanding mode
    keeps the original training start and adds new history each fold. Rolling
    mode keeps a fixed-length training window and advances its start through
    time. Test windows remain non-overlapping in both modes.
    """
    if data.empty:
        raise ValueError("Market data cannot be empty.")

    if training_window_type not in {"expanding", "rolling"}:
        raise ValueError(
            "Training-window type must be either 'expanding' or 'rolling'."
        )

    if initial_training_years < 1:
        raise ValueError("Initial training years must be at least 1.")

    if test_window_years < 1:
        raise ValueError("Test-window years must be at least 1.")

    if not data.index.is_monotonic_increasing:
        data = data.sort_index()

    start_timestamp = pd.Timestamp(data.index[0]).normalize()
    last_timestamp = pd.Timestamp(data.index[-1]).normalize()
    first_test_start = start_timestamp + pd.DateOffset(
        years=initial_training_years
    )

    if first_test_start > last_timestamp:
        raise ValueError(
            "The selected sample is too short for the requested initial "
            "training period."
        )

    folds: list[WalkForwardFold] = []
    fold_number = 1
    test_start = first_test_start

    while test_start <= last_timestamp:
        nominal_test_end = test_start + pd.DateOffset(
            years=test_window_years
        )

        # A fold is included only when the requested test window is effectively
        # represented by the downloaded sample. The market-data download ends
        # on the final available trading day before the requested exclusive
        # boundary, so weekends and exchange holidays can leave the last
        # observation a few calendar days before nominal_test_end. A small
        # tolerance keeps a complete trading-year fold (for example, 2025)
        # without accepting a genuinely truncated final test period.
        completion_tolerance = pd.Timedelta(days=7)
        if nominal_test_end > last_timestamp + completion_tolerance:
            break

        if training_window_type == "rolling":
            fold_training_start = test_start - pd.DateOffset(
                years=initial_training_years
            )
        else:
            fold_training_start = start_timestamp

        fold_data = data.loc[
            (data.index >= fold_training_start)
            & (data.index < nominal_test_end)
        ].copy()
        training_data = fold_data.loc[
            fold_data.index < test_start
        ]
        test_data = fold_data.loc[
            fold_data.index >= test_start
        ]

        if training_data.empty or test_data.empty:
            break

        validation = validate_strategy_out_of_sample(
            data=fold_data,
            strategy_name=strategy_name,
            split_date=test_start,
            parameter_grid=parameter_grid,
            objective=objective,
            initial_capital=initial_capital,
            transaction_cost_bps=transaction_cost_bps,
            cash_rate=cash_rate,
            risk_free_rate=risk_free_rate,
        )

        folds.append(
            WalkForwardFold(
                fold=fold_number,
                training_start=pd.Timestamp(training_data.index[0]),
                training_end=pd.Timestamp(training_data.index[-1]),
                test_start=pd.Timestamp(test_data.index[0]),
                test_end=pd.Timestamp(test_data.index[-1]),
                validation=validation,
            )
        )

        fold_number += 1
        test_start = nominal_test_end

    if not folds:
        raise ValueError(
            "No complete walk-forward test folds could be created. Increase "
            "the total sample length or reduce the initial training/test "
            "window lengths."
        )

    fold_summary = _build_walk_forward_fold_summary(
        folds=folds,
        objective=objective,
    )
    parameter_history = _build_walk_forward_parameter_history(folds)
    stitched_equity_curves = _build_walk_forward_stitched_equity(
        folds=folds,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )
    aggregate_summary = _build_walk_forward_aggregate_summary(
        folds=folds,
        fold_summary=fold_summary,
        stitched_equity_curves=stitched_equity_curves,
        objective=objective,
        initial_capital=initial_capital,
    )

    return WalkForwardResults(
        strategy_name=strategy_name,
        objective=objective,
        training_window_type=training_window_type,
        initial_training_years=initial_training_years,
        test_window_years=test_window_years,
        folds=folds,
        fold_summary=fold_summary,
        parameter_history=parameter_history,
        stitched_equity_curves=stitched_equity_curves,
        aggregate_summary=aggregate_summary,
    )