from datetime import date
from functools import reduce
from math import floor
from operator import mul
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from backtester import prepare_market_data
from optimization import (
    CoarseToFineOptimizationResults,
    OptimizationObjective,
    OptimizationResults,
    calculate_optimization_gain,
    calculate_relative_optimization_gain,
    calculate_optimization_robustness,
    create_parameter_sensitivity_profile,
    create_parameter_sensitivity_summary,
    create_parameter_sensitivity_table,
    optimize_strategy,
    optimize_strategy_coarse_to_fine,
)
from strategies import (
    STRATEGY_METADATA,
    get_optimization_grid,
)


OBJECTIVE_OPTIONS: dict[str, OptimizationObjective] = {
    "Sharpe Ratio": "sharpe_ratio",
    "Total Return": "total_return",
    "CAGR": "cagr",
    "Annualized Volatility": "annualized_volatility",
    "Maximum Drawdown": "max_drawdown",
}


@st.cache_data
def run_cached_optimization(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
    objective: OptimizationObjective,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
) -> OptimizationResults:
    """Run and cache one parameter-grid optimization."""
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return optimize_strategy(
        data=market_data,
        strategy_name=strategy_name,
        parameter_grid=parameter_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
    )


@st.cache_data
def run_cached_coarse_to_fine_optimization(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    broad_parameter_grid: dict[str, list[Any]],
    objective: OptimizationObjective,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
    refinement_points: int,
) -> CoarseToFineOptimizationResults:
    """Run and cache a two-stage coarse-to-fine optimization."""
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    return optimize_strategy_coarse_to_fine(
        data=market_data,
        strategy_name=strategy_name,
        broad_parameter_grid=broad_parameter_grid,
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
        refinement_points=refinement_points,
    )


def _format_parameter_value(
    strategy_name: str,
    parameter_name: str,
    value: Any,
) -> str:
    """Format a parameter using its strategy metadata."""
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
    """Create a compact human-readable parameter-set description."""
    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    parts: list[str] = []

    for parameter_name, value in parameters.items():
        label = parameter_specs[parameter_name]["label"]
        formatted_value = _format_parameter_value(
            strategy_name=strategy_name,
            parameter_name=parameter_name,
            value=value,
        )
        parts.append(f"{label}: {formatted_value}")

    return " | ".join(parts)


def _format_objective_value(
    objective: OptimizationObjective,
    value: float,
) -> str:
    """Format an optimization objective for display."""
    if objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }:
        return f"{value:.2%}"

    return f"{value:.3f}"


def _format_absolute_gain(
    objective: OptimizationObjective,
    value: float,
) -> str:
    """Format objective improvement without changing its meaning."""
    if objective in {
        "total_return",
        "cagr",
        "annualized_volatility",
        "max_drawdown",
    }:
        return f"{value:+.2%}"

    return f"{value:+.3f}"


def _count_grid_combinations(
    parameter_grid: dict[str, list[Any]],
) -> int:
    """Return the raw Cartesian-product size of an optimization grid."""
    lengths = [len(values) for values in parameter_grid.values()]

    if not lengths:
        return 0

    return reduce(mul, lengths, 1)


def _estimate_refined_grid_combinations(
    parameter_grid: dict[str, list[Any]],
    refinement_points: int,
) -> int:
    """Estimate the maximum local-grid size before the broad stage runs."""
    lengths = [
        1 if len(values) <= 1 else refinement_points
        for values in parameter_grid.values()
    ]

    if not lengths:
        return 0

    return reduce(mul, lengths, 1)


CUSTOM_GRID_HARD_LIMIT = 10_000


def _infer_default_custom_step(
    values: list[Any],
    parameter_type: str,
) -> float | int:
    """Infer a practical custom-grid step from the predefined grid."""
    numeric_values = sorted({float(value) for value in values})

    differences = [
        current - previous
        for previous, current in zip(
            numeric_values,
            numeric_values[1:],
        )
        if current > previous
    ]

    if not differences:
        return 1 if parameter_type == "int" else 0.1

    smallest_difference = min(differences)

    if parameter_type == "int":
        return max(1, int(round(smallest_difference)))

    return float(smallest_difference)


def _create_grid_values(
    minimum: float | int,
    maximum: float | int,
    step: float | int,
    parameter_type: str,
) -> list[Any]:
    """Create an inclusive numeric grid without floating-point drift."""
    minimum_float = float(minimum)
    maximum_float = float(maximum)
    step_float = float(step)

    if step_float <= 0:
        raise ValueError("Custom-grid step must be positive.")

    if minimum_float > maximum_float:
        raise ValueError(
            "Custom-grid minimum cannot exceed its maximum."
        )

    number_of_steps = floor(
        (maximum_float - minimum_float) / step_float
        + 1e-12
    )

    values = [
        minimum_float + index * step_float
        for index in range(number_of_steps + 1)
    ]

    if parameter_type == "int":
        return [int(round(value)) for value in values]

    return [round(value, 12) for value in values]


