from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.research.experiments import ExperimentSummary


class ExperimentAcceptanceOutcome(StrEnum):
    """Possible outcomes of a historical experiment assessment."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INSUFFICIENT_DATA = "insufficient_data"


class ExperimentAcceptanceCheckName(StrEnum):
    """Stable identifiers for historical acceptance checks."""

    MINIMUM_TOTAL_TRADES = "minimum_total_trades"
    MINIMUM_EXCESS_RETURN = "minimum_excess_return"
    MAXIMUM_DRAWDOWN_FRACTION = "maximum_drawdown_fraction"


class ExperimentAcceptancePolicy(BaseModel):
    """Explicit thresholds used to assess one historical experiment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    minimum_total_trades: int = Field(default=20, ge=1)
    minimum_excess_return: Decimal = Decimal("0")
    maximum_drawdown_fraction: Decimal = Field(
        default=Decimal("0.20"),
        ge=0,
        le=1,
    )


class ExperimentAcceptanceCheck(BaseModel):
    """One transparent threshold check in an experiment assessment."""

    model_config = ConfigDict(frozen=True)

    name: ExperimentAcceptanceCheckName
    passed: bool
    actual_value: Decimal
    threshold_value: Decimal
    comparison: Literal[
        "greater_than_or_equal",
        "less_than_or_equal",
    ]


class ExperimentAcceptanceResult(BaseModel):
    """Historical acceptance outcome with all supporting checks."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    outcome: ExperimentAcceptanceOutcome
    policy: ExperimentAcceptancePolicy
    checks: tuple[ExperimentAcceptanceCheck, ...]
    interpretation: Literal["historical_research_only"] = "historical_research_only"


class ExperimentAcceptanceEvaluator:
    """Apply reproducible research thresholds to an experiment summary."""

    def evaluate(
        self,
        *,
        experiment: ExperimentSummary,
        policy: ExperimentAcceptancePolicy,
    ) -> ExperimentAcceptanceResult:
        trades_check = ExperimentAcceptanceCheck(
            name=ExperimentAcceptanceCheckName.MINIMUM_TOTAL_TRADES,
            passed=(experiment.total_trades >= policy.minimum_total_trades),
            actual_value=Decimal(experiment.total_trades),
            threshold_value=Decimal(policy.minimum_total_trades),
            comparison="greater_than_or_equal",
        )

        excess_return_check = ExperimentAcceptanceCheck(
            name=ExperimentAcceptanceCheckName.MINIMUM_EXCESS_RETURN,
            passed=(experiment.excess_return >= policy.minimum_excess_return),
            actual_value=experiment.excess_return,
            threshold_value=policy.minimum_excess_return,
            comparison="greater_than_or_equal",
        )

        drawdown_check = ExperimentAcceptanceCheck(
            name=ExperimentAcceptanceCheckName.MAXIMUM_DRAWDOWN_FRACTION,
            passed=(experiment.max_drawdown_fraction <= policy.maximum_drawdown_fraction),
            actual_value=experiment.max_drawdown_fraction,
            threshold_value=policy.maximum_drawdown_fraction,
            comparison="less_than_or_equal",
        )

        checks = (
            trades_check,
            excess_return_check,
            drawdown_check,
        )

        if not trades_check.passed:
            outcome = ExperimentAcceptanceOutcome.INSUFFICIENT_DATA
        elif all(check.passed for check in checks):
            outcome = ExperimentAcceptanceOutcome.ACCEPTED
        else:
            outcome = ExperimentAcceptanceOutcome.REJECTED

        return ExperimentAcceptanceResult(
            experiment_id=experiment.experiment_id,
            outcome=outcome,
            policy=policy,
            checks=checks,
        )
