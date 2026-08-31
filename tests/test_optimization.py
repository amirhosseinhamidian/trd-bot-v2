from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.experiments import ExperimentParameter, ExperimentSummary
from trd_bot.research.optimization import (
    OptimizationParameterGrid,
    OptimizationPlanner,
    OptimizationScorer,
)


def test_planner_expands_grid_deterministically_and_skips_invalid_cross_parameter_trials() -> None:
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        parameter_grid=(
            OptimizationParameterGrid(
                name="slow_period",
                values=("10", "20"),
            ),
            OptimizationParameterGrid(
                name="fast_period",
                values=("9", "21"),
            ),
        ),
    )

    assert plan.requested_combinations == 4
    assert plan.total_trials == 2
    assert plan.skipped_combinations == 2
    assert [
        tuple((parameter.name, parameter.value) for parameter in trial.parameters)
        for trial in plan.trials
    ] == [
        (("fast_period", "9"), ("slow_period", "10")),
        (("fast_period", "9"), ("slow_period", "20")),
    ]


def test_planner_canonicalizes_decimal_values_and_preserves_objective() -> None:
    plan = OptimizationPlanner().plan(
        strategy_name="rsi-threshold",
        strategy_version="1.0.0",
        objective=ExperimentComparisonMetric.TOTAL_RETURN,
        parameter_grid=(
            OptimizationParameterGrid(name="period", values=("14",)),
            OptimizationParameterGrid(
                name="oversold_threshold",
                values=("30.0", "35.00"),
            ),
            OptimizationParameterGrid(
                name="overbought_threshold",
                values=("70.0",),
            ),
        ),
    )

    assert plan.objective is ExperimentComparisonMetric.TOTAL_RETURN
    assert plan.total_trials == 2
    assert [tuple(parameter.value for parameter in trial.parameters) for trial in plan.trials] == [
        ("14", "30", "70"),
        ("14", "35", "70"),
    ]


@pytest.mark.parametrize(
    ("grid", "message"),
    [
        (
            (OptimizationParameterGrid(name="fast_period", values=("9",)),),
            "missing optimization parameter: slow_period",
        ),
        (
            (
                OptimizationParameterGrid(name="fast_period", values=("9",)),
                OptimizationParameterGrid(name="slow_period", values=("21",)),
                OptimizationParameterGrid(name="unexpected", values=("1",)),
            ),
            "unexpected optimization parameter: unexpected",
        ),
    ],
)
def test_planner_requires_exact_strategy_parameter_names(
    grid: tuple[OptimizationParameterGrid, ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        OptimizationPlanner().plan(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            parameter_grid=grid,
        )


def test_planner_rejects_metadata_bound_and_canonical_duplicates() -> None:
    with pytest.raises(ValueError, match="below its minimum"):
        OptimizationPlanner().plan(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            parameter_grid=(
                OptimizationParameterGrid(name="fast_period", values=("1",)),
                OptimizationParameterGrid(name="slow_period", values=("21",)),
            ),
        )

    with pytest.raises(ValueError, match="contains duplicate values"):
        OptimizationPlanner().plan(
            strategy_name="rsi-threshold",
            strategy_version="1.0.0",
            parameter_grid=(
                OptimizationParameterGrid(name="period", values=("14",)),
                OptimizationParameterGrid(
                    name="oversold_threshold",
                    values=("30", "30.0"),
                ),
                OptimizationParameterGrid(
                    name="overbought_threshold",
                    values=("70",),
                ),
            ),
        )


def test_planner_rejects_grid_that_exceeds_trial_limit() -> None:
    with pytest.raises(ValueError, match="exceeds maximum of 3 trials"):
        OptimizationPlanner(max_trials=3).plan(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            parameter_grid=(
                OptimizationParameterGrid(name="fast_period", values=("2", "3")),
                OptimizationParameterGrid(name="slow_period", values=("10", "20")),
            ),
        )


def _summary(
    experiment_id: str,
    *,
    total_return: str,
    excess_return: str,
    max_drawdown_fraction: str,
) -> ExperimentSummary:
    return ExperimentSummary(
        experiment_id=experiment_id,
        created_at=datetime(2026, 8, 31, 12, 0, tzinfo=UTC),
        dataset_id="dataset-1234567890abcdef",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        horizon_candles=1,
        parameters=(
            ExperimentParameter(name="fast_period", value="9"),
            ExperimentParameter(name="slow_period", value="21"),
        ),
        generated_signals=4,
        total_trades=2,
        net_pnl=Decimal("100"),
        total_return=Decimal(total_return),
        win_rate=Decimal("0.5"),
        max_drawdown_fraction=Decimal(max_drawdown_fraction),
        profit_factor=Decimal("2"),
        benchmark_type="buy_and_hold",
        benchmark_return=Decimal("0.01"),
        excess_return=Decimal(excess_return),
        benchmark_max_drawdown_fraction=Decimal("0.04"),
        max_drawdown_fraction_delta=Decimal("0.01"),
        strategy_has_lower_drawdown=True,
        comparison_outcome="strategy",
    )


def test_scorer_ranks_higher_return_and_lower_drawdown_with_deterministic_ties() -> None:
    first = _summary(
        "experiment-0000000000000001",
        total_return="0.10",
        excess_return="0.08",
        max_drawdown_fraction="0.05",
    )
    second = _summary(
        "experiment-0000000000000002",
        total_return="0.12",
        excess_return="0.08",
        max_drawdown_fraction="0.03",
    )

    excess_ranking = OptimizationScorer().rank(
        experiments=(second, first),
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )
    drawdown_ranking = OptimizationScorer().rank(
        experiments=(first, second),
        objective=ExperimentComparisonMetric.MAX_DRAWDOWN_FRACTION,
    )

    assert excess_ranking.ranking_direction == "higher_is_better"
    assert excess_ranking.best_experiment_id == first.experiment_id
    assert [entry.experiment.experiment_id for entry in excess_ranking.entries] == [
        first.experiment_id,
        second.experiment_id,
    ]

    assert drawdown_ranking.ranking_direction == "lower_is_better"
    assert drawdown_ranking.best_experiment_id == second.experiment_id
    assert drawdown_ranking.entries[0].metric_value == Decimal("0.03")


def test_scorer_rejects_noncomparable_experiments() -> None:
    first = _summary(
        "experiment-0000000000000001",
        total_return="0.10",
        excess_return="0.08",
        max_drawdown_fraction="0.05",
    )
    other_dataset = _summary(
        "experiment-0000000000000002",
        total_return="0.12",
        excess_return="0.09",
        max_drawdown_fraction="0.03",
    ).model_copy(update={"dataset_id": "dataset-fedcba0987654321"})

    with pytest.raises(ValueError, match="must share dataset"):
        OptimizationScorer().rank(
            experiments=(first, other_dataset),
            objective=ExperimentComparisonMetric.TOTAL_RETURN,
        )
