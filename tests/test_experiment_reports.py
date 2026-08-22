from decimal import Decimal

import pytest

from trd_bot.research import (
    ExperimentAcceptanceOutcome,
    ExperimentAcceptancePolicy,
    ExperimentResearchReportBuilder,
    HistoricalDrawdownComparison,
)
from trd_bot.research.experiments import ExperimentSummary


def create_summary(
    *,
    total_return: str = "0.10",
    benchmark_return: str = "0.06",
    max_drawdown_fraction: str = "0.08",
    benchmark_max_drawdown_fraction: str = "0.12",
    total_trades: int = 30,
) -> ExperimentSummary:
    strategy_return = Decimal(total_return)
    reference_return = Decimal(benchmark_return)
    strategy_drawdown = Decimal(max_drawdown_fraction)
    reference_drawdown = Decimal(benchmark_max_drawdown_fraction)

    if strategy_return > reference_return:
        outcome = "strategy"
    elif strategy_return < reference_return:
        outcome = "benchmark"
    else:
        outcome = "tie"

    return ExperimentSummary.model_construct(
        experiment_id="experiment-0000000000000001",
        total_trades=total_trades,
        total_return=strategy_return,
        benchmark_type="buy_and_hold",
        benchmark_return=reference_return,
        excess_return=(strategy_return - reference_return),
        comparison_outcome=outcome,
        max_drawdown_fraction=strategy_drawdown,
        benchmark_max_drawdown_fraction=(reference_drawdown),
    )


def test_report_combines_experiment_benchmark_and_acceptance() -> None:
    experiment = create_summary()

    report = ExperimentResearchReportBuilder().build(
        experiment=experiment,
        policy=ExperimentAcceptancePolicy(),
    )

    assert report.experiment is experiment

    assert report.benchmark_context.strategy_total_return == Decimal("0.10")
    assert report.benchmark_context.benchmark_return == Decimal("0.06")
    assert report.benchmark_context.excess_return == Decimal("0.04")

    assert report.acceptance.outcome is ExperimentAcceptanceOutcome.ACCEPTED

    assert report.interpretation == "historical_research_only"


def test_report_counts_passed_and_failed_checks() -> None:
    report = ExperimentResearchReportBuilder().build(
        experiment=create_summary(max_drawdown_fraction="0.25"),
        policy=ExperimentAcceptancePolicy(),
    )

    assert report.passed_checks == 2
    assert report.failed_checks == 1

    assert report.passed_checks + report.failed_checks == 3


@pytest.mark.parametrize(
    (
        "strategy_return",
        "benchmark_return",
        "expected_outcome",
    ),
    [
        ("0.10", "0.05", "strategy"),
        ("0.05", "0.10", "benchmark"),
        ("0.05", "0.05", "tie"),
    ],
)
def test_report_preserves_benchmark_comparison_outcome(
    strategy_return: str,
    benchmark_return: str,
    expected_outcome: str,
) -> None:
    report = ExperimentResearchReportBuilder().build(
        experiment=create_summary(
            total_return=strategy_return,
            benchmark_return=benchmark_return,
        ),
        policy=ExperimentAcceptancePolicy(),
    )

    assert report.benchmark_context.comparison_outcome == expected_outcome


@pytest.mark.parametrize(
    (
        "strategy_drawdown",
        "benchmark_drawdown",
        "expected_comparison",
    ),
    [
        (
            "0.05",
            "0.10",
            HistoricalDrawdownComparison.LOWER,
        ),
        (
            "0.10",
            "0.10",
            HistoricalDrawdownComparison.EQUAL,
        ),
        (
            "0.15",
            "0.10",
            HistoricalDrawdownComparison.HIGHER,
        ),
    ],
)
def test_report_classifies_relative_drawdown(
    strategy_drawdown: str,
    benchmark_drawdown: str,
    expected_comparison: HistoricalDrawdownComparison,
) -> None:
    report = ExperimentResearchReportBuilder().build(
        experiment=create_summary(
            max_drawdown_fraction=(strategy_drawdown),
            benchmark_max_drawdown_fraction=(benchmark_drawdown),
        ),
        policy=ExperimentAcceptancePolicy(),
    )

    assert report.benchmark_context.drawdown_comparison is expected_comparison


def test_report_preserves_insufficient_data_outcome() -> None:
    report = ExperimentResearchReportBuilder().build(
        experiment=create_summary(total_trades=5),
        policy=ExperimentAcceptancePolicy(minimum_total_trades=20),
    )

    assert report.acceptance.outcome is ExperimentAcceptanceOutcome.INSUFFICIENT_DATA
