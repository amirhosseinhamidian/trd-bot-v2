from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.research import (
    ExperimentComparator,
    ExperimentComparisonMetric,
    ExperimentComparisonRequest,
)
from trd_bot.research.experiments import ExperimentSummary


def create_summary(
    *,
    suffix: str,
    dataset_id: str = "dataset-shared",
    horizon_candles: int = 1,
    total_return: str = "0.10",
    excess_return: str = "0.05",
    max_drawdown_fraction: str = "0.08",
) -> ExperimentSummary:
    return ExperimentSummary(
        experiment_id=f"experiment-{suffix:0>16}",
        created_at=datetime(2026, 8, 22, 12, tzinfo=UTC),
        dataset_id=dataset_id,
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=horizon_candles,
        parameters=(),
        generated_signals=2,
        total_trades=1,
        net_pnl=Decimal("100"),
        total_return=Decimal(total_return),
        win_rate=Decimal("1"),
        max_drawdown_fraction=Decimal(max_drawdown_fraction),
        profit_factor=None,
        benchmark_type="buy_and_hold",
        benchmark_return=Decimal("0.05"),
        excess_return=Decimal(excess_return),
        benchmark_max_drawdown_fraction=Decimal("0.10"),
        max_drawdown_fraction_delta=(Decimal(max_drawdown_fraction) - Decimal("0.10")),
        strategy_has_lower_drawdown=(Decimal(max_drawdown_fraction) < Decimal("0.10")),
        comparison_outcome="strategy",
    )


def test_comparator_ranks_higher_excess_return_first() -> None:
    lower = create_summary(
        suffix="1",
        excess_return="0.02",
    )
    higher = create_summary(
        suffix="2",
        excess_return="0.08",
    )

    result = ExperimentComparator().compare(
        experiments=(lower, higher),
        metric=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    assert result.best_experiment_id == higher.experiment_id
    assert result.ranking_direction == "higher_is_better"
    assert [entry.metric_value for entry in result.entries] == [
        Decimal("0.08"),
        Decimal("0.02"),
    ]


def test_comparator_ranks_higher_total_return_first() -> None:
    lower = create_summary(
        suffix="1",
        total_return="0.04",
    )
    higher = create_summary(
        suffix="2",
        total_return="0.12",
    )

    result = ExperimentComparator().compare(
        experiments=(lower, higher),
        metric=ExperimentComparisonMetric.TOTAL_RETURN,
    )

    assert result.best_experiment_id == higher.experiment_id


def test_comparator_ranks_lower_drawdown_first() -> None:
    higher = create_summary(
        suffix="1",
        max_drawdown_fraction="0.12",
    )
    lower = create_summary(
        suffix="2",
        max_drawdown_fraction="0.03",
    )

    result = ExperimentComparator().compare(
        experiments=(higher, lower),
        metric=ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION,
    )

    assert result.best_experiment_id == lower.experiment_id
    assert result.ranking_direction == "lower_is_better"


def test_comparator_breaks_metric_ties_by_experiment_id() -> None:
    second = create_summary(suffix="2")
    first = create_summary(suffix="1")

    result = ExperimentComparator().compare(
        experiments=(second, first),
        metric=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    assert [entry.experiment.experiment_id for entry in result.entries] == [
        first.experiment_id,
        second.experiment_id,
    ]


def test_comparator_rejects_different_datasets() -> None:
    with pytest.raises(
        ValueError,
        match="same dataset",
    ):
        ExperimentComparator().compare(
            experiments=(
                create_summary(
                    suffix="1",
                    dataset_id="dataset-a",
                ),
                create_summary(
                    suffix="2",
                    dataset_id="dataset-b",
                ),
            ),
            metric=ExperimentComparisonMetric.EXCESS_RETURN,
        )


def test_comparator_rejects_different_horizons() -> None:
    with pytest.raises(
        ValueError,
        match="same evaluation horizon",
    ):
        ExperimentComparator().compare(
            experiments=(
                create_summary(
                    suffix="1",
                    horizon_candles=1,
                ),
                create_summary(
                    suffix="2",
                    horizon_candles=2,
                ),
            ),
            metric=ExperimentComparisonMetric.EXCESS_RETURN,
        )


def test_comparison_request_rejects_duplicate_ids() -> None:
    experiment_id = "experiment-0000000000000001"

    with pytest.raises(
        ValidationError,
        match="must be unique",
    ):
        ExperimentComparisonRequest(
            experiment_ids=(
                experiment_id,
                experiment_id,
            ),
        )


def test_comparison_request_rejects_too_few_ids() -> None:
    with pytest.raises(ValidationError):
        ExperimentComparisonRequest(
            experiment_ids=("experiment-0000000000000001",),
        )
