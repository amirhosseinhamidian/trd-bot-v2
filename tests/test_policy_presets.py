from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research import (
    AcceptancePolicyPreset,
    AcceptancePolicyPresetCatalog,
    ExperimentAcceptancePolicy,
    default_acceptance_policy_presets,
)


def test_default_catalog_contains_versioned_presets() -> None:
    presets = default_acceptance_policy_presets()

    assert [preset.preset_id for preset in presets] == [
        "baseline-v1",
        "larger-sample-v1",
        "drawdown-focused-v1",
    ]

    assert all(preset.version == 1 for preset in presets)

    assert all(preset.interpretation == "historical_research_only" for preset in presets)


def test_default_presets_have_distinct_thresholds() -> None:
    catalog = AcceptancePolicyPresetCatalog()

    baseline = catalog.get("baseline-v1")
    larger_sample = catalog.get("larger-sample-v1")
    drawdown_focused = catalog.get("drawdown-focused-v1")

    assert baseline is not None
    assert larger_sample is not None
    assert drawdown_focused is not None

    assert baseline.policy.minimum_total_trades == 20
    assert larger_sample.policy.minimum_total_trades == 50
    assert drawdown_focused.policy.maximum_drawdown_fraction == Decimal("0.10")


def test_catalog_lists_presets_by_identifier() -> None:
    catalog = AcceptancePolicyPresetCatalog()

    assert [preset.preset_id for preset in catalog.list_all()] == [
        "baseline-v1",
        "drawdown-focused-v1",
        "larger-sample-v1",
    ]


def test_catalog_returns_none_for_unknown_preset() -> None:
    assert AcceptancePolicyPresetCatalog().get("unknown-v1") is None


def test_catalog_rejects_duplicate_preset_ids() -> None:
    preset = AcceptancePolicyPreset(
        preset_id="example-v1",
        name="example",
        version=1,
        description=("Example historical policy."),
        policy=ExperimentAcceptancePolicy(),
    )

    with pytest.raises(
        ValueError,
        match="must be unique",
    ):
        AcceptancePolicyPresetCatalog(
            (
                preset,
                preset,
            )
        )


def test_preset_rejects_identifier_that_does_not_match_name_and_version() -> None:
    with pytest.raises(
        ValidationError,
        match="must match",
    ):
        AcceptancePolicyPreset(
            preset_id="example-v2",
            name="example",
            version=1,
            description=("Example historical policy."),
            policy=ExperimentAcceptancePolicy(),
        )
