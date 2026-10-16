from datetime import date
from functools import reduce
from operator import mul
from typing import Any, cast

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from backtester import prepare_market_data
from optimization import OptimizationObjective
from strategies import (
    STRATEGY_METADATA,
    get_optimization_grid,
)
from validation import (
    ValidationResults,
    WalkForwardResults,
    WalkForwardWindowType,
    build_validation_summary,
    validate_strategy_out_of_sample,
    validate_strategy_walk_forward,
)


OBJECTIVE_OPTIONS: dict[str, OptimizationObjective] = {
    "Sharpe Ratio": "sharpe_ratio",
    "Total Return": "total_return",
    "CAGR": "cagr",
    "Annualized Volatility": "annualized_volatility",
    "Maximum Drawdown": "max_drawdown",
}

STRATEGY_OPTIONS: dict[str, str] = {
    metadata["display_name"]: strategy_name
    for strategy_name, metadata in STRATEGY_METADATA.items()
}


@st.cache_data
def run_cached_validation(
    ticker: str,
    start_date: str,
    split_date: str,
    end_date: str,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
    objective: OptimizationObjective,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
) -> ValidationResults:
    """Download one sample and cache a single-split validation study."""
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return validate_strategy_out_of_sample(
        data=market_data,
        strategy_name=strategy_name,
        split_date=split_date,
        parameter_grid=parameter_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
    )


def _count_grid_combinations(
    parameter_grid: dict[str, list[Any]],
) -> int:
    """Return the raw Cartesian-product size of a grid."""
    lengths = [len(values) for values in parameter_grid.values()]

    if not lengths:
        return 0

    return reduce(mul, lengths, 1)


def _format_parameter_value(
    strategy_name: str,
    parameter_name: str,
    value: Any,
) -> str:
    """Format a parameter value from strategy metadata."""
    specification = STRATEGY_METADATA[
        strategy_name
    ]["parameters"][parameter_name]

    if specification.get("format") == "percent":
        return f"{float(value):.2%}"

    if specification["type"] == "int":
        return str(int(value))

    return f"{float(value):g}"


def _format_parameter_set(
    strategy_name: str,
    parameters: dict[str, Any],
) -> str:
    """Create a compact readable parameter-set description."""
    specifications = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    parts: list[str] = []

    for parameter_name, value in parameters.items():
        label = specifications[parameter_name]["label"]
        formatted = _format_parameter_value(
            strategy_name=strategy_name,
            parameter_name=parameter_name,
            value=value,
        )
        parts.append(f"{label}: {formatted}")

    return " | ".join(parts)


def _format_objective_value(
    objective: OptimizationObjective,
    value: float,
) -> str:
    """Format one objective value for display."""
    if objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }:
        return f"{value:.2%}"

    return f"{value:.3f}"


def _format_degradation(
    objective: OptimizationObjective,
    absolute_value: float,
    relative_value: float,
) -> str:
    """Format an out-of-sample degradation measure."""
    if objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }:
        absolute_text = f"{absolute_value:+.2%}"
    else:
        absolute_text = f"{absolute_value:+.3f}"

    if np.isnan(relative_value):
        return f"{absolute_text} (relative: N/A)"

    return f"{absolute_text} ({relative_value:+.1%} relative)"


def _render_parameter_sets(
    validation: ValidationResults,
) -> None:
    """Show the three parameter configurations evaluated in validation."""
    st.subheader("Frozen parameter sets")

    default_column, optimized_column, robust_column = st.columns(3)

    with default_column:
        st.markdown("**Default parameters**")
        st.write(
            _format_parameter_set(
                validation.strategy_name,
                validation.default.parameters,
            )
        )

    with optimized_column:
        st.markdown("**Raw training optimum**")
        st.write(
            _format_parameter_set(
                validation.strategy_name,
                validation.optimized.parameters,
            )
        )

    with robust_column:
        st.markdown("**Stability-oriented candidate**")
        st.write(
            _format_parameter_set(
                validation.strategy_name,
                validation.robust_candidate.parameters,
            )
        )

    st.caption(
        "The raw optimum and stability-oriented candidate are selected using "
        "training data only. Their parameters are frozen before any test-period "
        "performance is measured."
    )


