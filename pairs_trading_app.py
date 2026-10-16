from __future__ import annotations

from datetime import date
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from pairs_trading_cointegration import (
    build_cointegration_pairs_research,
)
from pairs_trading_core import (
    METHOD_COINTEGRATION,
    METHOD_DISTANCE,
    METHOD_DYNAMIC,
    PairsResearchResult,
    prepare_pair_data,
)
from pairs_trading_discovery import discover_pairs
from pairs_trading_distance import build_distance_pairs_research
from pairs_trading_dynamic import build_dynamic_pairs_research
from pairs_trading_sensitivity import run_parameter_sensitivity




@st.cache_data
def _run_distance(**kwargs: Any) -> PairsResearchResult:
    return build_distance_pairs_research(**kwargs)


@st.cache_data
def _run_cointegration(**kwargs: Any) -> PairsResearchResult:
    return build_cointegration_pairs_research(**kwargs)


@st.cache_data
def _run_dynamic(**kwargs: Any) -> PairsResearchResult:
    return build_dynamic_pairs_research(**kwargs)


@st.cache_data
def _run_discovery(**kwargs: Any) -> pd.DataFrame:
    return discover_pairs(**kwargs)


@st.cache_data
def _load_pair_prices(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    return prepare_pair_data(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        start_date=start_date,
        end_date=end_date,
    )


def _number(value: object, decimals: int = 3) -> str:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(number):
        return "N/A"
    return f"{number:.{decimals}f}"


def _percent(value: object) -> str:
    try:
        number = float(str(value))
    except (TypeError, ValueError):
        return "N/A"
    if not np.isfinite(number):
        return "N/A"
    return f"{number:.2%}"


def _format_display_table(table: pd.DataFrame) -> pd.DataFrame:
    result = table.copy()

    for column in result.columns:
        if "start" in column or "end" in column or column.endswith("_date"):
            try:
                result[column] = pd.to_datetime(result[column]).dt.date
            except (TypeError, ValueError):
                pass

    percent_columns = {
        "test_return",
        "total_return",
        "max_drawdown",
        "long_leg_contribution",
        "short_leg_contribution",
        "gross_pair_return",
        "transaction_cost",
        "net_pair_return",
    }
    for column in percent_columns.intersection(result.columns):
        result[column] = result[column].map(
            lambda value: (
                f"{float(value):+.2%}"
                if pd.notna(value)
                else "N/A"
            )
        )

    # Shares are proportions, not signed returns.
    for column in {"valid_relationship_share", "valid_beta_share"}.intersection(
        result.columns
    ):
        result[column] = result[column].map(_percent)

    # A correlation is a coefficient in [-1, 1], not a percentage.
    if "return_correlation" in result.columns:
        result["return_correlation"] = result["return_correlation"].map(
            lambda value: _number(value, 2)
        )

    return result


def _render_summary(result: PairsResearchResult) -> None:
    data = result.stitched_data
    metrics = result.strategy_metrics
    trades = len(result.trades)

    st.subheader(
        f"{result.ticker_a} / {result.ticker_b} — {result.method_name}"
    )

    columns = st.columns(6)
    columns[0].metric(
        "Final value",
        f"${float(data['strategy_equity'].iloc[-1]):,.2f}",
    )
    columns[1].metric("Total return", _percent(metrics["total_return"]))
    columns[2].metric("Sharpe ratio", _number(metrics["sharpe_ratio"], 2))
    columns[3].metric("Maximum drawdown", _percent(metrics["max_drawdown"]))
    columns[4].metric("Trades", str(trades))
    columns[5].metric(
        "One-way turnover",
        f"{float(data['turnover'].sum()):.2f}×",
    )

    secondary = st.columns(4)
    secondary[0].metric("CAGR", _percent(metrics["cagr"]))
    secondary[1].metric(
        "Annualized volatility",
        _percent(metrics["annualized_volatility"]),
    )
    secondary[2].metric(
        "Return correlation",
        _number(result.full_sample_return_correlation, 3),
    )
    secondary[3].metric(
        "Price correlation",
        _number(result.full_sample_price_correlation, 3),
    )


def _render_diagnostics(result: PairsResearchResult) -> None:
    st.subheader("Method diagnostics")
    st.dataframe(
        _format_display_table(result.diagnostics),
        width="stretch",
        hide_index=True,
    )


def _render_trade_diagnostics(result: PairsResearchResult) -> None:
    st.subheader("Trade-by-trade diagnostics")
    trades = result.trades.copy()

    if trades.empty:
        st.info(
            "No realized trades were generated under the current "
            "relationship and qualification rules."
        )
        return

    winning_share = float((trades["net_pair_return"] > 0).mean())
    average_trade = float(trades["net_pair_return"].mean())
    average_cost = float(trades["transaction_cost"].mean())

    summary = st.columns(3)
    summary[0].metric("Winning trades", f"{winning_share:.1%}")
    summary[1].metric("Average trade return", f"{average_trade:+.2%}")
    summary[2].metric(
        "Average transaction-cost drag",
        f"{average_cost:.3%}",
    )

    st.dataframe(
        _format_display_table(trades),
        width="stretch",
        hide_index=True,
    )


def _render_zscore(
    result: PairsResearchResult,
    entry_zscore: float,
    exit_zscore: float,
    stop_zscore: float,
) -> None:
    data = result.stitched_data
    st.subheader("Spread z-score and trading thresholds")

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=data.index,
            y=data["spread_zscore"],
            mode="lines",
            name="Spread z-score",
        )
    )

    for level, label in [
        (entry_zscore, "Upper entry"),
        (-entry_zscore, "Lower entry"),
        (exit_zscore, "Upper exit"),
        (-exit_zscore, "Lower exit"),
        (stop_zscore, "Upper stop"),
        (-stop_zscore, "Lower stop"),
    ]:
        figure.add_hline(
            y=level,
            line_dash="dash",
            annotation_text=label,
            annotation_position="top left",
        )

    previous = data["pair_signal"].shift(1).fillna(0.0)
    long_entries = data[data["pair_signal"].eq(1) & previous.eq(0)]
    short_entries = data[data["pair_signal"].eq(-1) & previous.eq(0)]
    exits = data[data["pair_signal"].eq(0) & previous.ne(0)]

    figure.add_trace(
        go.Scatter(
            x=long_entries.index,
            y=long_entries["spread_zscore"],
            mode="markers",
            name="Long spread",
            marker_symbol="triangle-up",
            marker_size=9,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=short_entries.index,
            y=short_entries["spread_zscore"],
            mode="markers",
            name="Short spread",
            marker_symbol="triangle-down",
            marker_size=9,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=exits.index,
            y=exits["spread_zscore"],
            mode="markers",
            name="Exit",
            marker_symbol="circle",
            marker_size=7,
        )
    )

    if "relationship_broken" in data.columns:
        broken = data[data["relationship_broken"].astype(bool)]
        figure.add_trace(
            go.Scatter(
                x=broken.index,
                y=broken["spread_zscore"],
                mode="markers",
                name="Relationship break",
                marker_symbol="x",
                marker_size=7,
            )
        )

    figure.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Z-score",
    )
    st.plotly_chart(figure, width="stretch")


