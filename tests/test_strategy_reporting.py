from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research import (
    DirectionMetrics,
    SignalEvaluation,
    SignalEvaluationReport,
    SignalOutcome,
    StrategyReportBuilder,
)
from trd_bot.strategies import SignalDirection

REFERENCE_TIME = datetime(
    2026,
    8,
    21,
    10,
    tzinfo=UTC,
)

EVALUATION_TIME = datetime(
    2026,
    8,
    21,
    11,
    tzinfo=UTC,
)


def create_evaluation(
    *,
    signal_id: str,
    direction: SignalDirection,
    directional_return: Decimal,
    outcome: SignalOutcome,
) -> SignalEvaluation:
    reference_price = Decimal("100")

    if direction == SignalDirection.LONG:
        evaluation_price = reference_price * (Decimal("1") + directional_return)
    else:
        evaluation_price = reference_price * (Decimal("1") - directional_return)

    return SignalEvaluation(
        signal_id=signal_id,
        direction=direction,
        horizon_candles=1,
        reference_time=REFERENCE_TIME,
        reference_price=reference_price,
        evaluation_time=EVALUATION_TIME,
        evaluation_price=evaluation_price,
        directional_return=directional_return,
        outcome=outcome,
    )


def create_report(
    evaluations: tuple[SignalEvaluation, ...],
) -> SignalEvaluationReport:
    correct_signals = sum(evaluation.outcome == SignalOutcome.CORRECT for evaluation in evaluations)

    incorrect_signals = sum(
        evaluation.outcome == SignalOutcome.INCORRECT for evaluation in evaluations
    )

    flat_signals = sum(evaluation.outcome == SignalOutcome.FLAT for evaluation in evaluations)

    hit_rate = Decimal(correct_signals) / Decimal(len(evaluations)) if evaluations else None

    return SignalEvaluationReport(
        dataset_id="dataset-test",
        horizon_candles=1,
        total_signals=len(evaluations),
        resolved_signals=len(evaluations),
        unresolved_signals=0,
        ignored_neutral_signals=0,
        correct_signals=correct_signals,
        incorrect_signals=incorrect_signals,
        flat_signals=flat_signals,
        hit_rate=hit_rate,
        evaluations=evaluations,
    )


def test_summary_calculates_overall_metrics() -> None:
    report = create_report(
        (
            create_evaluation(
                signal_id="long-correct",
                direction=SignalDirection.LONG,
                directional_return=Decimal("0.10"),
                outcome=SignalOutcome.CORRECT,
            ),
            create_evaluation(
                signal_id="long-incorrect",
                direction=SignalDirection.LONG,
                directional_return=Decimal("-0.05"),
                outcome=SignalOutcome.INCORRECT,
            ),
            create_evaluation(
                signal_id="short-correct",
                direction=SignalDirection.SHORT,
                directional_return=Decimal("0.20"),
                outcome=SignalOutcome.CORRECT,
            ),
        )
    )

    summary = StrategyReportBuilder().build(report)

    assert summary.resolved_signals == 3
    assert summary.overall_hit_rate == Decimal("2") / Decimal("3")
    assert summary.average_directional_return == Decimal("0.25") / Decimal("3")
    assert summary.median_directional_return == Decimal("0.10")
    assert summary.best_directional_return == Decimal("0.20")
    assert summary.worst_directional_return == Decimal("-0.05")


def test_summary_separates_long_and_short_metrics() -> None:
    report = create_report(
        (
            create_evaluation(
                signal_id="long-correct",
                direction=SignalDirection.LONG,
                directional_return=Decimal("0.10"),
                outcome=SignalOutcome.CORRECT,
            ),
            create_evaluation(
                signal_id="long-incorrect",
                direction=SignalDirection.LONG,
                directional_return=Decimal("-0.05"),
                outcome=SignalOutcome.INCORRECT,
            ),
            create_evaluation(
                signal_id="short-correct",
                direction=SignalDirection.SHORT,
                directional_return=Decimal("0.20"),
                outcome=SignalOutcome.CORRECT,
            ),
        )
    )

    summary = StrategyReportBuilder().build(report)

    assert summary.long_metrics.evaluated_signals == 2
    assert summary.long_metrics.hit_rate == Decimal("0.5")
    assert summary.long_metrics.median_directional_return == Decimal("0.025")

    assert summary.short_metrics.evaluated_signals == 1
    assert summary.short_metrics.hit_rate == Decimal("1")


def test_empty_report_returns_empty_metrics() -> None:
    summary = StrategyReportBuilder().build(create_report(()))

    assert summary.overall_hit_rate is None
    assert summary.average_directional_return is None
    assert summary.long_metrics.hit_rate is None
    assert summary.short_metrics.hit_rate is None


def test_inconsistent_direction_counts_are_rejected() -> None:
    with pytest.raises(
        ValidationError,
        match="outcome counts must equal",
    ):
        DirectionMetrics(
            direction=SignalDirection.LONG,
            evaluated_signals=2,
            correct_signals=1,
            incorrect_signals=0,
            flat_signals=0,
            hit_rate=Decimal("0.5"),
        )