def _render_objective_diagnostics(
    validation: ValidationResults,
) -> None:
    """Compare training and test objective behavior."""
    st.subheader("In-sample to out-of-sample behavior")

    summary = build_validation_summary(validation)

    raw_row = summary.loc[
        summary["parameter_set"] == "Raw optimum"
    ].iloc[0]
    robust_row = summary.loc[
        summary["parameter_set"] == "Robust candidate"
    ].iloc[0]

    metric_columns = st.columns(4)

    metric_columns[0].metric(
        "Training optimum",
        _format_objective_value(
            validation.objective,
            float(raw_row["training_objective"]),
        ),
    )
    metric_columns[1].metric(
        "Raw optimum — test",
        _format_objective_value(
            validation.objective,
            float(raw_row["test_objective"]),
        ),
    )
    metric_columns[2].metric(
        "Robust candidate — test",
        _format_objective_value(
            validation.objective,
            float(robust_row["test_objective"]),
        ),
    )
    metric_columns[3].metric(
        "Training robustness",
        validation.robustness.robustness_label,
    )

    st.caption(
        "Positive degradation means the selected optimization objective became "
        "worse out of sample. A negative value means it improved on the test "
        "sample."
    )

    degradation_columns = st.columns(2)

    degradation_columns[0].metric(
        "Raw optimum OOS degradation",
        _format_degradation(
            validation.objective,
            float(raw_row["absolute_oos_degradation"]),
            float(raw_row["relative_oos_degradation"]),
        ),
    )
    degradation_columns[1].metric(
        "Robust candidate OOS degradation",
        _format_degradation(
            validation.objective,
            float(robust_row["absolute_oos_degradation"]),
            float(robust_row["relative_oos_degradation"]),
        ),
    )

    if (
        validation.robust_candidate.parameters
        == validation.optimized.parameters
    ):
        st.success(
            "The mathematical training optimum is also the stability-oriented "
            "candidate in the tested training grid."
        )
    else:
        raw_test = float(raw_row["test_objective"])
        robust_test = float(robust_row["test_objective"])

        if validation.objective == "annualized_volatility":
            robust_test_is_better = robust_test < raw_test
        else:
            robust_test_is_better = robust_test > raw_test

        if robust_test_is_better:
            st.info(
                "The stability-oriented candidate outperformed the raw training "
                "optimum on the selected out-of-sample objective. This is useful "
                "evidence for this split, but it is still only one test period."
            )
        else:
            st.info(
                "The raw training optimum outperformed the stability-oriented "
                "candidate on this test split. Robustness selection is not "
                "guaranteed to improve every unseen period."
            )


def _render_validation_table(
    validation: ValidationResults,
) -> None:
    """Render the detailed train/test comparison table."""
    st.subheader("Validation comparison")

    summary = build_validation_summary(validation).copy()

    summary = summary.rename(
        columns={
            "parameter_set": "Parameter Set",
            "training_objective": "Training Objective",
            "test_objective": "Test Objective",
            "absolute_oos_degradation": "Absolute OOS Degradation",
            "relative_oos_degradation": "Relative OOS Degradation",
            "test_final_value": "Test Final Value",
            "test_total_return": "Test Total Return",
            "test_cagr": "Test CAGR",
            "test_annualized_volatility": "Test Volatility",
            "test_sharpe_ratio": "Test Sharpe Ratio",
            "test_max_drawdown": "Test Maximum Drawdown",
            "test_rebalancing_days": "Test Rebalancing Days",
            "test_turnover": "Test One-Way Turnover",
        }
    )

    objective_percent = validation.objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }

    objective_format = "{:.2%}" if objective_percent else "{:.3f}"
    degradation_format = (
        "{:+.2%}" if objective_percent else "{:+.3f}"
    )

    st.dataframe(
        summary.style.format(
            {
                "Training Objective": objective_format,
                "Test Objective": objective_format,
                "Absolute OOS Degradation": degradation_format,
                "Relative OOS Degradation": "{:+.1%}",
                "Test Final Value": "${:,.2f}",
                "Test Total Return": "{:.2%}",
                "Test CAGR": "{:.2%}",
                "Test Volatility": "{:.2%}",
                "Test Sharpe Ratio": "{:.2f}",
                "Test Maximum Drawdown": "{:.2%}",
                "Test Rebalancing Days": "{:.0f}",
                "Test One-Way Turnover": "{:.2f}×",
            }
        ),
        width="stretch",
        hide_index=True,
    )