def _render_relative_prices(
    ticker_a: str,
    ticker_b: str,
    start_date: str,
    end_date: str,
) -> None:
    st.subheader("Relative price comparison")
    st.caption(
        "Both adjusted-price series are rebased to 1.00 on the first "
        "overlapping observation so their relative paths can be compared "
        "without the difference in dollar price levels obscuring the view."
    )

    pair = _load_pair_prices(
        ticker_a=ticker_a,
        ticker_b=ticker_b,
        start_date=start_date,
        end_date=end_date,
    )

    relative = pd.DataFrame(
        {
            ticker_a: pair["price_a"] / float(pair["price_a"].iloc[0]),
            ticker_b: pair["price_b"] / float(pair["price_b"].iloc[0]),
        },
        index=pair.index,
    )

    figure = px.line(
        relative,
        x=relative.index,
        y=relative.columns,
        title=f"{ticker_a} vs {ticker_b} — Relative Adjusted Prices",
    )
    figure.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Relative price (start = 1.00)",
        legend_title_text="Asset",
    )
    figure.add_hline(y=1.0, line_dash="dot")
    st.plotly_chart(figure, width="stretch")


def _render_equity(result: PairsResearchResult) -> None:
    data = result.stitched_data
    st.subheader("Portfolio value")

    chart = data[["strategy_equity", "benchmark_equity"]].rename(
        columns={
            "strategy_equity": "Pairs strategy",
            "benchmark_equity": "Equal-weight Buy and Hold",
        }
    )
    figure = px.line(
        chart,
        x=chart.index,
        y=chart.columns,
        title="Pairs Strategy vs Equal-Weight Benchmark",
    )
    figure.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Portfolio value",
        legend_title_text="Portfolio",
    )
    st.plotly_chart(figure, width="stretch")


