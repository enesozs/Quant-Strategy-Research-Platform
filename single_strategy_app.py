from datetime import date
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from backtester import (
    build_backtest,
    prepare_market_data,
    run_strategy_on_data,
)
from metrics import calculate_performance_metrics
from optimization import (
    OptimizationObjective,
    OptimizationResults,
    calculate_optimization_robustness,
    optimize_strategy,
)
from strategies import (
    STRATEGY_METADATA,
    get_default_parameters,
    get_optimization_grid,
)

STRATEGY_OPTIONS = {
    metadata["display_name"]: strategy_key
    for strategy_key, metadata
    in STRATEGY_METADATA.items()
}


@st.cache_data
def run_cached_backtest(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    strategy_parameters: dict[str, Any],
    initial_capital: float,
    transaction_cost_bps: float,
):
    """
    Run and cache a single-strategy backtest.
    """
    return build_backtest(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy_name,
        strategy_parameters=strategy_parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )


OBJECTIVE_OPTIONS: dict[str, OptimizationObjective] = {
    "Sharpe Ratio": "sharpe_ratio",
    "Total Return": "total_return",
    "CAGR": "cagr",
    "Annualized Volatility": "annualized_volatility",
    "Maximum Drawdown": "max_drawdown",
}


@st.cache_data
def run_cached_optimized_backtest(
    ticker: str,
    start_date: str,
    end_date: str,
    strategy_name: str,
    objective: OptimizationObjective,
    initial_capital: float,
    transaction_cost_bps: float,
    risk_free_rate: float,
) -> tuple[OptimizationResults, Any]:
    """
    Optimize one strategy on its predefined research grid and then
    backtest the best in-sample parameter set on the same market data.

    This deliberately uses the predefined Optimization Lab grid rather
    than silently launching a custom or coarse-to-fine search. The result
    is therefore reproducible and bounded, but it remains in-sample and
    may be overfit to the selected ticker and period.
    """
    market_data = prepare_market_data(
        ticker=ticker,
        start_date=start_date,
        end_date=end_date,
    )

    optimization_result = optimize_strategy(
        data=market_data,
        strategy_name=strategy_name,
        parameter_grid=get_optimization_grid(strategy_name),
        objective=objective,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
        risk_free_rate=risk_free_rate,
    )

    results = run_strategy_on_data(
        data=market_data,
        strategy_name=strategy_name,
        strategy_parameters=optimization_result.best_parameters,
        initial_capital=initial_capital,
        transaction_cost_bps=transaction_cost_bps,
    )

    return optimization_result, results


def render_strategy_parameters(
    strategy_name: str,
) -> dict[str, Any]:
    """
    Render Streamlit inputs from strategy metadata.
    """
    parameter_specs = STRATEGY_METADATA[
        strategy_name
    ]["parameters"]

    parameter_values: dict[str, Any] = {}

    for parameter_name, specification in parameter_specs.items():
        widget_key = (
            f"single_{strategy_name}_{parameter_name}"
        )

        if specification["type"] == "int":
            value = st.number_input(
                specification["label"],
                min_value=int(specification["min"]),
                max_value=int(specification["max"]),
                value=int(specification["default"]),
                step=int(specification["step"]),
                key=widget_key,
            )

            parameter_values[parameter_name] = int(value)

        else:
            display_as_percent = (
                specification.get("format") == "percent"
            )

            default_value = float(
                specification["default"]
            )
            minimum_value = float(
                specification["min"]
            )
            maximum_value = float(
                specification["max"]
            )
            step_value = float(
                specification["step"]
            )

            if display_as_percent:
                value = st.number_input(
                    f"{specification['label']} (%)",
                    min_value=minimum_value * 100,
                    max_value=maximum_value * 100,
                    value=default_value * 100,
                    step=step_value * 100,
                    key=widget_key,
                )

                parameter_values[parameter_name] = (
                    float(value) / 100
                )

            else:
                value = st.number_input(
                    specification["label"],
                    min_value=minimum_value,
                    max_value=maximum_value,
                    value=default_value,
                    step=step_value,
                    key=widget_key,
                )

                parameter_values[parameter_name] = float(value)

    return parameter_values


