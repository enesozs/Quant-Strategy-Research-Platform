from datetime import date

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from comparison import (
    calculate_optimized_comparison_workload,
    compare_all_strategies,
    get_comparison_leaders,
)
from optimization import OptimizationObjective


OBJECTIVE_OPTIONS: dict[str, OptimizationObjective] = {
    "Sharpe Ratio": "sharpe_ratio",
    "Total Return": "total_return",
    "CAGR": "cagr",
    "Annualized Volatility": "annualized_volatility",
    "Maximum Drawdown": "max_drawdown",
}

OPTIMIZED_COMPARISON_INFO_LIMIT = 2_500
OPTIMIZED_COMPARISON_WARNING_LIMIT = 5_000
OPTIMIZED_COMPARISON_HARD_LIMIT = 10_000


def _render_optimization_workload_notice(
    raw_combinations: int,
) -> None:
    """Explain the aggregate predefined-grid workload before execution."""
    message = (
        f"The optimized comparison will consider up to "
        f"{raw_combinations:,} raw parameter combinations across "
        "all registered strategies before structural validation. "
        "The actual number evaluated may be smaller."
    )

    if raw_combinations <= OPTIMIZED_COMPARISON_INFO_LIMIT:
        st.caption(message + " This is a relatively light search.")
    elif raw_combinations <= OPTIMIZED_COMPARISON_WARNING_LIMIT:
        st.info(message + " This is a moderately sized search.")
    elif raw_combinations <= OPTIMIZED_COMPARISON_HARD_LIMIT:
        st.warning(
            message
            + " This is a heavy interactive search and may take "
            "noticeably longer than the default comparison."
        )
    else:
        st.error(
            message
            + f" The {OPTIMIZED_COMPARISON_HARD_LIMIT:,}-combination "
            "interactive safety limit is exceeded, so optimized comparison "
            "is disabled for this workload."
        )


@st.cache_data
def run_cached_comparison(
    ticker: str,
    start_date: str,
    end_date: str,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
    use_optimized_parameters: bool,
    optimization_objective: OptimizationObjective,
):
    """
    Run and cache a full strategy comparison.
    """
    return compare_all_strategies(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
        use_optimized_parameters=use_optimized_parameters,
        optimization_objective=optimization_objective,
    )


