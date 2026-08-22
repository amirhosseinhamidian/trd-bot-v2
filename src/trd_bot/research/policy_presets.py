from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from trd_bot.research.acceptance import (
    ExperimentAcceptancePolicy,
)
from trd_bot.research.experiment_reports import (
    ExperimentResearchReport,
)


class AcceptancePolicyPreset(BaseModel):
    """Named and versioned thresholds for reproducible historical research."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    preset_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}-v[1-9][0-9]*$")
    name: str = Field(pattern=r"^[a-z][a-z0-9-]{1,49}$")
    version: int = Field(ge=1)
    description: str = Field(
        min_length=1,
        max_length=300,
    )
    policy: ExperimentAcceptancePolicy

    interpretation: Literal["historical_research_only"] = "historical_research_only"

    @model_validator(mode="after")
    def validate_preset_id(self) -> Self:
        expected_id = f"{self.name}-v{self.version}"

        if self.preset_id != expected_id:
            raise ValueError("preset ID must match name and version")

        return self


class PresetExperimentResearchReport(BaseModel):
    """Historical experiment report bundled with its exact policy preset."""

    model_config = ConfigDict(frozen=True)

    preset: AcceptancePolicyPreset
    report: ExperimentResearchReport

    interpretation: Literal["historical_research_only"] = "historical_research_only"


def default_acceptance_policy_presets() -> tuple[AcceptancePolicyPreset, ...]:
    """Return built-in example presets for reproducible research workflows."""

    return (
        AcceptancePolicyPreset(
            preset_id="baseline-v1",
            name="baseline",
            version=1,
            description=("Example baseline thresholds for historical research."),
            policy=ExperimentAcceptancePolicy(),
        ),
        AcceptancePolicyPreset(
            preset_id="larger-sample-v1",
            name="larger-sample",
            version=1,
            description=("Example policy requiring a larger historical trade sample."),
            policy=ExperimentAcceptancePolicy(minimum_total_trades=50),
        ),
        AcceptancePolicyPreset(
            preset_id="drawdown-focused-v1",
            name="drawdown-focused",
            version=1,
            description=("Example policy using a tighter historical drawdown threshold."),
            policy=ExperimentAcceptancePolicy(maximum_drawdown_fraction=Decimal("0.10")),
        ),
    )


class AcceptancePolicyPresetCatalog:
    """Read-only catalog of named historical policy presets."""

    def __init__(
        self,
        presets: (Sequence[AcceptancePolicyPreset] | None) = None,
    ) -> None:
        selected = tuple(presets or default_acceptance_policy_presets())

        preset_ids = [preset.preset_id for preset in selected]

        if len(preset_ids) != len(set(preset_ids)):
            raise ValueError("policy preset IDs must be unique")

        self._presets = {preset.preset_id: preset for preset in selected}

    def list_all(
        self,
    ) -> tuple[AcceptancePolicyPreset, ...]:
        return tuple(
            sorted(
                self._presets.values(),
                key=lambda preset: preset.preset_id,
            )
        )

    def get(
        self,
        preset_id: str,
    ) -> AcceptancePolicyPreset | None:
        return self._presets.get(preset_id)