def build_indicator_figure(
    results,
    strategy_name: str,
    strategy_parameters: dict[str, Any],
) -> go.Figure | None:
    """
    Build a strategy-specific indicator chart.

    Returns None when the strategy's indicators are already
    adequately represented on the price chart.
    """
    figure = go.Figure()

    if strategy_name == "rsi":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["rsi"],
                name="RSI",
            )
        )

        figure.add_hline(
            y=float(strategy_parameters["entry_threshold"]),
            line_dash="dash",
            annotation_text="Entry level",
        )

        figure.add_hline(
            y=float(strategy_parameters["exit_threshold"]),
            line_dash="dash",
            annotation_text="Exit level",
        )

        figure.update_layout(
            title="Relative Strength Index",
            yaxis_title="RSI",
        )

        figure.update_yaxes(
            range=[0, 100],
        )

    elif strategy_name == "stochastic":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["stochastic_k"],
                name="Stochastic %K",
            )
        )

        figure.add_hline(
            y=float(strategy_parameters["entry_threshold"]),
            line_dash="dash",
            annotation_text="Entry level",
        )

        figure.add_hline(
            y=float(strategy_parameters["exit_threshold"]),
            line_dash="dash",
            annotation_text="Exit level",
        )

        figure.update_layout(
            title="Stochastic Oscillator",
            yaxis_title="%K",
        )

        figure.update_yaxes(
            range=[0, 100],
        )

    elif strategy_name == "macd":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["macd"],
                name="MACD",
            )
        )

        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["macd_signal_line"],
                name="Signal line",
            )
        )

        figure.add_trace(
            go.Bar(
                x=results.index,
                y=results["macd_histogram"],
                name="Histogram",
            )
        )

        figure.update_layout(
            title="MACD",
            yaxis_title="MACD value",
        )

    elif strategy_name == "momentum":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["momentum_return"],
                name="Lookback return",
            )
        )

        figure.add_hline(
            y=float(strategy_parameters["threshold"]),
            line_dash="dash",
            annotation_text="Momentum threshold",
        )

        figure.update_layout(
            title="Price Momentum",
            yaxis_title="Lookback return",
            yaxis_tickformat=".0%",
        )

    elif strategy_name == "atr_breakout":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["atr"],
                name="Average true range",
            )
        )

        figure.update_layout(
            title="Average True Range",
            yaxis_title="ATR",
        )

    elif strategy_name == "adx":
        figure.add_trace(
            go.Scatter(x=results.index, y=results["adx"], name="ADX")
        )
        figure.add_trace(
            go.Scatter(x=results.index, y=results["plus_di"], name="+DI")
        )
        figure.add_trace(
            go.Scatter(x=results.index, y=results["minus_di"], name="-DI")
        )
        figure.add_hline(
            y=float(strategy_parameters["adx_threshold"]),
            line_dash="dash",
            annotation_text="ADX threshold",
        )
        figure.update_layout(
            title="Average Directional Index",
            yaxis_title="Indicator value",
        )

    elif strategy_name == "cci":
        figure.add_trace(
            go.Scatter(x=results.index, y=results["cci"], name="CCI")
        )
        figure.add_hline(
            y=float(strategy_parameters["entry_threshold"]),
            line_dash="dash",
            annotation_text="Entry threshold",
        )
        figure.add_hline(
            y=float(strategy_parameters["exit_threshold"]),
            line_dash="dash",
            annotation_text="Exit threshold",
        )
        figure.update_layout(
            title="Commodity Channel Index",
            yaxis_title="CCI",
        )

    elif strategy_name == "regime_filtered_trend":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["realized_volatility"],
                name="Realized volatility",
            )
        )

        figure.add_hline(
            y=float(strategy_parameters["maximum_volatility"]),
            line_dash="dash",
            annotation_text="Volatility ceiling",
        )

        figure.update_layout(
            title="Annualized Realized Volatility",
            yaxis_title="Volatility",
            yaxis_tickformat=".0%",
        )

    elif strategy_name == "volatility_targeted_momentum":
        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["position"],
                name="Realized portfolio exposure",
            )
        )

        figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["target_position"],
                name="Target exposure",
                line={"dash": "dot"},
            )
        )

        figure.update_layout(
            title="Volatility-Targeted Exposure",
            yaxis_title="Exposure",
        )

    else:
        return None

    figure.update_layout(
        xaxis_title="Date",
        hovermode="x unified",
    )

    return figure