def _render_drawdown(result: PairsResearchResult) -> None:
    data = result.stitched_data
    st.subheader("Drawdown")

    chart = data[["strategy_drawdown", "benchmark_drawdown"]].rename(
        columns={
            "strategy_drawdown": "Pairs strategy",
            "benchmark_drawdown": "Equal-weight Buy and Hold",
        }
    )
    figure = px.line(
        chart,
        x=chart.index,
        y=chart.columns,
        title="Drawdown",
    )
    figure.update_layout(
        hovermode="x unified",
        xaxis_title="Date",
        yaxis_title="Drawdown",
        yaxis_tickformat=".0%",
        legend_title_text="Portfolio",
    )
    st.plotly_chart(figure, width="stretch")


def _render_sensitivity(
    sensitivity: pd.DataFrame,
    optimized_kwargs: dict[str, Any] | None = None,
) -> None:
    st.subheader("Parameter sensitivity")
    if sensitivity.empty:
        st.info("No valid sensitivity combinations were produced.")
        return

    st.warning(
        "This is local, in-sample sensitivity research. Each active strategy "
        "parameter is tested around the current setting, and the highlighted "
        "choice is selected Sharpe-first with total return as a tie-breaker. "
        "The final combined set is still historical optimization, not validated evidence."
    )

    table = sensitivity.copy()

    for column in ["total_return", "max_drawdown"]:
        if column in table.columns:
            table[column] = table[column].map(
                lambda value: (
                    f"{float(value):+.2%}" if pd.notna(value) else "N/A"
                )
            )
    if "sharpe_ratio" in table.columns:
        table["sharpe_ratio"] = table["sharpe_ratio"].map(
            lambda value: (
                f"{float(value):.3f}" if pd.notna(value) else "N/A"
            )
        )
    if "turnover" in table.columns:
        table["turnover"] = table["turnover"].map(
            lambda value: (
                f"{float(value):.2f}" if pd.notna(value) else "N/A"
            )
        )
    if "selected" in table.columns:
        table["selected"] = table["selected"].map(
            lambda value: "✓" if bool(value) else ""
        )

    st.dataframe(table, width="stretch", hide_index=True)

    if optimized_kwargs:
        parameters = [
            parameter
            for parameter in sensitivity["parameter"].drop_duplicates().tolist()
            if parameter != "FINAL COMBINED SET"
        ]
        with st.expander("Sensitivity-derived parameter set", expanded=False):
            optimized_table = pd.DataFrame(
                {
                    "parameter": parameters,
                    "value": [optimized_kwargs.get(name) for name in parameters],
                }
            )
            st.dataframe(
                optimized_table,
                width="stretch",
                hide_index=True,
            )