def _render_test_equity_chart(
    validation: ValidationResults,
) -> None:
    """Plot all test-period equity curves on the same axes."""
    st.subheader("Out-of-sample equity curves")

    chart_data = (
        validation.test_equity_curves
        .rename_axis("Date")
        .reset_index()
        .melt(
            id_vars="Date",
            var_name="Parameter set",
            value_name="Portfolio value",
        )
    )

    figure = px.line(
        chart_data,
        x="Date",
        y="Portfolio value",
        color="Parameter set",
        title="Test-Period Portfolio Value",
    )

    figure.update_layout(
        hovermode="x unified",
        yaxis_title="Portfolio value",
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


def render_validation_page() -> None:
    """Render the single-split out-of-sample validation lab."""
    st.title("Validation Lab")

    st.write(
        "Optimize a strategy on an earlier training sample, freeze the selected "
        "parameters, and evaluate them on later observations that were not used "
        "for parameter selection."
    )

    with st.sidebar:
        validation_method = st.radio(
            "Validation method",
            options=[
                "Single Split",
                "Walk-Forward",
            ],
            key="validation_method",
            help=(
                "Single Split performs one train/test experiment. Walk-Forward "
                "repeats the experiment through time using either an expanding "
                "or fixed-length rolling training window and non-overlapping "
                "unseen test windows."
            ),
        )

    if validation_method == "Walk-Forward":
        _render_walk_forward_validation_page()
        return

    with st.sidebar:
        st.header("Validation settings")

        selected_strategy = st.selectbox(
            "Strategy",
            options=list(STRATEGY_OPTIONS),
            key="validation_strategy",
        )
        strategy_name = STRATEGY_OPTIONS[selected_strategy]

        ticker = (
            st.text_input(
                "Ticker",
                value="AAPL",
                key="validation_ticker",
            )
            .upper()
            .strip()
        )

        start_date = st.date_input(
            "Training start date",
            value=date(2020, 1, 1),
            key="validation_start_date",
        )

        split_date = st.date_input(
            "Out-of-sample start date",
            value=date(2024, 1, 1),
            key="validation_split_date",
            help=(
                "Observations before this date are used for optimization. "
                "Observations on or after this date are reserved for the "
                "out-of-sample test."
            ),
        )

        end_date = st.date_input(
            "Test end date",
            value=date(2026, 1, 1),
            key="validation_end_date",
        )

        selected_objective = st.selectbox(
            "Optimization objective",
            options=list(OBJECTIVE_OPTIONS),
            key="validation_objective",
        )
        objective = OBJECTIVE_OPTIONS[selected_objective]

        initial_capital = st.number_input(
            "Initial capital",
            min_value=1.0,
            value=10_000.0,
            step=1_000.0,
            key="validation_initial_capital",
        )

        transaction_cost_bps = st.number_input(
            "One-way transaction cost (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="validation_transaction_cost_bps",
        )

        risk_free_rate_percent = st.number_input(
            "Annual risk-free rate (%)",
            min_value=-99.0,
            value=0.0,
            step=0.25,
            key="validation_risk_free_rate_percent",
        )

        parameter_grid = get_optimization_grid(strategy_name)
        raw_combinations = _count_grid_combinations(parameter_grid)

        st.caption(
            f"Training optimization uses the predefined research grid: "
            f"{raw_combinations:,} raw combinations before structural "
            "validation."
        )

        run_validation = st.button(
            "Run validation",
            type="primary",
            width="stretch",
        )

    if start_date >= split_date:
        st.error(
            "The training start date must be earlier than the out-of-sample "
            "start date."
        )
        return

    if split_date >= end_date:
        st.error(
            "The out-of-sample start date must be earlier than the test end "
            "date."
        )
        return

    current_settings = {
        "ticker": ticker,
        "start_date": start_date.isoformat(),
        "split_date": split_date.isoformat(),
        "end_date": end_date.isoformat(),
        "strategy_name": strategy_name,
        "objective": objective,
        "initial_capital": float(initial_capital),
        "transaction_cost_bps": float(transaction_cost_bps),
        "risk_free_rate_percent": float(risk_free_rate_percent),
    }

    if run_validation:
        if not ticker:
            st.error("Enter a ticker before running validation.")
            return

        with st.spinner(
            "Optimizing the training sample and evaluating the frozen "
            "parameters out of sample..."
        ):
            try:
                validation = run_cached_validation(
                    ticker=ticker,
                    start_date=start_date.isoformat(),
                    split_date=split_date.isoformat(),
                    end_date=end_date.isoformat(),
                    strategy_name=strategy_name,
                    parameter_grid=parameter_grid,
                    objective=objective,
                    initial_capital=float(initial_capital),
                    transaction_cost_bps=float(transaction_cost_bps),
                    risk_free_rate=(
                        float(risk_free_rate_percent) / 100.0
                    ),
                )
            except Exception as error:
                st.error(f"Validation failed: {error}")
                return

        st.session_state["validation_results"] = validation
        st.session_state[
            "validation_settings_used"
        ] = current_settings

    if "validation_results" not in st.session_state:
        st.info(
            "Choose a strategy and split date, then click **Run validation**."
        )
        return

    validation = st.session_state["validation_results"]
    settings_used = st.session_state.get(
        "validation_settings_used"
    )

    if settings_used != current_settings:
        st.warning(
            "The controls have changed since this validation was run. Click "
            "**Run validation** to refresh the results."
        )

    st.warning(
        "The test period is unseen by the parameter-selection step, which is "
        "stronger evidence than the in-sample Optimization Lab. It is still one "
        "historical split, however, and should not be treated as proof of future "
        "performance. Walk-forward testing will provide a more demanding next "
        "validation layer."
    )

    training_end = validation.default.training_results.index[-1]
    test_start = validation.default.test_results.index[0]
    test_end = validation.default.test_results.index[-1]

    st.caption(
        f"Training observations: {validation.default.training_results.index[0].date()} "
        f"to {training_end.date()} · Out-of-sample observations: "
        f"{test_start.date()} to {test_end.date()} · Objective: "
        f"{selected_objective if settings_used == current_settings else validation.objective}"
    )

    _render_parameter_sets(validation)
    _render_objective_diagnostics(validation)
    _render_validation_table(validation)
    _render_test_equity_chart(validation)



@st.cache_data
def run_cached_walk_forward_validation(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
    objective: OptimizationObjective,
    training_window_type: WalkForwardWindowType,
    initial_training_years: int,
    test_window_years: int,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
) -> WalkForwardResults:
    """Download one sample and cache a walk-forward study."""
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return validate_strategy_walk_forward(
        data=market_data,
        strategy_name=strategy_name,
        parameter_grid=parameter_grid,
        objective=objective,
        training_window_type=training_window_type,
        initial_training_years=initial_training_years,
        test_window_years=test_window_years,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
    )


def _render_walk_forward_fold_table(
    walk_forward: WalkForwardResults,
) -> None:
    """Render the fold-by-fold unseen objective results."""
    st.subheader("Fold-by-fold out-of-sample results")

    table = walk_forward.fold_summary.copy()
    table = table.rename(
        columns={
            "fold": "Fold",
            "training_start": "Training Start",
            "training_end": "Training End",
            "test_start": "Test Start",
            "test_end": "Test End",
            "training_robustness": "Training Robustness",
            "default_test_objective": "Default Test Objective",
            "raw_test_objective": "Raw Optimum Test Objective",
            "robust_test_objective": "Robust Candidate Test Objective",
            "benchmark_test_objective": "Buy and Hold Test Objective",
            "raw_relative_oos_degradation": "Raw Relative OOS Degradation",
            "robust_relative_oos_degradation": (
                "Robust Relative OOS Degradation"
            ),
            "raw_beats_default": "Raw Beats Default",
            "robust_beats_default": "Robust Beats Default",
            "robust_beats_raw": "Robust Beats Raw",
        }
    )

    visible_columns = [
        "Fold",
        "Training End",
        "Test Start",
        "Test End",
        "Training Robustness",
        "Default Test Objective",
        "Raw Optimum Test Objective",
        "Robust Candidate Test Objective",
        "Buy and Hold Test Objective",
        "Raw Relative OOS Degradation",
        "Robust Relative OOS Degradation",
        "Raw Beats Default",
        "Robust Beats Default",
        "Robust Beats Raw",
    ]
    table = table[visible_columns]

    for date_column in [
        "Training End",
        "Test Start",
        "Test End",
    ]:
        table[date_column] = (
            pd.to_datetime(table[date_column])
            .dt.strftime("%Y-%m-%d")
        )

    objective_percent = walk_forward.objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }
    objective_format = "{:.2%}" if objective_percent else "{:.3f}"

    st.dataframe(
        table.style.format(
            {
                "Default Test Objective": objective_format,
                "Raw Optimum Test Objective": objective_format,
                "Robust Candidate Test Objective": objective_format,
                "Buy and Hold Test Objective": objective_format,
                "Raw Relative OOS Degradation": "{:+.1%}",
                "Robust Relative OOS Degradation": "{:+.1%}",
            }
        ),
        width="stretch",
        hide_index=True,
    )