def _render_custom_grid_controls(
    strategy_name: str,
    predefined_grid: dict[str, list[Any]],
) -> dict[str, list[Any]]:
    """Render user-editable min/max/step controls for every parameter."""
    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    custom_grid: dict[str, list[Any]] = {}

    with st.expander(
        "Custom parameter ranges",
        expanded=True,
    ):
        st.caption(
            "Choose the minimum, maximum, and step for each parameter. "
            "The exact generated values and raw combination count are "
            "shown below before you run the optimization."
        )

        for parameter_name, specification in (
            parameter_specs.items()
        ):
            predefined_values = predefined_grid[parameter_name]
            parameter_type = str(specification["type"])
            is_percent = (
                specification.get("format") == "percent"
            )
            scale = 100.0 if is_percent else 1.0

            raw_default_minimum = min(predefined_values)
            raw_default_maximum = max(predefined_values)
            raw_default_step = _infer_default_custom_step(
                values=predefined_values,
                parameter_type=parameter_type,
            )

            display_minimum_bound = float(
                specification["min"]
            ) * scale
            display_maximum_bound = float(
                specification["max"]
            ) * scale
            display_default_minimum = (
                float(raw_default_minimum) * scale
            )
            display_default_maximum = (
                float(raw_default_maximum) * scale
            )
            display_default_step = (
                float(raw_default_step) * scale
            )

            parameter_label = str(specification["label"])
            if is_percent:
                parameter_label += " (%)"

            st.markdown(f"**{parameter_label}**")
            control_columns = st.columns(3)

            if parameter_type == "int" and not is_percent:
                minimum_value = control_columns[0].number_input(
                    "Minimum",
                    min_value=int(specification["min"]),
                    max_value=int(specification["max"]),
                    value=int(raw_default_minimum),
                    step=1,
                    key=(
                        f"optimization_custom_{strategy_name}_"
                        f"{parameter_name}_min"
                    ),
                )
                maximum_value = control_columns[1].number_input(
                    "Maximum",
                    min_value=int(specification["min"]),
                    max_value=int(specification["max"]),
                    value=int(raw_default_maximum),
                    step=1,
                    key=(
                        f"optimization_custom_{strategy_name}_"
                        f"{parameter_name}_max"
                    ),
                )
                step_value = control_columns[2].number_input(
                    "Step",
                    min_value=1,
                    value=int(raw_default_step),
                    step=1,
                    key=(
                        f"optimization_custom_{strategy_name}_"
                        f"{parameter_name}_step"
                    ),
                )

                custom_grid[parameter_name] = _create_grid_values(
                    minimum=int(minimum_value),
                    maximum=int(maximum_value),
                    step=int(step_value),
                    parameter_type=parameter_type,
                )
                continue

            input_step = max(
                display_default_step,
                float(specification["step"]) * scale,
                1e-9,
            )

            minimum_display = control_columns[0].number_input(
                "Minimum",
                min_value=display_minimum_bound,
                max_value=display_maximum_bound,
                value=display_default_minimum,
                step=input_step,
                key=(
                    f"optimization_custom_{strategy_name}_"
                    f"{parameter_name}_min"
                ),
            )
            maximum_display = control_columns[1].number_input(
                "Maximum",
                min_value=display_minimum_bound,
                max_value=display_maximum_bound,
                value=display_default_maximum,
                step=input_step,
                key=(
                    f"optimization_custom_{strategy_name}_"
                    f"{parameter_name}_max"
                ),
            )
            step_display = control_columns[2].number_input(
                "Step",
                min_value=float(specification["step"]) * scale,
                value=display_default_step,
                step=float(specification["step"]) * scale,
                key=(
                    f"optimization_custom_{strategy_name}_"
                    f"{parameter_name}_step"
                ),
            )

            custom_grid[parameter_name] = _create_grid_values(
                minimum=float(minimum_display) / scale,
                maximum=float(maximum_display) / scale,
                step=float(step_display) / scale,
                parameter_type=parameter_type,
            )

    return custom_grid


def _render_grid_size_notice(
    combination_count: int,
) -> None:
    """Explain the expected computational size of the selected grid."""
    if combination_count <= 500:
        st.caption(
            f"Raw grid size: {combination_count:,} combinations before "
            "structural validation. This is a light interactive search."
        )
        return

    if combination_count <= 5_000:
        st.info(
            f"Raw grid size: {combination_count:,} combinations before "
            "structural validation. This is a moderately sized search."
        )
        return

    if combination_count <= CUSTOM_GRID_HARD_LIMIT:
        st.warning(
            f"Raw grid size: {combination_count:,} combinations before "
            "structural validation. This may take noticeably longer."
        )
        return

    st.error(
        f"Raw grid size: {combination_count:,} combinations before "
        f"structural validation. The interactive limit is "
        f"{CUSTOM_GRID_HARD_LIMIT:,}. Increase the step sizes or narrow "
        "the ranges before running the optimization."
    )


def _render_refined_grid_size_notice(
    combination_count: int,
) -> None:
    """Explain the expected computational size of coarse-to-fine stage 2."""
    if combination_count <= 500:
        st.caption(
            f"Estimated Stage 2 size: up to {combination_count:,} raw "
            "combinations before structural validation. This is a light "
            "interactive refinement."
        )
        return

    if combination_count <= 5_000:
        st.info(
            f"Estimated Stage 2 size: up to {combination_count:,} raw "
            "combinations before structural validation. This is a "
            "moderately sized refinement."
        )
        return

    if combination_count <= CUSTOM_GRID_HARD_LIMIT:
        st.warning(
            f"Estimated Stage 2 size: up to {combination_count:,} raw "
            "combinations before structural validation. This may take "
            "noticeably longer."
        )
        return

    st.error(
        f"Estimated Stage 2 size: up to {combination_count:,} raw "
        f"combinations before structural validation. The interactive "
        f"limit is {CUSTOM_GRID_HARD_LIMIT:,}. Reduce the refinement "
        "points per parameter before running the optimization."
    )