def render_comparison_page() -> None:
    st.title("Compare All Strategies")

    st.write(
        "Compare all registered strategies using the same ticker, "
        "historical period, capital, transaction costs, and "
        "performance assumptions."
    )

    with st.sidebar:
        st.header("Comparison settings")

        ticker = (
            st.text_input(
                "Ticker",
                value="AAPL",
                key="comparison_ticker",
            )
            .upper()
            .strip()
        )

        start_date = st.date_input(
            "Start date",
            value=date(2020, 1, 1),
            key="comparison_start_date",
        )

        end_date = st.date_input(
            "End date",
            value=date(2026, 1, 1),
            key="comparison_end_date",
        )

        initial_capital = st.number_input(
            "Initial capital",
            min_value=100.0,
            value=10_000.0,
            step=1_000.0,
            key="comparison_initial_capital",
        )

        transaction_cost_bps = st.number_input(
            "One-way transaction cost (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="comparison_transaction_cost",
        )

        risk_free_rate_percent = st.number_input(
            "Annual risk-free rate (%)",
            min_value=0.0,
            value=0.0,
            step=0.25,
            key="comparison_risk_free_rate",
        )

        use_optimized_parameters = st.checkbox(
            "Use optimized parameters (may cause overfitting)",
            value=False,
            key="comparison_use_optimized_parameters",
            help=(
                "Independently optimize every strategy on its predefined "
                "Optimization Lab grid using the same historical period. "
                "This is in-sample parameter selection and can materially "
                "increase overfitting and selection bias."
            ),
        )

        optimization_objective: OptimizationObjective = "sharpe_ratio"
        raw_optimization_combinations = 0

        if use_optimized_parameters:
            selected_objective_label = st.selectbox(
                "Optimization objective",
                options=list(OBJECTIVE_OPTIONS),
                index=0,
                key="comparison_optimization_objective",
            )

            optimization_objective = OBJECTIVE_OPTIONS[
                selected_objective_label
            ]

            (
                raw_optimization_combinations,
                strategy_grid_sizes,
            ) = calculate_optimized_comparison_workload()

            _render_optimization_workload_notice(
                raw_optimization_combinations
            )

            with st.expander(
                "Optimization workload by strategy",
                expanded=False,
            ):
                workload_rows = []

                for strategy_key, combination_count in (
                    strategy_grid_sizes.items()
                ):
                    workload_rows.append(
                        {
                            "Strategy key": strategy_key,
                            "Raw combinations": combination_count,
                        }
                    )

                st.dataframe(
                    workload_rows,
                    width="stretch",
                    hide_index=True,
                )

            st.caption(
                "Only predefined research grids are used here. Custom and "
                "Coarse-to-Fine searches remain in Optimization Lab so the "
                "multi-strategy comparison stays bounded and reproducible."
            )

        run_button = st.button(
            "Compare strategies",
            type="primary",
            width="stretch",
            key="comparison_run",
        )

    if run_button:
        if not ticker:
            st.error("Enter a ticker symbol.")
            return

        if start_date >= end_date:
            st.error(
                "The start date must be earlier than the end date."
            )
            return

        if (
            use_optimized_parameters
            and raw_optimization_combinations
            > OPTIMIZED_COMPARISON_HARD_LIMIT
        ):
            st.error(
                "The optimized comparison exceeds the interactive "
                f"safety limit of {OPTIMIZED_COMPARISON_HARD_LIMIT:,} "
                "raw combinations. Use the default comparison or study "
                "individual strategies in Optimization Lab."
            )
            return

        try:
            with st.spinner("Running all strategies..."):
                comparison = run_cached_comparison(
                    ticker=ticker,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    initial_capital=float(initial_capital),
                    transaction_cost_bps=float(
                        transaction_cost_bps
                    ),
                    risk_free_rate=(
                        float(risk_free_rate_percent) / 100
                    ),
                    use_optimized_parameters=(
                        use_optimized_parameters
                    ),
                    optimization_objective=(
                        optimization_objective
                    ),
                )

            st.session_state["comparison_results"] = comparison
            st.session_state["comparison_settings_used"] = {
                "ticker": ticker,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "initial_capital": float(initial_capital),
                "transaction_cost_bps": float(
                    transaction_cost_bps
                ),
                "risk_free_rate_percent": float(
                    risk_free_rate_percent
                ),
                "use_optimized_parameters": (
                    use_optimized_parameters
                ),
                "optimization_objective": (
                    optimization_objective
                ),
            }
            st.session_state[
                "comparison_widget_generation"
            ] = (
                st.session_state.get(
                    "comparison_widget_generation",
                    0,
                )
                + 1
            )
        except Exception as error:
            st.error(f"Strategy comparison failed: {error}")
            return

    if "comparison_results" not in st.session_state:
        st.info(
            "Choose the settings and click "
            "**Compare strategies**."
        )
        return

    comparison = st.session_state["comparison_results"]
    summary = comparison.summary.copy()
    leaders = get_comparison_leaders(summary)

    settings_used = st.session_state.get(
        "comparison_settings_used"
    )

    if settings_used is not None:
        current_settings = {
            "ticker": ticker,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "initial_capital": float(initial_capital),
            "transaction_cost_bps": float(
                transaction_cost_bps
            ),
            "risk_free_rate_percent": float(
                risk_free_rate_percent
            ),
            "use_optimized_parameters": (
                use_optimized_parameters
            ),
            "optimization_objective": optimization_objective,
        }

        if current_settings != settings_used:
            st.warning(
                "The controls have changed since this comparison "
                "was run. Click **Compare strategies** to refresh "
                "the results."
            )

    if comparison.use_optimized_parameters:
        objective_label = next(
            label
            for label, objective_value in OBJECTIVE_OPTIONS.items()
            if objective_value == comparison.optimization_objective
        )

        st.warning(
            "This is an in-sample optimized comparison. Each strategy was "
            f"independently selected for {objective_label} on the same "
            "historical period being reported below. Search-space sizes "
            "differ between strategies, so these rankings are more exposed "
            "to parameter-selection bias than the default comparison."
        )

        optimization_column_1, optimization_column_2 = st.columns(2)

        optimization_column_1.metric(
            "Raw optimization combinations",
            f"{comparison.raw_optimization_combinations:,}",
        )
        optimization_column_2.metric(
            "Valid parameter evaluations",
            f"{comparison.valid_optimization_evaluations:,}",
        )

    st.subheader("Comparison leaders")

    column_1, column_2, column_3 = st.columns(3)

    column_1.metric(
        "Highest return",
        leaders["highest_return"],
    )

    column_2.metric(
        "Best Sharpe ratio",
        leaders["highest_sharpe"],
    )

    column_3.metric(
        "Smallest drawdown",
        leaders["smallest_drawdown"],
    )

    column_1, column_2, column_3 = st.columns(3)

    column_1.metric(
        "Lowest volatility",
        leaders["lowest_volatility"],
    )

    column_2.metric(
        "Highest turnover",
        leaders["highest_turnover"],
    )

    column_3.metric(
        "Lowest turnover",
        leaders["lowest_turnover"],
    )

    st.subheader("Strategy rankings")

    display_columns = [
        "strategy",
        "family",
        "features",
    ]

    if comparison.use_optimized_parameters:
        display_columns.extend(
            [
                "parameters",
                "optimization_evaluations",
                "default_objective",
                "optimized_objective",
                "optimization_gain",
                "optimization_robustness",
                "robust_candidate_parameters",
            ]
        )

    display_columns.extend(
        [
            "final_value",
            "total_return",
            "cagr",
            "annualized_volatility",
            "sharpe_ratio",
            "max_drawdown",
            "trades",
            "turnover",
            "average_exposure",
            "return_rank",
            "sharpe_rank",
            "volatility_rank",
            "drawdown_rank",
        ]
    )

    display_summary = summary[display_columns].copy()

    display_summary = display_summary.rename(
        columns={
            "strategy": "Strategy",
            "family": "Family",
            "features": "Features",
            "parameters": "Optimized Parameters",
            "optimization_evaluations": "Valid Evaluations",
            "default_objective": "Default Objective",
            "optimized_objective": "Optimized Objective",
            "optimization_gain": "Optimization Gain",
            "optimization_robustness": "Optimization Robustness",
            "robust_candidate_parameters": "Robust Candidate",
            "final_value": "Final Value",
            "total_return": "Total Return",
            "cagr": "CAGR",
            "annualized_volatility": "Volatility",
            "sharpe_ratio": "Sharpe Ratio",
            "max_drawdown": "Maximum Drawdown",
            "trades": "Rebalancing Days",
            "turnover": "Cumulative One-Way Turnover",
            "average_exposure": "Average Exposure",
            "return_rank": "Return Rank",
            "sharpe_rank": "Sharpe Rank",
            "volatility_rank": "Volatility Rank",
            "drawdown_rank": "Drawdown Rank",
        }
    )

    display_formatters = {
        "Final Value": "${:,.2f}",
        "Total Return": "{:.2%}",
        "CAGR": "{:.2%}",
        "Volatility": "{:.2%}",
        "Sharpe Ratio": "{:.2f}",
        "Maximum Drawdown": "{:.2%}",
        "Cumulative One-Way Turnover": "{:.2f}×",
        "Average Exposure": "{:.1%}",
    }

    if comparison.use_optimized_parameters:
        display_formatters.update(
            {
                "Default Objective": "{:.4f}",
                "Optimized Objective": "{:.4f}",
                "Optimization Gain": "{:+.4f}",
            }
        )

    st.dataframe(
        display_summary.style.format(display_formatters),
        width="stretch",
        hide_index=True,
    )

    st.subheader("Risk versus return")

    risk_return_figure = px.scatter(
        summary,
        x="annualized_volatility",
        y="cagr",
        size="final_value",
        color="family",
        hover_name="strategy",
        hover_data={
            "annualized_volatility": ":.2%",
            "cagr": ":.2%",
            "sharpe_ratio": ":.2f",
            "max_drawdown": ":.2%",
            "final_value": ":$,.2f",
            "family": True,
        },
        labels={
            "annualized_volatility": "Annualized volatility",
            "cagr": "CAGR",
            "family": "Strategy family",
        },
        title="Annualized Return Versus Volatility",
    )

    risk_return_figure.update_xaxes(
        tickformat=".0%",
    )

    risk_return_figure.update_yaxes(
        tickformat=".0%",
    )

    st.plotly_chart(
        risk_return_figure,
        width="stretch",
    )

    st.subheader("Time-series comparison")

    chart_options = summary["strategy"].tolist()

    default_chart_strategies = list(
        dict.fromkeys(
            [
                "Buy and Hold",
                leaders["highest_sharpe"],
                leaders["highest_return"],
                leaders["smallest_drawdown"],
            ]
        )
    )

    default_chart_strategies = [
        strategy
        for strategy in default_chart_strategies
        if strategy in chart_options
    ]

    active_chart_options = (
        summary.loc[
            summary["family"] != "Benchmark",
            "strategy",
        ]
        .tolist()
    )

    focused_default = leaders["highest_sharpe"]

    if focused_default not in active_chart_options:
        focused_default = active_chart_options[0]

    widget_generation = st.session_state.get(
        "comparison_widget_generation",
        0,
    )

    selected_strategies = st.multiselect(
        "Strategies shown in the equity and drawdown charts",
        options=chart_options,
        default=default_chart_strategies,
        key=(
            "comparison_chart_strategies_"
            f"{widget_generation}"
        ),
    )

    if not selected_strategies:
        st.warning(
            "Select at least one strategy to display the "
            "time-series charts."
        )
    else:
        selected_strategy_names = set(selected_strategies)

        st.subheader("Portfolio value comparison")

        equity_figure = go.Figure()

        for strategy_key, results in (
            comparison.strategy_results.items()
        ):
            strategy_row = summary[
                summary["strategy_key"] == strategy_key
            ].iloc[0]

            strategy_display_name = str(
                strategy_row["strategy"]
            )

            if (
                strategy_display_name
                not in selected_strategy_names
            ):
                continue

            equity_figure.add_trace(
                go.Scatter(
                    x=results.index,
                    y=results["strategy_equity"],
                    mode="lines",
                    name=strategy_display_name,
                )
            )

        first_results = next(
            iter(comparison.strategy_results.values())
        )

        if "Buy and Hold" in selected_strategy_names:
            equity_figure.add_trace(
                go.Scatter(
                    x=first_results.index,
                    y=first_results["buy_hold_equity"],
                    mode="lines",
                    name="Buy and Hold",
                    line={
                        "width": 3,
                        "dash": "dash",
                    },
                )
            )

        equity_figure.update_layout(
            xaxis_title="Date",
            yaxis_title="Portfolio value",
            hovermode="x unified",
            legend_title="Strategy",
        )

        st.plotly_chart(
            equity_figure,
            width="stretch",
        )

        st.subheader("Selected drawdown comparison")

        drawdown_figure = go.Figure()

        for strategy_key, results in (
            comparison.strategy_results.items()
        ):
            strategy_row = summary[
                summary["strategy_key"] == strategy_key
            ].iloc[0]

            strategy_display_name = str(
                strategy_row["strategy"]
            )

            if (
                strategy_display_name
                not in selected_strategy_names
            ):
                continue

            drawdown_figure.add_trace(
                go.Scatter(
                    x=results.index,
                    y=results["strategy_drawdown"],
                    mode="lines",
                    name=strategy_display_name,
                )
            )

        if "Buy and Hold" in selected_strategy_names:
            drawdown_figure.add_trace(
                go.Scatter(
                    x=first_results.index,
                    y=first_results["buy_hold_drawdown"],
                    mode="lines",
                    name="Buy and Hold",
                    line={
                        "width": 3,
                        "dash": "dash",
                    },
                )
            )

        drawdown_figure.update_layout(
            xaxis_title="Date",
            yaxis_title="Drawdown",
            yaxis_tickformat=".0%",
            hovermode="x unified",
            legend_title="Strategy",
        )

        st.plotly_chart(
            drawdown_figure,
            width="stretch",
        )


    st.subheader("Maximum drawdown by strategy")

    drawdown_bar_data = summary.sort_values(
        by="max_drawdown",
        ascending=True,
    ).copy()

    drawdown_bar_figure = px.bar(
        drawdown_bar_data,
        x="max_drawdown",
        y="strategy",
        orientation="h",
        color="family",
        hover_name="strategy",
        hover_data={
            "max_drawdown": ":.2%",
            "sharpe_ratio": ":.2f",
            "total_return": ":.2%",
            "family": True,
        },
        labels={
            "max_drawdown": "Maximum drawdown",
            "strategy": "Strategy",
            "family": "Strategy family",
        },
        title="Worst Peak-to-Trough Decline",
    )

    drawdown_bar_figure.update_xaxes(
        tickformat=".0%",
    )

    drawdown_bar_figure.update_layout(
        yaxis={
            "categoryorder": "total ascending",
        },
    )

    st.plotly_chart(
        drawdown_bar_figure,
        width="stretch",
    )

    st.caption("Comparison view: selected curves, maximum-drawdown ranking, and drawdown deep dive.")

    st.subheader("Drawdown deep dive")

    active_strategy_rows = summary[
        summary["family"] != "Benchmark"
    ].copy()

    active_strategy_names = active_strategy_rows[
        "strategy"
    ].astype(str).tolist()

    focused_strategy_name = st.selectbox(
        "Strategy to inspect",
        options=active_strategy_names,
        index=active_strategy_names.index(focused_default),
        key=(
            "comparison_drawdown_focus_"
            f"{widget_generation}"
        ),
    )

    focused_strategy_key = str(
        active_strategy_rows.loc[
            active_strategy_rows["strategy"].astype(str)
            == focused_strategy_name,
            "strategy_key",
        ].iloc[0]
    )

    focused_results = comparison.strategy_results[
        focused_strategy_key
    ]

    focused_drawdown_figure = go.Figure()

    focused_drawdown_figure.add_trace(
        go.Scatter(
            x=focused_results.index,
            y=focused_results["strategy_drawdown"],
            mode="lines",
            name=focused_strategy_name,
            fill="tozeroy",
        )
    )

    focused_drawdown_figure.add_trace(
        go.Scatter(
            x=focused_results.index,
            y=focused_results["buy_hold_drawdown"],
            mode="lines",
            name="Buy and Hold",
            line={
                "dash": "dash",
                "width": 2,
            },
        )
    )

    focused_drawdown_figure.update_layout(
        title=(
            f"{focused_strategy_name} Drawdown "
            "Versus Buy and Hold"
        ),
        xaxis_title="Date",
        yaxis_title="Drawdown",
        yaxis_tickformat=".0%",
        hovermode="x unified",
        legend_title="Portfolio",
    )

    st.plotly_chart(
        focused_drawdown_figure,
        width="stretch",
    )

    focused_max_drawdown = float(
        focused_results["strategy_drawdown"].min()
    )

    benchmark_max_drawdown = float(
        focused_results["buy_hold_drawdown"].min()
    )

    focused_underwater_days = int(
        (focused_results["strategy_drawdown"] < 0).sum()
    )

    benchmark_underwater_days = int(
        (focused_results["buy_hold_drawdown"] < 0).sum()
    )

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        f"{focused_strategy_name} max drawdown",
        f"{focused_max_drawdown:.2%}",
    )

    column_2.metric(
        "Buy-and-hold max drawdown",
        f"{benchmark_max_drawdown:.2%}",
    )

    column_3.metric(
        f"{focused_strategy_name} underwater days",
        f"{focused_underwater_days:,}",
    )

    column_4.metric(
        "Buy-and-hold underwater days",
        f"{benchmark_underwater_days:,}",
    )

    st.caption(
        "An underwater day is a trading day when the portfolio "
        "remains below its previous historical peak."
    )

    st.subheader("Initial interpretation")

    benchmark_row = summary[
        summary["family"] == "Benchmark"
    ].iloc[0]

    active_strategies = summary[
        summary["family"] != "Benchmark"
    ].copy()

    best_active_return_row = active_strategies.loc[
        active_strategies["total_return"].idxmax()
    ]

    best_active_sharpe_row = active_strategies.loc[
        active_strategies["sharpe_ratio"].idxmax()
    ]

    trend_rows = active_strategies[
        active_strategies["family"] == "Trend Following"
    ]

    mean_reversion_rows = active_strategies[
        active_strategies["family"] == "Mean Reversion"
    ]

    observations: list[str] = []

    if (
        benchmark_row["total_return"]
        > best_active_return_row["total_return"]
    ):
        return_gap = (
            benchmark_row["total_return"]
            - best_active_return_row["total_return"]
        )

        observations.append(
            f"Buy and Hold generated the highest absolute "
            f"return, outperforming the strongest active "
            f"strategy by {return_gap:.2%}. This suggests "
            f"that remaining invested was especially valuable "
            f"over the selected period."
        )

    if (
        best_active_sharpe_row["sharpe_ratio"]
        > benchmark_row["sharpe_ratio"]
    ):
        observations.append(
            f"{best_active_sharpe_row['strategy']} achieved "
            f"a higher Sharpe ratio than Buy and Hold, "
            f"indicating stronger return relative to measured "
            f"volatility."
        )

    if (
        not trend_rows.empty
        and not mean_reversion_rows.empty
    ):
        average_trend_sharpe = trend_rows[
            "sharpe_ratio"
        ].mean()

        average_mean_reversion_sharpe = (
            mean_reversion_rows["sharpe_ratio"].mean()
        )

        if (
            average_trend_sharpe
            > average_mean_reversion_sharpe
        ):
            observations.append(
                "Trend-following strategies produced a higher "
                "average Sharpe ratio than mean-reversion "
                "strategies. The selected ticker therefore "
                "appears to have rewarded persistent directional "
                "movement more than short-term reversal signals."
            )
        else:
            observations.append(
                "Mean-reversion strategies produced a higher "
                "average Sharpe ratio than trend-following "
                "strategies. The selected ticker appears to have "
                "rewarded reversals more than sustained trends."
            )

    turnover_values = active_strategies["turnover"].astype(float)
    highest_turnover_index = turnover_values.idxmax()

    highest_turnover_strategy = str(
        active_strategies.loc[
            highest_turnover_index,
            "strategy",
        ]
    )

    highest_turnover = float(
        turnover_values.loc[highest_turnover_index]
    )

    observations.append(
        f"{highest_turnover_strategy} generated the highest "
        f"cumulative one-way turnover at {highest_turnover:.2f}×, "
        f"making its results especially sensitive to the "
        f"transaction-cost assumption."
    )

    rebalancing_days = active_strategies["trades"].astype(int)
    most_rebalancing_index = rebalancing_days.idxmax()

    most_rebalancing_strategy = str(
        active_strategies.loc[
            most_rebalancing_index,
            "strategy",
        ]
    )

    most_rebalancing_days = int(
        rebalancing_days.loc[most_rebalancing_index]
    )

    if most_rebalancing_strategy != highest_turnover_strategy:
        observations.append(
            f"{most_rebalancing_strategy} changed exposure on "
            f"{most_rebalancing_days} trading days. Frequent "
            f"rebalancing does not necessarily imply the highest "
            f"turnover because individual exposure changes may be small."
        )

    if comparison.use_optimized_parameters:
        observations.append(
            "Every active strategy in this view was optimized independently "
            "on the same in-sample period using its predefined research grid. "
            "Differences in grid size give strategies unequal numbers of "
            "parameter opportunities, so optimized rankings should be treated "
            "as exploratory until they are checked out of sample."
        )

    for observation in observations:
        st.markdown(f"- {observation}")