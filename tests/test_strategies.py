import numpy as np
import pandas as pd
import pytest

from backtester import run_strategy_on_data
from strategies import (
    STRATEGIES,
    STRATEGY_METADATA,
    apply_strategy,
    get_default_parameters,
)


def create_market_data(
    number_of_rows: int = 600,
) -> pd.DataFrame:
    """
    Create deterministic synthetic OHLC market data.

    The combination of a trend and a cyclical component gives
    strategies both rising and falling price environments.
    """
    index = pd.date_range(
        start="2020-01-01",
        periods=number_of_rows,
        freq="B",
    )

    time = np.arange(number_of_rows)

    close = (
        100
        + 0.05 * time
        + 8 * np.sin(time / 20)
        + 2 * np.sin(time / 5)
    )

    data = pd.DataFrame(
        {
            "Open": close - 0.25,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": 1_000_000,
        },
        index=index,
    )

    data["asset_return"] = data["Close"].pct_change()

    return data


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_registered_strategy_produces_valid_signals(
    strategy_name: str,
) -> None:
    data = create_market_data()

    parameters = get_default_parameters(
        strategy_name
    )

    result = apply_strategy(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=parameters,
    )

    assert "signal" in result.columns
    assert len(result) == len(data)
    assert result.index.equals(data.index)
    assert not result["signal"].isna().any()

    unique_signals = set(
        result["signal"].unique()
    )

    assert unique_signals.issubset({0, 1})


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_registered_strategy_runs_through_backtester(
    strategy_name: str,
) -> None:
    data = create_market_data()

    parameters = get_default_parameters(
        strategy_name
    )

    result = run_strategy_on_data(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=parameters,
        initial_capital=10_000,
        transaction_cost_bps=10,
    )

    required_columns = {
        "signal",
        "position",
        "trade",
        "strategy_return",
        "strategy_equity",
        "strategy_drawdown",
        "buy_hold_return",
        "buy_hold_turnover",
        "buy_hold_transaction_cost",
        "buy_hold_equity",
        "buy_hold_drawdown",
    }

    assert required_columns.issubset(
        result.columns
    )

    assert result["strategy_equity"].notna().all()
    assert result["buy_hold_equity"].notna().all()

    assert (
        result["strategy_equity"] > 0
    ).all()

    assert (
        result["buy_hold_equity"] > 0
    ).all()

    assert result["buy_hold_turnover"].sum() == pytest.approx(
        1.0
    )


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_strategy_does_not_modify_original_data(
    strategy_name: str,
) -> None:
    data = create_market_data()
    original = data.copy(deep=True)

    apply_strategy(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=get_default_parameters(
            strategy_name
        ),
    )

    pd.testing.assert_frame_equal(
        data,
        original,
    )


def test_every_registered_strategy_has_metadata() -> None:
    """
    Every executable strategy must also have a complete
    metadata entry for the research interface.
    """
    assert set(STRATEGIES) == set(STRATEGY_METADATA)


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_strategy_guide_metadata_is_complete(
    strategy_name: str,
) -> None:
    """
    Ensure every registered strategy contains every field
    required by the Strategy Guide.
    """
    metadata = STRATEGY_METADATA[strategy_name]

    required_fields = {
        "display_name",
        "family",
        "subtype",
        "signal_style",
        "features",
        "best_suited_for",
        "description",
        "thesis",
        "favorable_environment",
        "unfavorable_environment",
        "main_risks",
        "validation_focus",
    }

    missing_fields = (
        required_fields
        - set(metadata)
    )

    assert not missing_fields, (
        f"{strategy_name} is missing Strategy Guide "
        f"metadata fields: {sorted(missing_fields)}"
    )


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_strategy_guide_text_fields_are_non_empty(
    strategy_name: str,
) -> None:
    """
    Prevent blank Strategy Guide sections from appearing in
    the application.
    """
    metadata = STRATEGY_METADATA[strategy_name]

    text_fields = {
        "display_name",
        "family",
        "subtype",
        "signal_style",
        "best_suited_for",
        "description",
        "thesis",
        "favorable_environment",
        "unfavorable_environment",
        "main_risks",
        "validation_focus",
    }

    for field in text_fields:
        value = metadata[field]

        assert isinstance(value, str), (
            f"{strategy_name}.{field} must be a string."
        )

        assert value.strip(), (
            f"{strategy_name}.{field} cannot be empty."
        )


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_strategy_features_are_non_empty(
    strategy_name: str,
) -> None:
    """
    Every strategy should expose at least one meaningful feature.
    """
    features = STRATEGY_METADATA[
        strategy_name
    ]["features"]

    assert isinstance(features, list), (
        f"{strategy_name}.features must be a list."
    )

    assert features, (
        f"{strategy_name}.features cannot be empty."
    )

    for feature in features:
        assert isinstance(feature, str), (
            f"Every feature for {strategy_name} "
            "must be a string."
        )

        assert feature.strip(), (
            f"{strategy_name} contains an empty feature."
        )


def test_strategy_display_names_are_unique() -> None:
    """
    Distinct strategies should not appear under the same
    human-readable name in selectors and research tables.
    """
    display_names = [
        STRATEGY_METADATA[
            strategy_name
        ]["display_name"]
        for strategy_name in STRATEGIES
    ]

    assert len(display_names) == len(
        set(display_names)
    )


@pytest.mark.parametrize(
    "strategy_name",
    list(STRATEGIES),
)
def test_strategy_default_parameters_are_valid(
    strategy_name: str,
) -> None:
    """
    Every registered strategy must expose its defaults as a
    dictionary and those defaults must successfully run through
    the strategy implementation.
    """
    parameters = get_default_parameters(
        strategy_name
    )

    assert isinstance(parameters, dict)

    data = create_market_data()

    result = apply_strategy(
        data=data,
        strategy_name=strategy_name,
        strategy_parameters=parameters,
    )

    assert len(result) == len(data)
    assert result.index.equals(data.index)


def test_strategy_families_are_consistently_named() -> None:
    """
    Catch accidental whitespace or capitalization variants that
    would split one conceptual family into multiple UI groups.
    """
    families = [
        STRATEGY_METADATA[
            strategy_name
        ]["family"]
        for strategy_name in STRATEGIES
    ]

    normalized_families = [
        family.strip().casefold()
        for family in families
    ]

    unique_original = {
        family.strip()
        for family in families
    }

    unique_normalized = set(
        normalized_families
    )

    assert len(unique_original) == len(
        unique_normalized
    )


def test_strategy_subtypes_are_consistently_named() -> None:
    """
    Catch accidental whitespace or capitalization variants in
    Strategy Guide subtype classifications.
    """
    subtypes = [
        STRATEGY_METADATA[
            strategy_name
        ]["subtype"]
        for strategy_name in STRATEGIES
    ]

    normalized_subtypes = [
        subtype.strip().casefold()
        for subtype in subtypes
    ]

    unique_original = {
        subtype.strip()
        for subtype in subtypes
    }

    unique_normalized = set(
        normalized_subtypes
    )

    assert len(unique_original) == len(
        unique_normalized
    )