def _render_walk_forward_aggregate(
    walk_forward: WalkForwardResults,
) -> None:
    """Render aggregate evidence across repeated unseen test periods."""
    st.subheader("Aggregate walk-forward evidence")

    summary = walk_forward.aggregate_summary.set_index("parameter_set")
    raw_row = summary.loc[["Raw optimum"]].iloc[0]
    robust_row = summary.loc[["Robust candidate"]].iloc[0]

    raw_beats_default_share = float(
        cast(Any, raw_row.at["beats_default_share"])
    )
    robust_beats_default_share = float(
        cast(Any, robust_row.at["beats_default_share"])
    )

    metric_columns = st.columns(4)
    metric_columns[0].metric(
        "Completed test folds",
        str(len(walk_forward.folds)),
    )
    metric_columns[1].metric(
        "Raw optimum beat default",
        f"{raw_beats_default_share:.1%}",
    )
    metric_columns[2].metric(
        "Robust candidate beat default",
        f"{robust_beats_default_share:.1%}",
    )
    metric_columns[3].metric(
        "Robust candidate beat raw",
        f"{float(walk_forward.fold_summary['robust_beats_raw'].mean()):.1%}",
    )

    display = walk_forward.aggregate_summary.copy().rename(
        columns={
            "parameter_set": "Parameter Set",
            "folds": "Folds",
            "median_test_objective": "Median Test Objective",
            "mean_test_objective": "Mean Test Objective",
            "worst_test_objective": "Worst Test Objective",
            "best_test_objective": "Best Test Objective",
            "beats_default_share": "Beat Default Share",
            "stitched_final_value": "Stitched Final Value",
            "stitched_total_return": "Stitched Total Return",
            "stitched_cagr": "Stitched CAGR",
            "stitched_max_drawdown": "Stitched Maximum Drawdown",
        }
    )

    objective_percent = walk_forward.objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }
    objective_format = "{:.2%}" if objective_percent else "{:.3f}"

    st.dataframe(
        display.style.format(
            {
                "Median Test Objective": objective_format,
                "Mean Test Objective": objective_format,
                "Worst Test Objective": objective_format,
                "Best Test Objective": objective_format,
                "Beat Default Share": "{:.1%}",
                "Stitched Final Value": "${:,.2f}",
                "Stitched Total Return": "{:.2%}",
                "Stitched CAGR": "{:.2%}",
                "Stitched Maximum Drawdown": "{:.2%}",
            },
            na_rep="N/A",
        ),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Each fold is optimized only with information available before that "
        "fold's test period. Fold-level metrics remain independently rebased "
        "to the selected validation capital, while the stitched strategy curves "
        "represent one continuous out-of-sample portfolio. At each fold boundary, "
        "transaction costs are charged only on the actual change from the previous "
        "fold's final exposure to the newly selected fold's first exposure. Buy "
        "and Hold remains continuously invested and pays one initial entry cost."
    )


