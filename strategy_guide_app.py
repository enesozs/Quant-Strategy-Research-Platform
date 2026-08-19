from typing import Any

import pandas as pd
import streamlit as st

from strategies import STRATEGIES, STRATEGY_METADATA


FAMILY_DESCRIPTIONS: dict[str, str] = {
    "Trend Following": (
        "Attempts to participate in persistent directional movement and move to cash "
        "when the relevant trend condition is no longer satisfied."
    ),
    "Breakout": (
        "Attempts to enter after price moves beyond a recent range or a "
        "volatility-adjusted boundary, anticipating continued directional expansion."
    ),
    "Momentum": (
        "Uses the persistence of recent returns or directional strength to determine "
        "whether, and in some cases how much, to invest."
    ),
    "Mean Reversion": (
        "Attempts to buy unusually weak or stretched conditions on the assumption that "
        "price may move back toward a recent reference level."
    ),
}


def _format_parameter_value(
    value: Any,
    specification: dict[str, Any],
) -> str:
    """Format a parameter value using the metadata specification."""
    if specification.get("format") == "percent":
        return f"{float(value):.2%}"

    if specification.get("type") == "int":
        return str(int(value))

    if isinstance(value, float):
        return f"{value:g}"

    return str(value)


def _build_catalog_table() -> pd.DataFrame:
    """Build a fully populated one-row-per-strategy catalog."""
    rows: list[dict[str, str]] = []

    for strategy_key in STRATEGIES:
        metadata = STRATEGY_METADATA[strategy_key]

        rows.append(
            {
                "Strategy": str(metadata["display_name"]),
                "Family": str(metadata["family"]),
                "Subtype": str(metadata["subtype"]),
                "Signal Style": str(metadata["signal_style"]),
                "Features": ", ".join(
                    str(feature)
                    for feature in metadata["features"]
                ),
                "Best Suited For": str(
                    metadata["best_suited_for"]
                ),
            }
        )

    table = pd.DataFrame(rows)

    if table.empty:
        raise ValueError("The strategy catalog cannot be empty.")

    if table.isna().any().any():
        raise ValueError(
            "Every Strategy Guide catalog cell must contain a value."
        )

    if (
        table.astype(str)
        .apply(lambda column: column.str.strip().eq(""))
        .any()
        .any()
    ):
        raise ValueError(
            "Every Strategy Guide catalog cell must contain a non-empty value."
        )

    return table


def _build_parameter_table(
    metadata: dict[str, Any],
) -> pd.DataFrame:
    """Build the selected strategy's parameter reference table."""
    rows: list[dict[str, str]] = []

    parameter_specs = metadata["parameters"]

    for parameter_name, specification in parameter_specs.items():
        rows.append(
            {
                "Parameter": str(specification["label"]),
                "Code Name": str(parameter_name),
                "Type": str(specification["type"]),
                "Default": _format_parameter_value(
                    specification["default"],
                    specification,
                ),
                "Minimum": _format_parameter_value(
                    specification["min"],
                    specification,
                ),
                "Maximum": _format_parameter_value(
                    specification["max"],
                    specification,
                ),
                "Step": _format_parameter_value(
                    specification["step"],
                    specification,
                ),
            }
        )

    table = pd.DataFrame(rows)

    if table.isna().any().any():
        raise ValueError(
            "Every Strategy Guide parameter-table cell must contain a value."
        )

    return table


def render_strategy_guide_page() -> None:
    """Render the Strategy Guide research-reference page."""
    st.title("Strategy Guide")
    st.write(
        "Understand what each registered strategy is trying to capture, the market "
        "conditions in which its logic is most plausible, its main failure modes, "
        "and what to inspect during optimization and validation."
    )

    st.info(
        "The favorable and unfavorable environments below describe the economic or "
        "market behavior that matches each strategy's design. They are not claims that "
        "a strategy will outperform in a particular stock, sector, or future period."
    )

    strategy_names = {
        STRATEGY_METADATA[key]["display_name"]: key
        for key in STRATEGIES
    }

    with st.sidebar:
        st.subheader("Strategy Guide")

        selected_display_name = st.selectbox(
            "Strategy",
            options=list(strategy_names),
            key="strategy_guide_strategy",
        )

    selected_key = strategy_names[selected_display_name]
    metadata = STRATEGY_METADATA[selected_key]

    st.subheader("Strategy catalog")
    st.caption(
        "A compact overview of each strategy's classification, signal design, "
        "core features, and the market behavior it is best suited to investigate. "
        "The full environment and risk explanations appear in the research profile below."
    )

    catalog_table = _build_catalog_table()

    st.dataframe(
        catalog_table,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    st.header(str(metadata["display_name"]))

    classification_columns = st.columns(4)
    classification_columns[0].metric(
        "Family",
        str(metadata["family"]),
    )
    classification_columns[1].metric(
        "Subtype",
        str(metadata["subtype"]),
    )
    classification_columns[2].metric(
        "Signal style",
        str(metadata["signal_style"]),
    )
    classification_columns[3].metric(
        "Number of parameters",
        str(len(metadata["parameters"])),
    )

    st.caption(
        FAMILY_DESCRIPTIONS[str(metadata["family"])]
    )

    st.subheader("Core idea")
    st.write(str(metadata["description"]))

    with st.expander("Strategy thesis", expanded=True):
        st.write(str(metadata["thesis"]))

    st.subheader("Research profile")

    profile_columns = st.columns(2)

    with profile_columns[0]:
        st.markdown("**Favorable environment**")
        st.write(str(metadata["favorable_environment"]))

        st.markdown("**Main risks**")
        st.write(str(metadata["main_risks"]))

    with profile_columns[1]:
        st.markdown("**Unfavorable environment**")
        st.write(str(metadata["unfavorable_environment"]))

        st.markdown("**Features**")
        st.write(
            " · ".join(
                str(feature)
                for feature in metadata["features"]
            )
        )

    st.subheader("Parameters")
    st.dataframe(
        _build_parameter_table(metadata),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("How to research this strategy")

    research_columns = st.columns(2)

    with research_columns[0]:
        st.markdown("**Optimization considerations**")
        st.write(str(metadata["optimization_notes"]))

    with research_columns[1]:
        st.markdown("**Validation focus**")
        st.write(str(metadata["validation_focus"]))

    st.subheader("Related strategies")
    st.write(
        " · ".join(
            str(strategy)
            for strategy in metadata["related_strategies"]
        )
    )

    st.caption(
        "Use the Single Strategy page for a detailed backtest, Optimization Lab for "
        "parameter sensitivity and robustness, and Validation Lab for unseen-period "
        "and walk-forward evidence."
    )