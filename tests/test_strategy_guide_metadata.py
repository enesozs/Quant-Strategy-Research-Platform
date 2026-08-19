from strategies import STRATEGIES, STRATEGY_METADATA


GUIDE_FIELDS = {
    "display_name",
    "family",
    "subtype",
    "features",
    "signal_style",
    "description",
    "thesis",
    "favorable_environment",
    "unfavorable_environment",
    "main_risks",
    "optimization_notes",
    "validation_focus",
    "related_strategies",
    "parameters",
}


def test_every_registered_strategy_has_complete_guide_metadata() -> None:
    assert set(STRATEGIES) == set(STRATEGY_METADATA)

    for strategy_name, metadata in STRATEGY_METADATA.items():
        assert GUIDE_FIELDS.issubset(metadata)

        for field in GUIDE_FIELDS:
            value = metadata[field]
            assert value is not None, (strategy_name, field)
            assert value != "", (strategy_name, field)
            assert value != [], (strategy_name, field)
            assert value != {}, (strategy_name, field)


def test_every_strategy_parameter_has_complete_metadata() -> None:
    required_parameter_fields = {
        "label",
        "type",
        "default",
        "min",
        "max",
        "step",
    }

    for strategy_name, metadata in STRATEGY_METADATA.items():
        for parameter_name, specification in metadata["parameters"].items():
            assert required_parameter_fields.issubset(specification), (
                strategy_name,
                parameter_name,
            )


def test_related_strategy_names_exist() -> None:
    display_names = {
        str(metadata["display_name"])
        for metadata in STRATEGY_METADATA.values()
    }

    for strategy_name, metadata in STRATEGY_METADATA.items():
        for related_strategy in metadata["related_strategies"]:
            assert related_strategy in display_names, (
                strategy_name,
                related_strategy,
            )