def render_single_strategy_page() -> None:
    st.title("Single-Strategy Backtester")

    st.write(
        "Configure and test one systematic trading strategy "
        "against a buy-and-hold benchmark."
    )

    with st.sidebar:
        st.header("Backtest settings")

        ticker = (
            st.text_input(
                "Ticker",
                value="AAPL",
                key="single_ticker",
            )
            .upper()
            .strip()
        )

        start_date = st.date_input(
            "Start date",
            value=date(2020, 1, 1),
            key="single_start_date",
        )

        end_date = st.date_input(
            "End date",
            value=date(2026, 1, 1),
            key="single_end_date",
        )

        selected_strategy = st.selectbox(
            "Strategy",
            options=list(STRATEGY_OPTIONS),
            key="single_strategy",
        )

        strategy_name = STRATEGY_OPTIONS[selected_strategy]

        use_optimized_parameters = st.checkbox(
            "Use optimized parameters (may cause overfitting)",
            value=False,
            key="single_use_optimized_parameters",
            help=(
                "When enabled, the app searches this strategy's predefined "
                "Optimization Lab grid on the selected ticker and date range, "
                "then runs the backtest with the best in-sample parameters. "
                "Use Optimization Lab to inspect whether the optimum is robust "
                "rather than an isolated historical result."
            ),
        )

        optimization_objective: OptimizationObjective = "sharpe_ratio"

        if use_optimized_parameters:
            selected_objective = st.selectbox(
                "Optimization objective",
                options=list(OBJECTIVE_OPTIONS),
                index=0,
                key="single_optimization_objective",
            )

            optimization_objective = OBJECTIVE_OPTIONS[
                selected_objective
            ]

            optimization_grid = get_optimization_grid(
                strategy_name
            )

            raw_combinations = 1
            for values in optimization_grid.values():
                raw_combinations *= len(values)

            st.warning(
                "This is an in-sample optimization. The selected parameters "
                "are chosen using the same historical period shown in the "
                "backtest, so the result may overstate future performance."
            )

            st.caption(
                f"The predefined Optimization Lab grid contains "
                f"{raw_combinations:,} raw combinations before structural "
                "validation. Use Optimization Lab for custom/coarse-to-fine "
                "searches and robustness inspection."
            )

        st.subheader("Strategy parameters")

        strategy_metadata = STRATEGY_METADATA[
            strategy_name
        ]

        st.caption(
            strategy_metadata["description"]
        )

        with st.expander("Strategy thesis"):
            st.write(strategy_metadata["thesis"])

        if use_optimized_parameters:
            strategy_parameters = get_default_parameters(
                strategy_name
            )

            st.caption(
                "Manual parameter inputs are hidden because the parameter "
                "set will be selected by the optimizer when you run the "
                "backtest."
            )
        else:
            strategy_parameters = render_strategy_parameters(
                strategy_name
            )

        st.subheader("Portfolio assumptions")

        initial_capital = st.number_input(
            "Initial capital",
            min_value=100.0,
            value=10_000.0,
            step=1_000.0,
            key="single_initial_capital",
        )

        transaction_cost_bps = st.number_input(
            "One-way transaction cost (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="single_transaction_cost",
        )

        risk_free_rate_percent = st.number_input(
            "Annual risk-free rate (%)",
            min_value=0.0,
            value=0.0,
            step=0.25,
            key="single_risk_free_rate",
        )

        run_button = st.button(
            "Run backtest",
            type="primary",
            use_container_width=True,
            key="single_run",
        )


    if not run_button:
        st.info("Choose the settings and click **Run backtest**.")
        st.stop()

    if not ticker:
        st.error("Enter a ticker symbol.")
        st.stop()

    if start_date >= end_date:
        st.error("The start date must be earlier than the end date.")
        st.stop()

    if (
        strategy_name == "moving_average"
        and strategy_parameters["fast_window"]
        >= strategy_parameters["slow_window"]
    ):
        st.error(
            "The fast moving-average window must be smaller "
            "than the slow window."
        )
        st.stop()

    if (
        strategy_name == "ema"
        and strategy_parameters["fast_window"]
        >= strategy_parameters["slow_window"]
    ):
        st.error(
            "The fast EMA window must be smaller "
            "than the slow EMA window."
        )
        st.stop()

    if (
        strategy_name == "rsi"
        and strategy_parameters["entry_threshold"]
        >= strategy_parameters["exit_threshold"]
    ):
        st.error(
            "The RSI entry threshold must be smaller "
            "than the exit threshold."
        )
        st.stop()

    if (
        strategy_name == "macd"
        and strategy_parameters["fast_window"]
        >= strategy_parameters["slow_window"]
    ):
        st.error(
            "The fast MACD window must be smaller "
            "than the slow MACD window."
        )
        st.stop()

    if (
        strategy_name == "stochastic"
        and strategy_parameters["entry_threshold"]
        >= strategy_parameters["exit_threshold"]
    ):
        st.error(
            "The stochastic entry threshold must be smaller "
            "than the exit threshold."
        )
        st.stop()

    if (
        strategy_name == "cci"
        and strategy_parameters["entry_threshold"]
        >= strategy_parameters["exit_threshold"]
    ):
        st.error(
            "The CCI entry threshold must be smaller "
            "than the exit threshold."
        )
        st.stop()

    optimization_result: OptimizationResults | None = None

    try:
        if use_optimized_parameters:
            with st.spinner(
                "Optimizing parameters and running backtest..."
            ):
                optimization_result, results = (
                    run_cached_optimized_backtest(
                        ticker=ticker,
                        start_date=start_date.isoformat(),
                        end_date=end_date.isoformat(),
                        strategy_name=strategy_name,
                        objective=optimization_objective,
                        initial_capital=float(initial_capital),
                        transaction_cost_bps=float(
                            transaction_cost_bps
                        ),
                        risk_free_rate=(
                            float(risk_free_rate_percent) / 100
                        ),
                    )
                )

                strategy_parameters = dict(
                    optimization_result.best_parameters
                )
        else:
            with st.spinner("Running backtest..."):
                results = run_cached_backtest(
                    ticker=ticker,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    strategy_name=strategy_name,
                    strategy_parameters=strategy_parameters,
                    initial_capital=float(initial_capital),
                    transaction_cost_bps=float(
                        transaction_cost_bps
                    ),
                )
    except Exception as error:
        st.error(f"Backtest failed: {error}")
        st.stop()

    strategy_metrics = calculate_performance_metrics(
        returns=results["strategy_return"],
        equity=results["strategy_equity"],
        risk_free_rate=(
            float(risk_free_rate_percent) / 100
        ),
        initial_value=float(initial_capital),
    )

    benchmark_metrics = calculate_performance_metrics(
        returns=results["buy_hold_return"],
        equity=results["buy_hold_equity"],
        risk_free_rate=(
            float(risk_free_rate_percent) / 100
        ),
        initial_value=float(initial_capital),
    )

    position_changes = (
        results["position"]
        .diff()
        .abs()
        .fillna(results["position"].abs())
    )
    number_of_position_changes = int((position_changes > 0).sum())
    total_turnover = float(position_changes.sum())
    average_exposure = float(
        results["position"].astype(float).mean()
    )
    final_strategy_value = results["strategy_equity"].iloc[-1]
    final_benchmark_value = results["buy_hold_equity"].iloc[-1]

    st.subheader("Strategy results")

    if optimization_result is not None:
        objective_label = next(
            label
            for label, objective_value in OBJECTIVE_OPTIONS.items()
            if objective_value == optimization_result.objective
        )

        st.warning(
            "These strategy results use parameters optimized in-sample on "
            "the same ticker and historical period. Treat the improvement "
            "as exploratory rather than validated out-of-sample evidence."
        )

        with st.expander(
            "Optimized parameters used",
            expanded=True,
        ):
            st.write(
                f"**Objective:** {objective_label}"
            )

            parameter_text = " | ".join(
                f"{STRATEGY_METADATA[strategy_name]['parameters'][name]['label']}: "
                f"{value}"
                for name, value in strategy_parameters.items()
            )

            st.write(parameter_text)

            default_objective_value = (
                optimization_result.default_metrics[
                    optimization_result.objective
                ]
            )
            optimized_objective_value = (
                optimization_result.best_metrics[
                    optimization_result.objective
                ]
            )

            st.caption(
                f"Default objective value: "
                f"{default_objective_value:.4f} | "
                f"Optimized objective value: "
                f"{optimized_objective_value:.4f}. "
                "Use Optimization Lab to inspect the surrounding parameter "
                "surface before interpreting this as a robust improvement."
            )

            robustness = calculate_optimization_robustness(
                optimization_result
            )

            st.write(
                f"**Parameter robustness:** "
                f"{robustness.robustness_label} "
                f"(selection risk: {robustness.selection_risk_label})"
            )

            robust_parameter_text = " | ".join(
                f"{STRATEGY_METADATA[strategy_name]['parameters'][name]['label']}: "
                f"{value}"
                for name, value in (
                    robustness.robust_candidate_parameters.items()
                )
            )

            if (
                robustness.robust_candidate_parameters
                != optimization_result.best_parameters
            ):
                st.info(
                    "A stability-oriented candidate also exists within 10% "
                    "of the raw optimum. It favors stronger median performance "
                    "across its immediate tested-grid neighborhood:\n\n"
                    f"{robust_parameter_text}\n\n"
                    f"Objective gap from raw optimum: "
                    f"{robustness.robust_candidate_relative_gap:.1%}. "
                    "The backtest above still uses the mathematical optimum; "
                    "this candidate is shown as a robustness diagnostic, not "
                    "as an automatic replacement."
                )
            else:
                st.success(
                    "The mathematical optimum is also the strongest "
                    "stability-oriented candidate in the tested near-optimal "
                    "region."
                )

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "Final strategy value",
        f"${final_strategy_value:,.2f}",
    )

    column_2.metric(
        "Total return",
        f"{strategy_metrics['total_return']:.2%}",
    )

    column_3.metric(
        "Sharpe ratio",
        f"{strategy_metrics['sharpe_ratio']:.2f}",
    )

    column_4.metric(
        "Rebalancing days",
        f"{number_of_position_changes}",
    )

    column_1, column_2, column_3, column_4 = st.columns(4)

    column_1.metric(
        "CAGR",
        f"{strategy_metrics['cagr']:.2%}",
    )

    column_2.metric(
        "Annualized volatility",
        f"{strategy_metrics['annualized_volatility']:.2%}",
    )

    column_3.metric(
        "Maximum drawdown",
        f"{strategy_metrics['max_drawdown']:.2%}",
    )

    column_4.metric(
        "Buy-and-hold value",
        f"${final_benchmark_value:,.2f}",
    )

    exposure_column, _ = st.columns([1, 3])

    exposure_column.metric(
        "Average market exposure",
        f"{average_exposure:.1%}",
        help=(
            "Average fraction of portfolio capital exposed to the asset "
            "across the backtest. Buy and Hold is approximately 100% exposed."
        ),
    )

    st.caption(
        f"Cumulative one-way turnover: {total_turnover:.2f}× "
        "over the selected period."
    )

    price_figure = go.Figure()

    price_figure.add_trace(
        go.Scatter(
            x=results.index,
            y=results["Close"],
            name="Adjusted close",
        )
    )

    if strategy_name == "moving_average":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["fast_ma"],
                name="Fast moving average",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["slow_ma"],
                name="Slow moving average",
            )
        )

    elif strategy_name == "ema":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["fast_ema"],
                name="Fast EMA",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["slow_ema"],
                name="Slow EMA",
            )
        )

    elif strategy_name == "bollinger":
        for column, label in [
            ("bollinger_upper", "Upper band"),
            ("bollinger_middle", "Middle band"),
            ("bollinger_lower", "Lower band"),
        ]:
            price_figure.add_trace(
                go.Scatter(
                    x=results.index,
                    y=results[column],
                    name=label,
                )
            )

    elif strategy_name == "donchian":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["donchian_entry_high"],
                name="Entry channel",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["donchian_exit_low"],
                name="Exit channel",
            )
        )

    elif strategy_name == "atr_breakout":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["atr_trend_mean"],
                name="Trend mean",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["atr_entry_level"],
                name="ATR entry level",
            )
        )
    elif strategy_name == "adx":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["adx_trend_average"],
                name="Trend average",
            )
        )

    elif strategy_name == "keltner":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["keltner_upper"],
                name="Upper Keltner channel",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["keltner_middle"],
                name="Middle Keltner channel",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["keltner_lower"],
                name="Lower Keltner channel",
            )
        )

    elif strategy_name == "regime_filtered_trend":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["regime_trend_average"],
                name="Trend average",
            )
        )

    elif strategy_name == "multi_timeframe_trend":
        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["daily_trend_average"],
                name="Daily trend average",
            )
        )

        price_figure.add_trace(
            go.Scatter(
                x=results.index,
                y=results["weekly_trend_average"],
                name="Weekly trend average",
            )
        )

    previous_position = results["position"].shift(1).fillna(0.0)
    entries = results[(results["position"] > 0) & (previous_position == 0)]
    exits = results[(results["position"] == 0) & (previous_position > 0)]

    price_figure.add_trace(
        go.Scatter(
            x=entries.index,
            y=entries["Close"],
            mode="markers",
            marker={
                "symbol": "triangle-up",
                "size": 11,
            },
            name="Buy",
        )
    )

    price_figure.add_trace(
        go.Scatter(
            x=exits.index,
            y=exits["Close"],
            mode="markers",
            marker={
                "symbol": "triangle-down",
                "size": 11,
            },
            name="Sell",
        )
    )

    price_figure.update_layout(
        title=f"{ticker} price and strategy trades",
        xaxis_title="Date",
        yaxis_title="Price",
        hovermode="x unified",
    )

    st.plotly_chart(
        price_figure,
        use_container_width=True,
    )

    equity_figure = go.Figure()

    indicator_figure = build_indicator_figure(
        results=results,
        strategy_name=strategy_name,
        strategy_parameters=strategy_parameters,
    )

    if indicator_figure is not None:
        st.plotly_chart(
            indicator_figure,
            use_container_width=True,
        )

    equity_figure.add_trace(
        go.Scatter(
            x=results.index,
            y=results["strategy_equity"],
            name="Strategy",
        )
    )

    equity_figure.add_trace(
        go.Scatter(
            x=results.index,
            y=results["buy_hold_equity"],
            name="Buy and hold",
        )
    )

    equity_figure.update_layout(
        title="Portfolio value",
        xaxis_title="Date",
        yaxis_title="Portfolio value",
        hovermode="x unified",
    )

    st.plotly_chart(
        equity_figure,
        use_container_width=True,
    )


    drawdown_figure = go.Figure()

    drawdown_figure.add_trace(
        go.Scatter(
            x=results.index,
            y=results["strategy_drawdown"],
            name="Strategy",
        )
    )

    drawdown_figure.add_trace(
        go.Scatter(
            x=results.index,
            y=results["buy_hold_drawdown"],
            name="Buy and hold",
        )
    )

    drawdown_figure.update_layout(
        title="Drawdowns",
        xaxis_title="Date",
        yaxis_title="Drawdown",
        yaxis_tickformat=".0%",
        hovermode="x unified",
    )

    st.plotly_chart(
        drawdown_figure,
        use_container_width=True,
    )

    comparison_data = {
        "Metric": [
            "Total return",
            "CAGR",
            "Annualized volatility",
            "Sharpe ratio",
            "Maximum drawdown",
        ],
        "Strategy": [
            f"{strategy_metrics['total_return']:.2%}",
            f"{strategy_metrics['cagr']:.2%}",
            f"{strategy_metrics['annualized_volatility']:.2%}",
            f"{strategy_metrics['sharpe_ratio']:.2f}",
            f"{strategy_metrics['max_drawdown']:.2%}",
        ],
        "Buy and hold": [
            f"{benchmark_metrics['total_return']:.2%}",
            f"{benchmark_metrics['cagr']:.2%}",
            f"{benchmark_metrics['annualized_volatility']:.2%}",
            f"{benchmark_metrics['sharpe_ratio']:.2f}",
            f"{benchmark_metrics['max_drawdown']:.2%}",
        ],
    }

    st.subheader("Performance comparison")
    st.dataframe(
        comparison_data,
        use_container_width=True,
        hide_index=True,
    )