def _render_discovery(discovery: pd.DataFrame) -> None:
    st.subheader("Pair discovery")
    if discovery.empty:
        st.info("No candidate pairs met the minimum data requirements.")
        return

    st.caption(
        "Pairs are ranked only on the first formation window of the selected "
        "period, so later trading periods stay out of sample for the selection "
        "step. With many candidates, some will look cointegrated by chance: "
        "check the Bonferroni-adjusted p-value. A good rank marks a pair worth "
        "researching, not an out-of-sample edge."
    )
    st.dataframe(
        _format_display_table(discovery),
        width="stretch",
        hide_index=True,
    )


def render_pairs_trading_page() -> None:
    st.title("Pairs Trading Lab")
    st.write(
        "Compare three relative-value models, audit individual trades, inspect "
        "parameter sensitivity, and discover candidate pairs from a small universe."
    )
    st.info(
        "When no divergence signal is active, strategy capital remains in cash. "
        "The current project assumes cash earns 0%."
    )

    with st.sidebar:
        st.header("Pairs trading settings")

        method = st.radio(
            "Pairs method",
            options=[METHOD_DISTANCE, METHOD_COINTEGRATION, METHOD_DYNAMIC],
            key="pairs_method",
        )

        ticker_a = st.text_input(
            "Asset A",
            value="KO",
            key="pairs_ticker_a",
        ).upper().strip()
        ticker_b = st.text_input(
            "Asset B",
            value="PEP",
            key="pairs_ticker_b",
        ).upper().strip()

        start_date = st.date_input(
            "Historical start date",
            value=date(2020, 1, 1),
            key="pairs_start_date",
        )
        end_date = st.date_input(
            "Historical end date",
            value=date(2026, 1, 1),
            key="pairs_end_date",
        )

        formation_years = 2
        trading_months = 6
        warmup_window = 120
        state_noise = 1e-5
        observation_noise_scale = 1.0
        zscore_window = 60
        minimum_hedge_ratio = 0.25
        maximum_hedge_ratio = 4.0
        maximum_cointegration_pvalue = 0.10
        adf_reference_pvalue = 0.10
        minimum_half_life_days = 2.0
        maximum_half_life_days = 120.0
        minimum_mean_crossings = 4
        require_qualification = True
        relationship_break_window = 20
        maximum_recent_volatility_ratio = 2.0
        maximum_recent_mean_shift_z = 2.5
        minimum_recent_return_correlation = 0.0

        if method in {METHOD_DISTANCE, METHOD_COINTEGRATION}:
            st.divider()
            st.subheader("Walk-forward design")
            formation_years = st.number_input(
                "Formation window (years)",
                min_value=1,
                max_value=10,
                value=2,
                step=1,
                key="pairs_formation_years",
            )
            trading_months = st.number_input(
                "Trading window (months)",
                min_value=1,
                max_value=24,
                value=6,
                step=1,
                key="pairs_trading_months",
            )

        if method == METHOD_DISTANCE:
            st.divider()
            st.subheader("Relationship-break filter")
            relationship_break_window = st.number_input(
                "Recent stability window (days)",
                min_value=5,
                max_value=120,
                value=20,
                step=5,
                key="pairs_break_window",
            )
            maximum_recent_volatility_ratio = st.number_input(
                "Maximum recent/formation spread volatility",
                min_value=1.0,
                max_value=10.0,
                value=2.0,
                step=0.25,
                key="pairs_break_vol_ratio",
            )
            maximum_recent_mean_shift_z = st.number_input(
                "Maximum recent mean displacement (formation std)",
                min_value=0.5,
                max_value=10.0,
                value=2.5,
                step=0.25,
                key="pairs_break_mean_shift",
            )
            minimum_recent_return_correlation = st.number_input(
                "Minimum recent return correlation",
                min_value=-1.0,
                max_value=1.0,
                value=0.0,
                step=0.05,
                key="pairs_break_corr",
            )

        if method == METHOD_COINTEGRATION:
            st.divider()
            st.subheader("Cointegration qualification")
            require_qualification = st.checkbox(
                "Trade only qualified folds",
                value=True,
                key="pairs_require_qualification",
                help=(
                    "When enabled, only formation periods that pass the "
                    "cointegration and practical mean-reversion filters may "
                    "trade, which is the point of this method. Disable it to "
                    "inspect the spread in diagnostic mode: every fold then "
                    "trades a plain OLS z-score whether or not the pair was "
                    "cointegrated."
                ),
            )
            maximum_cointegration_pvalue = st.number_input(
                "Maximum cointegration p-value",
                min_value=0.01,
                max_value=0.50,
                value=0.10,
                step=0.01,
                format="%.2f",
                key="pairs_coint_p",
            )
            adf_reference_pvalue = st.number_input(
                "ADF reference p-value (diagnostic only)",
                min_value=0.01,
                max_value=0.50,
                value=0.10,
                step=0.01,
                format="%.2f",
                key="pairs_adf_reference",
                help=(
                    "ADF remains visible as supporting evidence but is no longer "
                    "a second mandatory stationarity gate."
                ),
            )
            minimum_half_life_days = st.number_input(
                "Minimum half-life (days)",
                min_value=0.5,
                max_value=100.0,
                value=2.0,
                step=0.5,
                key="pairs_min_half_life",
            )
            maximum_half_life_days = st.number_input(
                "Maximum half-life (days)",
                min_value=1.0,
                max_value=500.0,
                value=120.0,
                step=5.0,
                key="pairs_max_half_life",
            )
            minimum_mean_crossings = st.number_input(
                "Minimum mean crossings",
                min_value=0,
                max_value=100,
                value=4,
                step=1,
                key="pairs_min_crossings",
            )

        if method == METHOD_DYNAMIC:
            st.divider()
            st.subheader("Dynamic Kalman relationship")
            warmup_window = st.number_input(
                "Warmup window (trading days)",
                min_value=20,
                max_value=504,
                value=120,
                step=10,
                key="pairs_kalman_warmup",
            )
            state_noise = st.number_input(
                "State noise",
                min_value=0.000001,
                max_value=0.01,
                value=0.00001,
                step=0.00001,
                format="%.6f",
                key="pairs_kalman_state_noise",
                help="Higher values let alpha and beta adapt faster.",
            )
            observation_noise_scale = st.number_input(
                "Observation-noise scale",
                min_value=0.10,
                max_value=10.0,
                value=1.0,
                step=0.10,
                key="pairs_kalman_observation_noise",
            )
            zscore_window = st.number_input(
                "Z-score volatility window (trading days)",
                min_value=10,
                max_value=252,
                value=60,
                step=5,
                key="pairs_kalman_zscore_window",
                help=(
                    "Each innovation is divided by the standard deviation of "
                    "the preceding innovations over this window, so the "
                    "z-score reflects how the spread has actually behaved."
                ),
            )
            minimum_hedge_ratio = st.number_input(
                "Minimum hedge ratio",
                min_value=0.01,
                max_value=2.0,
                value=0.25,
                step=0.05,
                key="pairs_minimum_hedge_ratio",
            )
            maximum_hedge_ratio = st.number_input(
                "Maximum hedge ratio",
                min_value=0.10,
                max_value=10.0,
                value=4.0,
                step=0.25,
                key="pairs_maximum_hedge_ratio",
            )

        st.divider()
        st.subheader("Trading rules")
        entry_zscore = st.number_input(
            "Entry z-score",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.25,
            key="pairs_entry_zscore",
        )
        exit_zscore = st.number_input(
            "Exit z-score",
            min_value=0.0,
            max_value=4.5,
            value=0.0,
            step=0.25,
            key="pairs_exit_zscore",
        )
        stop_zscore = st.number_input(
            "Stop z-score",
            min_value=1.0,
            max_value=10.0,
            value=4.0,
            step=0.25,
            key="pairs_stop_zscore",
        )
        maximum_holding_days = st.number_input(
            "Maximum holding period (days)",
            min_value=1,
            max_value=504,
            value=60,
            step=5,
            key="pairs_max_holding",
        )

        st.divider()
        st.subheader("Portfolio assumptions")
        initial_capital = st.number_input(
            "Initial capital",
            min_value=1.0,
            value=10_000.0,
            step=1_000.0,
            key="pairs_initial_capital",
        )
        transaction_cost_bps = st.number_input(
            "One-way transaction cost (bps)",
            min_value=0.0,
            value=10.0,
            step=1.0,
            key="pairs_cost_bps",
        )
        risk_free_rate_percent = st.number_input(
            "Annual risk-free rate (%)",
            min_value=-99.0,
            value=0.0,
            step=0.25,
            key="pairs_risk_free",
        )

        use_optimized_parameters = st.checkbox(
            "Use sensitivity-optimized parameters",
            value=False,
            key=f"pairs_use_optimized_parameters::{method}",
            help=(
                "Always available. When enabled, clicking Run pairs research "
                "first runs a fresh parameter-sensitivity analysis for the "
                "currently selected method and controls, then runs the research "
                "with the resulting combined in-sample parameter set. This may "
                "overfit; validation remains necessary."
            ),
        )

        run_analysis = st.button(
            "Run pairs research",
            type="primary",
            width="stretch",
        )
        run_sensitivity = st.button(
            "Run parameter sensitivity",
            width="stretch",
        )

        st.divider()
        st.subheader("Pair discovery")
        discovery_universe = st.text_area(
            "Candidate tickers",
            value="KO, PEP, KDP, MNST, COKE",
            key="pairs_discovery_universe",
            help="Comma-separated. Keep the universe modest because every ticker is downloaded.",
        )
        discovery_top_n = st.number_input(
            "Candidates to show",
            min_value=3,
            max_value=25,
            value=10,
            step=1,
            key="pairs_discovery_top_n",
        )
        run_discovery = st.button(
            "Discover candidate pairs",
            width="stretch",
        )

    if not ticker_a or not ticker_b:
        st.info("Enter two tickers.")
        return
    if ticker_a == ticker_b:
        st.error("Choose two different tickers.")
        return
    if start_date >= end_date:
        st.error("Start date must be earlier than end date.")
        return
    if exit_zscore >= entry_zscore:
        st.error("Exit z-score must be below entry z-score.")
        return
    if stop_zscore <= entry_zscore:
        st.error("Stop z-score must exceed entry z-score.")
        return
    if maximum_hedge_ratio <= minimum_hedge_ratio:
        st.error("Maximum hedge ratio must exceed the minimum hedge ratio.")
        return

    common = {
        "ticker_a": ticker_a,
        "ticker_b": ticker_b,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "entry_zscore": float(entry_zscore),
        "exit_zscore": float(exit_zscore),
        "stop_zscore": float(stop_zscore),
        "maximum_holding_days": int(maximum_holding_days),
        "initial_capital": float(initial_capital),
        "transaction_cost_bps": float(transaction_cost_bps),
        "risk_free_rate": float(risk_free_rate_percent) / 100.0,
    }

    if method == METHOD_DISTANCE:
        method_kwargs = {
            **common,
            "formation_years": int(formation_years),
            "trading_months": int(trading_months),
            "relationship_break_window": int(relationship_break_window),
            "maximum_recent_volatility_ratio": float(maximum_recent_volatility_ratio),
            "maximum_recent_mean_shift_z": float(maximum_recent_mean_shift_z),
            "minimum_recent_return_correlation": float(minimum_recent_return_correlation),
        }
    elif method == METHOD_COINTEGRATION:
        method_kwargs = {
            **common,
            "formation_years": int(formation_years),
            "trading_months": int(trading_months),
            "maximum_cointegration_pvalue": float(maximum_cointegration_pvalue),
            "adf_reference_pvalue": float(adf_reference_pvalue),
            "minimum_half_life_days": float(minimum_half_life_days),
            "maximum_half_life_days": float(maximum_half_life_days),
            "minimum_mean_crossings": int(minimum_mean_crossings),
            "require_qualification": bool(require_qualification),
        }
    else:
        method_kwargs = {
            **common,
            "warmup_window": int(warmup_window),
            "state_noise": float(state_noise),
            "observation_noise_scale": float(observation_noise_scale),
            "zscore_window": int(zscore_window),
            "minimum_hedge_ratio": float(minimum_hedge_ratio),
            "maximum_hedge_ratio": float(maximum_hedge_ratio),
        }

    sensitivity_bundle = st.session_state.get("pairs_sensitivity")

    # Running pairs research with optimization enabled is deliberately atomic:
    # sensitivity is refreshed from the CURRENT controls first, then the
    # resulting combined parameter set is used immediately for the research run.
    if run_analysis:
        effective_kwargs = dict(method_kwargs)
        used_optimized = False

        if use_optimized_parameters:
            try:
                with st.spinner(
                    "Running parameter sensitivity before optimized pairs research..."
                ):
                    sensitivity, recommended_kwargs = run_parameter_sensitivity(
                        method=method,
                        base_kwargs=method_kwargs,
                    )
            except Exception as error:
                st.error(
                    "Parameter sensitivity failed, so optimized pairs research "
                    f"was not run: {error}"
                )
                return
            else:
                st.session_state["pairs_sensitivity"] = {
                    "method": method,
                    "data": sensitivity,
                    "source_kwargs": dict(method_kwargs),
                    "optimized_kwargs": dict(recommended_kwargs),
                }
                sensitivity_bundle = st.session_state["pairs_sensitivity"]
                effective_kwargs = dict(recommended_kwargs)
                used_optimized = True

        try:
            run_label = (
                f"Running {method} with sensitivity-optimized parameters..."
                if used_optimized
                else f"Running {method}..."
            )
            with st.spinner(run_label):
                if method == METHOD_DISTANCE:
                    result = _run_distance(**effective_kwargs)
                elif method == METHOD_COINTEGRATION:
                    result = _run_cointegration(**effective_kwargs)
                else:
                    result = _run_dynamic(**effective_kwargs)
        except Exception as error:
            st.error(f"Pairs research failed: {error}")
        else:
            st.session_state["pairs_last_run"] = {
                "result": result,
                "method": method,
                "kwargs": dict(effective_kwargs),
                "source_kwargs": dict(method_kwargs),
                "used_optimized_parameters": used_optimized,
            }

    # The standalone button remains useful when the user wants to inspect the
    # sensitivity surface without running the strategy afterward.
    if run_sensitivity:
        try:
            with st.spinner(
                "Testing local sensitivity across all active strategy parameters..."
            ):
                sensitivity, recommended_kwargs = run_parameter_sensitivity(
                    method=method,
                    base_kwargs=method_kwargs,
                )
        except Exception as error:
            st.error(f"Sensitivity analysis failed: {error}")
        else:
            st.session_state["pairs_sensitivity"] = {
                "method": method,
                "data": sensitivity,
                "source_kwargs": dict(method_kwargs),
                "optimized_kwargs": dict(recommended_kwargs),
            }
            sensitivity_bundle = st.session_state["pairs_sensitivity"]

    if run_discovery:
        tickers = [
            item.strip().upper()
            for item in discovery_universe.split(",")
            if item.strip()
        ]
        try:
            with st.spinner("Ranking candidate pairs from formation data..."):
                discovery = _run_discovery(
                    tickers=tickers,
                    start_date=start_date.isoformat(),
                    end_date=end_date.isoformat(),
                    method=method,
                    formation_years=int(formation_years),
                    top_n=int(discovery_top_n),
                    maximum_cointegration_pvalue=float(maximum_cointegration_pvalue),
                    minimum_half_life_days=float(minimum_half_life_days),
                    maximum_half_life_days=float(maximum_half_life_days),
                    minimum_mean_crossings=int(minimum_mean_crossings),
                    kalman_warmup_window=int(warmup_window),
                    kalman_state_noise=float(state_noise),
                    kalman_observation_noise_scale=float(observation_noise_scale),
                    kalman_zscore_window=int(zscore_window),
                )
        except Exception as error:
            st.error(f"Pair discovery failed: {error}")
        else:
            st.session_state["pairs_discovery"] = {
                "method": method,
                "data": discovery,
                "inputs": (discovery_universe, start_date, end_date),
            }

    discovery_bundle = st.session_state.get("pairs_discovery")
    if isinstance(discovery_bundle, dict) and discovery_bundle.get("method") == method:
        discovery_data = discovery_bundle.get("data")
        if isinstance(discovery_data, pd.DataFrame):
            if discovery_bundle.get("inputs") != (
                discovery_universe,
                start_date,
                end_date,
            ):
                st.warning(
                    "The universe or dates have changed since this discovery "
                    "run. Click **Discover candidate pairs** to refresh it."
                )
            _render_discovery(discovery_data)

    sensitivity_bundle = st.session_state.get("pairs_sensitivity")
    if isinstance(sensitivity_bundle, dict) and sensitivity_bundle.get("method") == method:
        sensitivity_data = sensitivity_bundle.get("data")
        sensitivity_optimized = sensitivity_bundle.get("optimized_kwargs")
        if isinstance(sensitivity_data, pd.DataFrame):
            _render_sensitivity(
                sensitivity_data,
                sensitivity_optimized
                if isinstance(sensitivity_optimized, dict)
                else None,
            )

    run_bundle = st.session_state.get("pairs_last_run")
    if not isinstance(run_bundle, dict):
        st.info("Choose a method and click **Run pairs research**.")
        return

    saved_result = run_bundle.get("result")
    saved_method = run_bundle.get("method")
    saved_kwargs = run_bundle.get("kwargs")
    saved_source_kwargs = run_bundle.get("source_kwargs")
    saved_used_optimized = bool(
        run_bundle.get("used_optimized_parameters", False)
    )

    if not isinstance(saved_result, PairsResearchResult):
        st.info("Run the pairs research again after the code update.")
        return
    if saved_method != method:
        st.warning("The displayed result belongs to a different method. Run the current method to refresh it.")
        return
    controls_changed = (
        not isinstance(saved_source_kwargs, dict)
        or saved_source_kwargs != method_kwargs
        or saved_used_optimized != bool(use_optimized_parameters)
    )

    if controls_changed:
        st.warning(
            "The controls or optimized-parameter setting have changed since "
            "the displayed run. Click **Run pairs research** to refresh."
        )

    _render_summary(saved_result)
    _render_relative_prices(
        ticker_a=saved_result.ticker_a,
        ticker_b=saved_result.ticker_b,
        start_date=(
            str(saved_kwargs.get("start_date", start_date.isoformat()))
            if isinstance(saved_kwargs, dict)
            else start_date.isoformat()
        ),
        end_date=(
            str(saved_kwargs.get("end_date", end_date.isoformat()))
            if isinstance(saved_kwargs, dict)
            else end_date.isoformat()
        ),
    )
    _render_diagnostics(saved_result)
    _render_trade_diagnostics(saved_result)
    _render_zscore(
        saved_result,
        float(saved_kwargs.get("entry_zscore", entry_zscore)) if isinstance(saved_kwargs, dict) else float(entry_zscore),
        float(saved_kwargs.get("exit_zscore", exit_zscore)) if isinstance(saved_kwargs, dict) else float(exit_zscore),
        float(saved_kwargs.get("stop_zscore", stop_zscore)) if isinstance(saved_kwargs, dict) else float(stop_zscore),
    )
    _render_equity(saved_result)
    _render_drawdown(saved_result)
