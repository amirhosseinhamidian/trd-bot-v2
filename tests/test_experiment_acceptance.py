from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research import (
    ExperimentAcceptanceCheckName,
    ExperimentAcceptanceEvaluator,
    ExperimentAcceptanceOutcome,
    ExperimentAcceptancePolicy,
)
from trd_bot.research.experiments import ExperimentSummary


def create_summary(
    *,
    total_trades: int = 30,
    excess_return: str = "0.05",
    max_drawdown_fraction: str = "0.10",
) -> ExperimentSummary:
    return ExperimentSummary.model_construct(
        experiment_id="experiment-0000000000000001",
        total_trades=total_trades,
        excess_return=Decimal(excess_return),
        max_drawdown_fraction=Decimal(max_drawdown_fraction),
    )


def test_evaluator_accepts_experiment_that_passes_all_checks() -> None:
    result = ExperimentAcceptanceEvaluator().evaluate(
        experiment=create_summary(),
        policy=ExperimentAcceptancePolicy(),
    )

    assert result.outcome is ExperimentAcceptanceOutcome.ACCEPTED
    assert all(check.passed for check in result.checks)
    assert result.interpretation == "historical_research_only"


def test_evaluator_marks_too_few_trades_as_insufficient_data() -> None:
    result = ExperimentAcceptanceEvaluator().evaluate(
        experiment=create_summary(total_trades=19),
        policy=ExperimentAcceptancePolicy(minimum_total_trades=20),
    )

    assert result.outcome is ExperimentAcceptanceOutcome.INSUFFICIENT_DATA
    assert result.checks[0].name is ExperimentAcceptanceCheckName.MINIMUM_TOTAL_TRADES
    assert result.checks[0].passed is False


def test_evaluator_rejects_insufficient_excess_return() -> None:
    result = ExperimentAcceptanceEvaluator().evaluate(
        experiment=create_summary(excess_return="0.01"),
        policy=ExperimentAcceptancePolicy(minimum_excess_return=Decimal("0.02")),
    )

    assert result.outcome is ExperimentAcceptanceOutcome.REJECTED
    assert result.checks[1].name is ExperimentAcceptanceCheckName.MINIMUM_EXCESS_RETURN
    assert result.checks[1].passed is False


def test_evaluator_rejects_excessive_drawdown() -> None:
    result = ExperimentAcceptanceEvaluator().evaluate(
        experiment=create_summary(max_drawdown_fraction="0.21"),
        policy=ExperimentAcceptancePolicy(maximum_drawdown_fraction=Decimal("0.20")),
    )

    assert result.outcome is ExperimentAcceptanceOutcome.REJECTED
    assert result.checks[2].name is ExperimentAcceptanceCheckName.MAXIMUM_DRAWDOWN_FRACTION
    assert result.checks[2].passed is False


def test_evaluator_includes_actual_and_threshold_values() -> None:
    policy = ExperimentAcceptancePolicy(
        minimum_total_trades=25,
        minimum_excess_return=Decimal("0.03"),
        maximum_drawdown_fraction=Decimal("0.15"),
    )

    result = ExperimentAcceptanceEvaluator().evaluate(
        experiment=create_summary(),
        policy=policy,
    )

    assert result.checks[0].actual_value == Decimal("30")
    assert result.checks[0].threshold_value == Decimal("25")
    assert result.checks[1].actual_value == Decimal("0.05")
    assert result.checks[1].threshold_value == Decimal("0.03")
    assert result.checks[2].actual_value == Decimal("0.10")
    assert result.checks[2].threshold_value == Decimal("0.15")


@pytest.mark.parametrize(
    "policy_data",
    [
        {
            "minimum_total_trades": 0,
        },
        {
            "maximum_drawdown_fraction": Decimal("-0.01"),
        },
        {
            "maximum_drawdown_fraction": Decimal("1.01"),
        },
    ],
)
def test_policy_rejects_invalid_thresholds(
    policy_data: dict[str, int | Decimal],
) -> None:
    with pytest.raises(ValidationError):
        ExperimentAcceptancePolicy.model_validate(policy_data)