def _filter_sensitivity_slice(
    optimization_result: OptimizationResults,
    row_parameter: str,
    column_parameter: str,
) -> pd.DataFrame:
    """
    Hold all non-plotted parameters at their optimized values.

    This converts higher-dimensional optimizations into an interpretable
    two-parameter sensitivity slice without averaging across unrelated
    parameter configurations.
    """
    filtered = optimization_result.results.copy()

    for parameter_name, parameter_value in (
        optimization_result.best_parameters.items()
    ):
        if parameter_name in {
            row_parameter,
            column_parameter,
        }:
            continue

        filtered = filtered[
            filtered[parameter_name] == parameter_value
        ]

    return filtered


def _calculate_near_optimal_count(
    optimization_result: OptimizationResults,
) -> tuple[int, int]:
    """Count combinations whose objective is within 5% of the best value."""
    objective = optimization_result.objective
    objective_values = (
        optimization_result.results[objective]
        .astype(float)
        .replace([np.inf, -np.inf], np.nan)
        .dropna()
    )

    total = int(len(objective_values))

    if total == 0:
        return 0, 0

    best_value = float(
        optimization_result.best_metrics[objective]
    )

    tolerance = 0.05 * max(abs(best_value), 1e-12)

    if objective == "annualized_volatility":
        near_optimal = int(
            (objective_values <= best_value + tolerance).sum()
        )
    else:
        near_optimal = int(
            (objective_values >= best_value - tolerance).sum()
        )

    return near_optimal, total


def _render_grid_preview(
    strategy_name: str,
    parameter_grid: dict[str, list[Any]],
) -> None:
    """Show exactly which predefined parameter values will be evaluated."""
    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    preview_rows: list[dict[str, str]] = []

    for parameter_name, values in parameter_grid.items():
        preview_rows.append(
            {
                "Parameter": parameter_specs[
                    parameter_name
                ]["label"],
                "Values": ", ".join(
                    _format_parameter_value(
                        strategy_name=strategy_name,
                        parameter_name=parameter_name,
                        value=value,
                    )
                    for value in values
                ),
            }
        )

    st.dataframe(
        pd.DataFrame(preview_rows),
        use_container_width=True,
        hide_index=True,
    )