def _render_walk_forward_parameter_history(
    walk_forward: WalkForwardResults,
) -> None:
    """Show how selected parameters change across walk-forward folds."""
    st.subheader("Parameter stability across folds")

    history = walk_forward.parameter_history.copy()
    history = history.rename(
        columns={
            "fold": "Fold",
            "training_end": "Training End",
            "test_start": "Test Start",
            "test_end": "Test End",
            "training_robustness": "Training Robustness",
        }
    )

    date_columns = [
        "Training End",
        "Test Start",
        "Test End",
    ]
    for column in date_columns:
        history[column] = (
            pd.to_datetime(history[column])
            .dt.strftime("%Y-%m-%d")
        )

    st.dataframe(
        history,
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "Large jumps in selected parameters from one fold to the next can be a "
        "sign that the apparent optimum is regime-dependent or sensitive to "
        "sampling noise. Repeatedly similar selections are more reassuring, "
        "although they still do not guarantee future stability."
    )


def _render_walk_forward_equity_chart(
    walk_forward: WalkForwardResults,
) -> None:
    """Plot the chronologically stitched unseen-period equity curves."""
    st.subheader("Stitched out-of-sample equity curves")

    chart_data = (
        walk_forward.stitched_equity_curves
        .rename_axis("Date")
        .reset_index()
        .melt(
            id_vars="Date",
            var_name="Parameter set",
            value_name="Portfolio value",
        )
    )

    figure = px.line(
        chart_data,
        x="Date",
        y="Portfolio value",
        color="Parameter set",
        title="Walk-Forward Out-of-Sample Portfolio Value",
    )
    figure.update_layout(
        hovermode="x unified",
        yaxis_title="Portfolio value",
    )

    st.plotly_chart(
        figure,
        width="stretch",
    )


