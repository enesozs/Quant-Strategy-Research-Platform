import streamlit as st

from comparison_app import render_comparison_page
from optimization_app import render_optimization_page
from single_strategy_app import render_single_strategy_page
from strategy_guide_app import render_strategy_guide_page
from validation_app import render_validation_page


st.set_page_config(
    page_title="Quant Strategy Research Platform",
    page_icon="📈",
    layout="wide",
)


def main() -> None:
    with st.sidebar:
        st.title("Research Platform")

        analysis_mode = st.radio(
            "Analysis mode",
            options=[
                "Compare All Strategies",
                "Single Strategy",
                "Optimization Lab",
                "Validation Lab",
                "Strategy Guide",
            ],
            key="analysis_mode",
        )

        st.divider()

        st.caption(
            "Results are based on historical adjusted-price "
            "data and do not guarantee future performance."
        )

    if analysis_mode == "Compare All Strategies":
        render_comparison_page()
    elif analysis_mode == "Single Strategy":
        render_single_strategy_page()
    elif analysis_mode == "Optimization Lab":
        render_optimization_page()
    elif analysis_mode == "Validation Lab":
        render_validation_page()
    else:
        render_strategy_guide_page()


if __name__ == "__main__":
    main()