def _render_parameter_sensitivity_profiles(
    optimization_result: OptimizationResults,
    strategy_name: str,
    objective_display_name: str,
) -> None:
    """
    Visualize marginal one-parameter sensitivity for larger search spaces.

    Every point is the median objective across all valid tested combinations
    containing that parameter value. This complements, rather than replaces,
    the conditional two-parameter heatmap below.
    """
    parameter_names = list(
        optimization_result.best_parameters
    )

    sensitivity_summary = (
        create_parameter_sensitivity_summary(
            results=optimization_result.results,
            parameter_names=parameter_names,
            metric=optimization_result.objective,
            objective=optimization_result.objective,
        )
    )

    if sensitivity_summary.empty:
        st.info(
            "No finite parameter-sensitivity profiles could be "
            "calculated for this optimization result."
        )
        return

    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    st.subheader("Higher-dimensional sensitivity")

    st.caption(
        "For each parameter value, the chart shows the median selected "
        "objective across every valid tested combination containing that "
        "value. This makes strategies with three or more parameters easier "
        "to inspect without pretending that a two-dimensional heatmap can "
        "represent the entire parameter space."
    )

    ranking = sensitivity_summary.copy()

    ranking["Parameter"] = ranking["parameter"].map(
        lambda name: parameter_specs[name]["label"]
    )

    ranking["Most favorable tested value"] = ranking.apply(
        lambda row: _format_parameter_value(
            strategy_name=strategy_name,
            parameter_name=str(row["parameter"]),
            value=row["best_parameter_value"],
        ),
        axis=1,
    )

    ranking["Weakest tested value"] = ranking.apply(
        lambda row: _format_parameter_value(
            strategy_name=strategy_name,
            parameter_name=str(row["parameter"]),
            value=row["weakest_parameter_value"],
        ),
        axis=1,
    )

    ranking["Sensitivity spread"] = ranking[
        "sensitivity_spread"
    ]
    ranking["Best median objective"] = ranking[
        "best_median_objective"
    ]
    ranking["Weakest median objective"] = ranking[
        "weakest_median_objective"
    ]
    ranking["Tested values"] = ranking[
        "tested_values"
    ]

    ranking_display = ranking[
        [
            "Parameter",
            "Sensitivity spread",
            "Most favorable tested value",
            "Best median objective",
            "Weakest tested value",
            "Weakest median objective",
            "Tested values",
        ]
    ]

    objective_format = (
        "{:.2%}"
        if optimization_result.objective in {
            "total_return",
            "cagr",
            "annualized_volatility",
            "max_drawdown",
        }
        else "{:.3f}"
    )

    st.dataframe(
        ranking_display.style.format(
            {
                "Sensitivity spread": objective_format,
                "Best median objective": objective_format,
                "Weakest median objective": objective_format,
                "Tested values": "{:.0f}",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    st.caption(
        "A larger sensitivity spread means the selected objective changed "
        "more across the tested values of that parameter. It is a "
        "descriptive robustness diagnostic, not causal feature importance."
    )

    chart_columns = st.columns(2)

    for parameter_index, parameter_name in enumerate(
        parameter_names
    ):
        profile = create_parameter_sensitivity_profile(
            results=optimization_result.results,
            parameter_name=parameter_name,
            metric=optimization_result.objective,
        )

        parameter_label = parameter_specs[
            parameter_name
        ]["label"]

        figure = px.line(
            profile,
            x=parameter_name,
            y="median_objective",
            markers=True,
            labels={
                parameter_name: parameter_label,
                "median_objective": (
                    f"Median {objective_display_name}"
                ),
            },
            title=(
                f"{parameter_label} — Median "
                f"{objective_display_name}"
            ),
        )

        if optimization_result.objective in {
            "total_return",
            "cagr",
            "annualized_volatility",
            "max_drawdown",
        }:
            figure.update_yaxes(tickformat=".0%")

        figure.update_layout(
            hovermode="x unified",
        )

        chart_columns[
            parameter_index % 2
        ].plotly_chart(
            figure,
            use_container_width=True,
        )


def render_optimization_page() -> None:
    """Render the in-sample parameter-optimization research page."""
    st.title("Optimization Lab")

    st.write(
        "Evaluate a strategy across a predefined or custom parameter grid, "
        "compare the best configuration with the default settings, "
        "and inspect parameter sensitivity."
    )

    display_to_key = {
        metadata["display_name"]: strategy_name
        for strategy_name, metadata in STRATEGY_METADATA.items()
    }

    with st.sidebar:
        st.header("Optimization settings")

        selected_strategy = st.selectbox(
            "Strategy",
            options=list(display_to_key),
            index=list(display_to_key).index(
                "Donchian Breakout"
            ),
            key="optimization_strategy",
        )

        strategy_name = display_to_key[
            selected_strategy
        ]

        search_mode = st.radio(
            "Search grid",
            options=[
                "Predefined",
                "Custom",
                "Coarse-to-Fine",
            ],
            horizontal=True,
            key="optimization_search_mode",
        )

        predefined_grid = get_optimization_grid(
            strategy_name
        )

        refinement_points = 5

        if search_mode == "Custom":
            current_grid = _render_custom_grid_controls(
                strategy_name=strategy_name,
                predefined_grid=predefined_grid,
            )
        elif search_mode == "Coarse-to-Fine":
            current_grid = predefined_grid

            refinement_points = int(
                st.number_input(
                    "Refinement points per parameter",
                    min_value=3,
                    max_value=9,
                    value=5,
                    step=1,
                    key="optimization_refinement_points",
                    help=(
                        "After Stage 1 finds the best broad-grid setting, "
                        "Stage 2 takes the neighboring broad-grid interval "
                        "around that winner and creates approximately this "
                        "many evenly spaced candidate values for each "
                        "parameter. Integer parameters are rounded and "
                        "deduplicated; decimal and percentage parameters "
                        "are interpolated numerically. The Stage 2 search "
                        "size grows multiplicatively across parameters."
                    ),
                )
            )
        else:
            current_grid = predefined_grid

        raw_grid_size = _count_grid_combinations(
            current_grid
        )

        estimated_refined_grid_size = (
            _estimate_refined_grid_combinations(
                parameter_grid=current_grid,
                refinement_points=refinement_points,
            )
            if search_mode == "Coarse-to-Fine"
            else 0
        )

        if search_mode == "Coarse-to-Fine":
            st.caption(
                "Refinement points are candidate values per parameter, "
                "not a numeric amount added to each parameter. Stage 2 "
                "interpolates them within the local interval around the "
                "broad-stage winner."
            )
            _render_refined_grid_size_notice(
                combination_count=estimated_refined_grid_size
            )

        with st.form("optimization_settings_form"):
            ticker = (
                st.text_input(
                    "Ticker",
                    value="AAPL",
                    key="optimization_ticker",
                )
                .upper()
                .strip()
            )

            start_date = st.date_input(
                "Start date",
                value=date(2020, 1, 1),
                key="optimization_start_date",
            )

            end_date = st.date_input(
                "End date",
                value=date(2026, 1, 1),
                key="optimization_end_date",
            )

            selected_objective = st.selectbox(
                "Optimization objective",
                options=list(OBJECTIVE_OPTIONS),
                index=0,
                key="optimization_objective",
            )

            objective = OBJECTIVE_OPTIONS[
                selected_objective
            ]

            initial_capital = st.number_input(
                "Initial capital",
                min_value=100.0,
                value=10_000.0,
                step=1_000.0,
                key="optimization_initial_capital",
            )

            transaction_cost_bps = st.number_input(
                "One-way transaction cost (bps)",
                min_value=0.0,
                value=10.0,
                step=1.0,
                key="optimization_transaction_cost",
            )

            risk_free_rate_percent = st.number_input(
                "Annual risk-free rate (%)",
                min_value=-99.0,
                value=0.0,
                step=0.25,
                key="optimization_risk_free_rate",
            )

            run_button = st.form_submit_button(
                "Run optimization",
                type="primary",
                use_container_width=True,
            )

        if search_mode == "Predefined":
            grid_expander_label = "Predefined parameter grid"
        elif search_mode == "Custom":
            grid_expander_label = "Custom parameter grid preview"
        else:
            grid_expander_label = "Coarse-to-fine broad grid"

        with st.expander(
            grid_expander_label,
            expanded=(search_mode == "Custom"),
        ):
            _render_grid_size_notice(
                combination_count=raw_grid_size
            )

            if search_mode == "Coarse-to-Fine":
                st.caption(
                    "Stage 1 evaluates the broad grid below. Stage 2 then "
                    "builds a denser local grid around the broad-stage "
                    "optimum."
                )
                st.caption(
                    "The Stage 2 estimate shown above is the raw Cartesian "
                    "maximum. Integer rounding, deduplication, parameter "
                    "bounds, and structural validation can reduce the "
                    "number of combinations actually evaluated."
                )

            _render_grid_preview(
                strategy_name=strategy_name,
                parameter_grid=current_grid,
            )

    if run_button:
        if raw_grid_size > CUSTOM_GRID_HARD_LIMIT:
            st.error(
                "The selected grid is too large for the interactive "
                "Optimization Lab. Narrow the ranges or increase the "
                "step sizes before running it."
            )
            st.stop()

        if (
            search_mode == "Coarse-to-Fine"
            and estimated_refined_grid_size
            > CUSTOM_GRID_HARD_LIMIT
        ):
            st.error(
                "The estimated refined grid is too large for the "
                "interactive Optimization Lab. Reduce the refinement "
                "points per parameter before running it."
            )
            st.stop()

        if not ticker:
            st.error("Enter a ticker symbol.")
            st.stop()

        if start_date >= end_date:
            st.error(
                "The start date must be earlier than the end date."
            )
            st.stop()

        try:
            with st.spinner(
                "Running parameter-grid optimization..."
            ):
                coarse_to_fine_result: (
                    CoarseToFineOptimizationResults | None
                ) = None

                if search_mode == "Coarse-to-Fine":
                    coarse_to_fine_result = (
                        run_cached_coarse_to_fine_optimization(
                            ticker=ticker,
                            start_date=start_date.isoformat(),
                            end_date=end_date.isoformat(),
                            strategy_name=strategy_name,
                            broad_parameter_grid=current_grid,
                            objective=objective,
                            initial_capital=float(initial_capital),
                            transaction_cost_bps=float(
                                transaction_cost_bps
                            ),
                            risk_free_rate=(
                                float(risk_free_rate_percent) / 100
                            ),
                            refinement_points=refinement_points,
                        )
                    )
                    result = coarse_to_fine_result.refined_result
                else:
                    result = run_cached_optimization(
                        ticker=ticker,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        strategy_name=strategy_name,
                        parameter_grid=current_grid,
                        objective=objective,
                        initial_capital=float(initial_capital),
                        transaction_cost_bps=float(
                            transaction_cost_bps
                        ),
                        risk_free_rate=(
                            float(risk_free_rate_percent) / 100
                        ),
                    )
        except Exception as error:
            st.error(f"Optimization failed: {error}")
            st.stop()

        st.session_state[
            "optimization_result"
        ] = result

        st.session_state[
            "optimization_context"
        ] = {
            "ticker": ticker,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "strategy_name": strategy_name,
            "strategy_display_name": selected_strategy,
            "search_mode": search_mode,
            "raw_grid_size": raw_grid_size,
            "parameter_grid": current_grid,
            "objective": objective,
            "objective_display_name": selected_objective,
            "initial_capital": float(initial_capital),
            "transaction_cost_bps": float(
                transaction_cost_bps
            ),
            "risk_free_rate": (
                float(risk_free_rate_percent) / 100
            ),
        }

        if coarse_to_fine_result is not None:
            st.session_state[
                "optimization_context"
            ].update(
                {
                    "refinement_points": refinement_points,
                    "broad_raw_grid_size": raw_grid_size,
                    "refined_raw_grid_size": (
                        _count_grid_combinations(
                            coarse_to_fine_result.refined_parameter_grid
                        )
                    ),
                    "refined_parameter_grid": (
                        coarse_to_fine_result.refined_parameter_grid
                    ),
                    "broad_best_parameters": (
                        coarse_to_fine_result.broad_result.best_parameters
                    ),
                    "broad_best_metrics": (
                        coarse_to_fine_result.broad_result.best_metrics
                    ),
                }
            )

        parameter_names = list(current_grid)

        if len(parameter_names) >= 2:
            st.session_state[
                "optimization_sensitivity_row"
            ] = parameter_names[0]
            st.session_state[
                "optimization_sensitivity_column"
            ] = parameter_names[1]

    if (
        "optimization_result" not in st.session_state
        or "optimization_context" not in st.session_state
    ):
        st.info(
            "Choose the settings and click **Run optimization**."
        )
        return

    result = st.session_state["optimization_result"]
    context = st.session_state["optimization_context"]

    result_strategy_name = str(
        context["strategy_name"]
    )
    result_objective = result.objective

    optimized_objective_value = float(
        result.best_metrics[result_objective]
    )
    default_objective_value = float(
        result.default_metrics[result_objective]
    )

    absolute_gain = calculate_optimization_gain(
        optimized_value=optimized_objective_value,
        default_value=default_objective_value,
        objective=result_objective,
    )

    relative_gain = calculate_relative_optimization_gain(
        optimized_value=optimized_objective_value,
        default_value=default_objective_value,
        objective=result_objective,
    )

    st.subheader("Optimization summary")

    if context.get("search_mode") == "Coarse-to-Fine":
        grid_description = (
            f"Coarse-to-Fine "
            f"({int(context.get('broad_raw_grid_size', 0)):,} broad + "
            f"{int(context.get('refined_raw_grid_size', 0)):,} refined "
            "raw combinations)"
        )
    else:
        grid_description = (
            f"{context.get('search_mode', 'Predefined')} "
            f"({int(context.get('raw_grid_size', 0)):,} raw combinations)"
        )

    st.caption(
        f"{context['strategy_display_name']} on {context['ticker']} "
        f"from {context['start_date']} to {context['end_date']} · "
        f"Objective: {context['objective_display_name']} · "
        f"Grid: {grid_description}"
    )

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "Default objective",
        _format_objective_value(
            objective=result_objective,
            value=default_objective_value,
        ),
    )

    column_2.metric(
        "Optimized objective",
        _format_objective_value(
            objective=result_objective,
            value=optimized_objective_value,
        ),
    )

    column_3.metric(
        "Absolute improvement",
        _format_absolute_gain(
            objective=result_objective,
            value=absolute_gain,
        ),
    )

    relative_gain_text = (
        "N/A"
        if np.isnan(relative_gain)
        else f"{relative_gain:+.2%}"
    )

    column_4.metric(
        "Relative improvement",
        relative_gain_text,
    )

    parameter_column_1, parameter_column_2 = st.columns(2)

    with parameter_column_1:
        st.markdown("**Default parameters**")
        st.write(
            _format_parameter_set(
                strategy_name=result_strategy_name,
                parameters=result.default_parameters,
            )
        )

    with parameter_column_2:
        st.markdown("**Optimized parameters**")
        st.write(
            _format_parameter_set(
                strategy_name=result_strategy_name,
                parameters=result.best_parameters,
            )
        )

    if context.get("search_mode") == "Coarse-to-Fine":
        st.subheader("Coarse-to-fine stages")

        broad_best_metrics = context.get(
            "broad_best_metrics",
            {},
        )
        broad_best_parameters = context.get(
            "broad_best_parameters",
            {},
        )

        broad_objective_value = float(
            broad_best_metrics[result_objective]
        )

        stage_column_1, stage_column_2, stage_column_3, stage_column_4 = (
            st.columns(4)
        )

        stage_column_1.metric(
            "Broad-stage best",
            _format_objective_value(
                objective=result_objective,
                value=broad_objective_value,
            ),
        )
        stage_column_2.metric(
            "Refined-stage best",
            _format_objective_value(
                objective=result_objective,
                value=optimized_objective_value,
            ),
        )
        stage_column_3.metric(
            "Broad raw combinations",
            f"{int(context.get('broad_raw_grid_size', 0)):,}",
        )
        stage_column_4.metric(
            "Refined raw combinations",
            f"{int(context.get('refined_raw_grid_size', 0)):,}",
        )

        st.markdown("**Broad-stage optimum**")
        st.write(
            _format_parameter_set(
                strategy_name=result_strategy_name,
                parameters=broad_best_parameters,
            )
        )

        st.markdown("**Automatically refined local grid**")
        _render_grid_preview(
            strategy_name=result_strategy_name,
            parameter_grid=context["refined_parameter_grid"],
        )

        st.caption(
            "The broad stage locates a promising region. The refined "
            "stage then searches only the neighborhood between adjacent "
            "broad-grid values around that optimum. This increases local "
            "resolution without brute-forcing the full parameter range."
        )

    st.subheader("Top parameter combinations")

    parameter_columns = list(
        result.best_parameters
    )

    metric_columns = [
        "final_value",
        "total_return",
        "cagr",
        "annualized_volatility",
        "sharpe_ratio",
        "max_drawdown",
        "rebalancing_days",
        "turnover",
    ]

    ranking_table = result.results[
        parameter_columns + metric_columns
    ].head(20).copy()

    rename_map = {
        parameter_name: STRATEGY_METADATA[
            result_strategy_name
        ]["parameters"][parameter_name]["label"]
        for parameter_name in parameter_columns
    }

    rename_map.update(
        {
            "final_value": "Final Value",
            "total_return": "Total Return",
            "cagr": "CAGR",
            "annualized_volatility": "Volatility",
            "sharpe_ratio": "Sharpe Ratio",
            "max_drawdown": "Maximum Drawdown",
            "rebalancing_days": "Rebalancing Days",
            "turnover": "One-Way Turnover",
        }
    )

    display_table = ranking_table.rename(
        columns=rename_map
    )

    st.dataframe(
        display_table.style.format(
            {
                "Final Value": "${:,.2f}",
                "Total Return": "{:.2%}",
                "CAGR": "{:.2%}",
                "Volatility": "{:.2%}",
                "Sharpe Ratio": "{:.3f}",
                "Maximum Drawdown": "{:.2%}",
                "Rebalancing Days": "{:.0f}",
                "One-Way Turnover": "{:.2f}×",
            }
        ),
        use_container_width=True,
        hide_index=True,
    )

    if len(parameter_columns) >= 3:
        _render_parameter_sensitivity_profiles(
            optimization_result=result,
            strategy_name=result_strategy_name,
            objective_display_name=str(
                context["objective_display_name"]
            ),
        )

    if len(parameter_columns) >= 2:
        st.subheader("Parameter sensitivity")

        if len(parameter_columns) >= 3:
            st.caption(
                "This heatmap is a conditional two-parameter slice. "
                "Parameters not shown on the axes are held at their "
                "optimized values; use the profiles above for a broader "
                "view of the full search space."
            )

        sensitivity_column_1, sensitivity_column_2 = (
            st.columns(2)
        )

        row_parameter = sensitivity_column_1.selectbox(
            "Heatmap row parameter",
            options=parameter_columns,
            key="optimization_sensitivity_row",
            format_func=lambda parameter_name: (
                STRATEGY_METADATA[
                    result_strategy_name
                ]["parameters"][parameter_name]["label"]
            ),
        )

        column_options = [
            parameter_name
            for parameter_name in parameter_columns
            if parameter_name != row_parameter
        ]

        current_column = st.session_state.get(
            "optimization_sensitivity_column"
        )

        if current_column not in column_options:
            st.session_state[
                "optimization_sensitivity_column"
            ] = column_options[0]

        column_parameter = sensitivity_column_2.selectbox(
            "Heatmap column parameter",
            options=column_options,
            key="optimization_sensitivity_column",
            format_func=lambda parameter_name: (
                STRATEGY_METADATA[
                    result_strategy_name
                ]["parameters"][parameter_name]["label"]
            ),
        )

        # Streamlit's selectbox type annotation permits None even when
        # a non-empty list of string options is supplied. These assertions
        # narrow the values to str for static type checkers such as Pylance.
        assert isinstance(row_parameter, str)
        assert isinstance(column_parameter, str)

        sensitivity_slice = _filter_sensitivity_slice(
            optimization_result=result,
            row_parameter=row_parameter,
            column_parameter=column_parameter,
        )

        sensitivity_table = (
            create_parameter_sensitivity_table(
                results=sensitivity_slice,
                row_parameter=row_parameter,
                column_parameter=column_parameter,
                metric=result_objective,
            )
        )

        heatmap = px.imshow(
            sensitivity_table,
            text_auto=True,
            aspect="auto",
            labels={
                "x": STRATEGY_METADATA[
                    result_strategy_name
                ]["parameters"][column_parameter]["label"],
                "y": STRATEGY_METADATA[
                    result_strategy_name
                ]["parameters"][row_parameter]["label"],
                "color": context[
                    "objective_display_name"
                ],
            },
            title=(
                f"{context['ticker']} "
                f"{context['strategy_display_name']} "
                f"Parameter Sensitivity — "
                f"{context['objective_display_name']}"
            ),
        )

        if result_objective in {
            "total_return",
            "cagr",
            "annualized_volatility",
            "max_drawdown",
        }:
            heatmap.update_traces(
                texttemplate="%{z:.2%}"
            )
            heatmap.update_layout(
                coloraxis_colorbar={
                    "tickformat": ".0%",
                }
            )
        else:
            heatmap.update_traces(
                texttemplate="%{z:.3f}"
            )

        st.plotly_chart(
            heatmap,
            use_container_width=True,
        )

        fixed_parameters = {
            parameter_name: parameter_value
            for parameter_name, parameter_value
            in result.best_parameters.items()
            if parameter_name not in {
                row_parameter,
                column_parameter,
            }
        }

        if fixed_parameters:
            st.caption(
                "All other parameters are held at their optimized "
                "values for this two-dimensional sensitivity slice: "
                + _format_parameter_set(
                    strategy_name=result_strategy_name,
                    parameters=fixed_parameters,
                )
            )

    st.subheader("Robustness diagnostics")

    robustness = calculate_optimization_robustness(result)

    robustness_column_1, robustness_column_2, robustness_column_3, robustness_column_4 = (
        st.columns(4)
    )

    robustness_column_1.metric(
        "Parameter robustness",
        robustness.robustness_label,
    )

    robustness_column_2.metric(
        "Within 5% of optimum",
        f"{robustness.near_optimal_5_share:.1%}",
        help=(
            "Share of all finite tested parameter combinations whose "
            "selected objective finishes within 5% of the best value."
        ),
    )

    robustness_column_3.metric(
        "Nearby points within 5%",
        f"{robustness.local_near_optimal_5_share:.1%}",
        help=(
            "Share of combinations in the immediate tested-grid "
            "neighborhood of the optimum that remain within 5% of it."
        ),
    )

    median_local_degradation_text = (
        "N/A"
        if np.isnan(
            robustness.local_median_relative_degradation
        )
        else (
            f"{robustness.local_median_relative_degradation:.1%}"
        )
    )

    robustness_column_4.metric(
        "Median nearby degradation",
        median_local_degradation_text,
        help=(
            "Median relative loss in the selected objective among the "
            "immediate neighboring parameter combinations. Smaller is "
            "more reassuring."
        ),
    )

    st.caption(
        f"Parameter-selection risk: **{robustness.selection_risk_label}** · "
        f"{robustness.near_optimal_5_count:,} of "
        f"{robustness.evaluated_combinations:,} combinations are within "
        "5% of the optimum · "
        f"{robustness.near_optimal_10_count:,} are within 10%."
    )

    robust_candidate_differs = (
        robustness.robust_candidate_parameters
        != result.best_parameters
    )

    with st.expander(
        "Stability-oriented robust candidate",
        expanded=robust_candidate_differs,
    ):
        robust_parameter_text = _format_parameter_set(
            strategy_name=result_strategy_name,
            parameters=robustness.robust_candidate_parameters,
        )

        st.write(robust_parameter_text)

        robust_columns = st.columns(3)
        robust_columns[0].metric(
            "Candidate objective",
            _format_objective_value(
                result_objective,
                robustness.robust_candidate_objective,
            ),
        )
        robust_columns[1].metric(
            "Gap from raw optimum",
            f"{robustness.robust_candidate_relative_gap:.1%}",
        )
        robust_columns[2].metric(
            "Local median objective",
            _format_objective_value(
                result_objective,
                robustness.robust_candidate_local_median_objective,
            ),
        )

        if robust_candidate_differs:
            st.info(
                "This candidate is not the single best historical point. "
                "It is selected from configurations within 10% of the raw "
                "optimum and favors the strongest median performance across "
                "its immediate tested-grid neighborhood. It is therefore a "
                "stability-oriented alternative, not an out-of-sample "
                "recommendation."
            )
        else:
            st.success(
                "The raw optimum is also the strongest stability-oriented "
                "candidate within the tested near-optimal region."
            )

    if robustness.robustness_label == "Broad plateau":
        st.success(
            "The optimum sits inside a comparatively broad region of "
            "similar in-sample performance. This is more reassuring than "
            "an isolated peak, although it is not out-of-sample evidence."
        )
    elif robustness.robustness_label == "Moderate plateau":
        st.info(
            "The tested neighborhood shows some parameter stability, but "
            "performance is not uniformly close to the optimum. Treat the "
            "optimized values as exploratory rather than uniquely correct."
        )
    elif robustness.robustness_label == "Narrow peak":
        st.warning(
            "The best configuration forms a relatively narrow performance peak within the "
            "tested grid. Small parameter changes degrade the selected "
            "objective noticeably, which increases parameter-selection "
            "risk and makes out-of-sample validation especially important."
        )
    else:
        st.info(
            "There are too few finite or neighboring combinations to make "
            "a useful statement about the width of the optimum."
        )

    if robustness.boundary_parameters:
        boundary_text = _format_parameter_set(
            strategy_name=result_strategy_name,
            parameters={
                parameter_name: result.best_parameters[parameter_name]
                for parameter_name in robustness.boundary_parameters
            },
        )

        st.warning(
            "At least one optimized parameter lies on the edge of the "
            "tested grid: "
            f"{boundary_text}. A boundary optimum can mean the search "
            "range has not fully bracketed the preferred region."
        )

    with st.expander("How these robustness diagnostics are calculated"):
        st.markdown(
            "- **Within 5% / 10% of optimum:** counts parameter sets whose "
            "objective is no more than that relative amount worse than the "
            "best tested value.\n"
            "- **Nearby points:** combinations at the optimum or one tested "
            "grid step away in every parameter. Irregular grids use value "
            "order rather than assuming equal numeric spacing.\n"
            "- **Median nearby degradation:** the median relative objective "
            "loss across that local neighborhood.\n"
            "- **Broad plateau / moderate plateau / narrow peak:** transparent "
            "heuristic labels based on the local near-optimal share, the "
            "overall 10% near-optimal share, and median local degradation.\n"
            "- **Robust candidate:** among parameter sets within 10% of the raw "
            "optimum, the candidate whose immediate tested-grid neighborhood "
            "has the strongest median objective. This favors local stability "
            "over an isolated best point. These are descriptive in-sample "
            "diagnostics, not statistical proof that a strategy is or is not "
            "overfit."
        )

    st.subheader("Initial interpretation")

    near_optimal_count, evaluated_count = (
        _calculate_near_optimal_count(result)
    )

    observations: list[str] = []

    if abs(absolute_gain) <= 1e-12:
        observations.append(
            "The predefined default parameters already achieve the "
            "best value of the selected objective within this grid."
        )
    elif absolute_gain > 0:
        observations.append(
            "The optimized configuration improves the selected "
            "in-sample objective relative to the default parameters."
        )

    if evaluated_count > 0:
        near_optimal_share = (
            near_optimal_count / evaluated_count
        )

        observations.append(
            f"{near_optimal_count} of {evaluated_count} evaluated "
            f"parameter combinations ({near_optimal_share:.1%}) "
            "finish within 5% of the best objective value. A broader "
            "near-optimal region generally provides more reassurance "
            "than a single isolated optimum."
        )

    if context.get("search_mode") == "Coarse-to-Fine":
        broad_best_metrics = context.get(
            "broad_best_metrics",
            {},
        )
        broad_objective_value = float(
            broad_best_metrics[result_objective]
        )
        refinement_gain = calculate_optimization_gain(
            optimized_value=optimized_objective_value,
            default_value=broad_objective_value,
            objective=result_objective,
        )

        if refinement_gain > 1e-12:
            observations.append(
                "The local refinement stage improved on the broad-stage "
                "optimum, indicating that the denser neighborhood search "
                "found a better in-sample configuration."
            )
        else:
            observations.append(
                "The local refinement stage did not improve on the "
                "broad-stage optimum. The broad grid had already located "
                "the best tested point within the refined neighborhood."
            )

    observations.append(
        "These results are in-sample. Parameter optimization can "
        "overfit historical data, so the selected configuration "
        "should be evaluated on unseen data before it is treated as "
        "evidence of a robust strategy."
    )

    for observation in observations:
        st.markdown(f"- {observation}")