def _render_walk_forward_validation_page() -> None:
    """Render expanding- or rolling-window walk-forward validation."""
    with st.sidebar:
        st.header("Walk-forward settings")

        selected_strategy = st.selectbox(
            "Strategy",
            options=list(STRATEGY_OPTIONS),
            key="walk_forward_strategy",
        )
        strategy_name = STRATEGY_OPTIONS[selected_strategy]

        ticker = (
            st.text_input(
                "Ticker",
                value="AAPL",
                key="walk_forward_ticker",
            )
            .upper()
            .strip()
        )

        start_date = st.date_input(
            "Historical start date",
            value=date(2020, 1, 1),
            key="walk_forward_start_date",
        )

        end_date = st.date_input(
            "Historical end date",
            value=date(2026, 1, 1),
            key="walk_forward_end_date",
        )

        training_window_label = st.radio(
            "Training window",
            options=[
                "Expanding",
                "Rolling",
            ],
            key="walk_forward_training_window_type",
            help=(
                "Expanding keeps the original training start and adds all new "
                "history before each test fold. Rolling keeps only the most "
                "recent fixed-length training window, so older observations "
                "drop out as the study advances."
            ),
        )
        training_window_type = (
            "rolling"
            if training_window_label == "Rolling"
            else "expanding"
        )

        training_period_label = (
            "Training window (years)"
            if training_window_type == "rolling"
            else "Initial training period (years)"
        )
        training_period_help = (
            "Rolling mode always optimizes on approximately this many calendar "
            "years immediately before each unseen test window."
            if training_window_type == "rolling"
            else (
                "The first unseen test begins after this many calendar years. "
                "Later folds keep the same historical start and expand the "
                "training sample."
            )
        )

        initial_training_years = st.number_input(
            training_period_label,
            min_value=1,
            value=2,
            step=1,
            key="walk_forward_initial_training_years",
            help=training_period_help,
        )

        test_window_years = st.number_input(
            "Test window (years)",
            min_value=1,
            value=1,
            step=1,
            key="walk_forward_test_window_years",
            help=(
                "Length of each non-overlapping unseen test period. Parameters "
                "are re-optimized using only prior observations before every "
                "new test window."
            ),
        )

        selected_objective = st.selectbox(
            "Optimization objective",
            options=list(OBJECTIVE_OPTIONS),
            key="walk_forward_objective",
        )
        objective = OBJECTIVE_OPTIONS[selected_objective]

        initial_capital = st.number_input(
            "Initial capital",
            min_value=1.0,
            value=10_000.0,
            step=1_000.0,
            key="walk_forward_initial_capital",
        )

        transaction_cost_bps = st.number_input(
            "One-way transaction cost (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="walk_forward_transaction_cost_bps",
        )

        risk_free_rate_percent = st.number_input(
            "Annual risk-free rate (%)",
            min_value=-99.0,
            value=0.0,
            step=0.25,
            key="walk_forward_risk_free_rate_percent",
        )

        parameter_grid = get_optimization_grid(strategy_name)
        raw_combinations = _count_grid_combinations(parameter_grid)

        st.caption(
            f"Every fold uses the predefined research grid: "
            f"{raw_combinations:,} raw combinations before structural "
            "validation. The grid is re-evaluated independently for each "
            f"{training_window_label.lower()} training sample."
        )

        run_walk_forward = st.button(
            "Run walk-forward validation",
            type="primary",
            width="stretch",
        )

    if start_date >= end_date:
        st.error("The historical start date must be earlier than the end date.")
        return

    current_settings = {
        "ticker": ticker,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "strategy_name": strategy_name,
        "objective": objective,
        "training_window_type": training_window_type,
        "initial_training_years": int(initial_training_years),
        "test_window_years": int(test_window_years),
        "initial_capital": float(initial_capital),
        "transaction_cost_bps": float(transaction_cost_bps),
        "risk_free_rate_percent": float(risk_free_rate_percent),
    }

    if run_walk_forward:
        if not ticker:
            st.error("Enter a ticker before running walk-forward validation.")
            return

        training_description = (
            "fixed-length rolling training samples"
            if training_window_type == "rolling"
            else "expanding training samples"
        )
        with st.spinner(
            f"Repeatedly optimizing {training_description} and evaluating "
            "the frozen parameters on unseen test windows..."
        ):
            try:
                walk_forward = run_cached_walk_forward_validation(
                    ticker=ticker,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    strategy_name=strategy_name,
                    parameter_grid=parameter_grid,
                    objective=objective,
                    training_window_type=training_window_type,
                    initial_training_years=int(initial_training_years),
                    test_window_years=int(test_window_years),
                    initial_capital=float(initial_capital),
                    transaction_cost_bps=float(transaction_cost_bps),
                    risk_free_rate=(
                        float(risk_free_rate_percent) / 100.0
                    ),
                )
            except Exception as error:
                st.error(f"Walk-forward validation failed: {error}")
                return

        st.session_state["walk_forward_results"] = walk_forward
        st.session_state[
            "walk_forward_settings_used"
        ] = current_settings

    if "walk_forward_results" not in st.session_state:
        st.info(
            "Choose a strategy and historical range, then click "
            "**Run walk-forward validation**."
        )
        return

    walk_forward = st.session_state["walk_forward_results"]
    settings_used = st.session_state.get(
        "walk_forward_settings_used"
    )

    if settings_used != current_settings:
        st.warning(
            "The controls have changed since this walk-forward study was run. "
            "Click **Run walk-forward validation** to refresh the results."
        )

    st.warning(
        "Walk-forward validation repeatedly re-selects parameters using only "
        "past observations and then evaluates them on the next unseen period. "
        "This is substantially stronger evidence than one in-sample optimum or "
        "one train/test split, but it remains a historical simulation rather "
        "than proof of future performance."
    )

    first_fold = walk_forward.folds[0]
    last_fold = walk_forward.folds[-1]
    window_description = (
        f"Rolling {walk_forward.initial_training_years}-year training window"
        if getattr(walk_forward, "training_window_type", "expanding") == "rolling"
        else "Expanding training window"
    )
    st.caption(
        f"{window_description} · {len(walk_forward.folds)} complete folds · "
        f"first test: {first_fold.test_start.date()} to "
        f"{first_fold.test_end.date()} · last test: "
        f"{last_fold.test_start.date()} to {last_fold.test_end.date()} · "
        f"Objective: {selected_objective if settings_used == current_settings else walk_forward.objective}"
    )

    _render_walk_forward_aggregate(walk_forward)
    _render_walk_forward_fold_table(walk_forward)
    _render_walk_forward_parameter_history(walk_forward)
    _render_walk_forward_equity_chart(walk_forward)