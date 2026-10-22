from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research.comparisons import ExperimentComparisonMetric
from trd_bot.research.datasets import DatasetBuilder, DatasetSnapshot
from trd_bot.research.experiments import ExperimentSummary
from trd_bot.research.optimization_robustness import (
    OptimizationRobustnessPlan,
    OptimizationRobustnessPlanner,
    OptimizationRobustnessScorer,
    OptimizationTrialRejectionReason,
)
from trd_bot.research.walk_forward import WalkForwardConfig
from trd_bot.research.walk_forward_reporting import (
    HistoricalFoldReturnDirection,
    WalkForwardFoldStatistics,
    WalkForwardStabilityReport,
)


def build_dataset(candle_count: int = 16) -> DatasetSnapshot:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    candles = tuple(
        OHLCVCandle(
            source="test-exchange",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            received_at=start,
            open_price=Decimal(100 + index),
            high_price=Decimal(102 + index),
            low_price=Decimal(99 + index),
            close_price=Decimal(101 + index),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index in range(candle_count)
    )
    return DatasetBuilder().build(name="Robustness dataset", candles=candles)


def build_summary(
    experiment_id: str,
    *,
    total_return: str,
    excess_return: str,
    max_drawdown: str = "0.10",
) -> ExperimentSummary:
    return ExperimentSummary(
        experiment_id=experiment_id,
        created_at=datetime(2026, 9, 1, tzinfo=UTC),
        dataset_id="dataset-1234567890abcdef",
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        strategy_fingerprint=None,
        horizon_candles=1,
        parameters=(),
        generated_signals=3,
        total_trades=3,
        net_pnl=Decimal("100"),
        total_return=Decimal(total_return),
        win_rate=Decimal("0.5"),
        max_drawdown_fraction=Decimal(max_drawdown),
        profit_factor=Decimal("1.2"),
        benchmark_type="buy_and_hold",
        benchmark_return=Decimal(total_return) - Decimal(excess_return),
        excess_return=Decimal(excess_return),
        benchmark_max_drawdown_fraction=Decimal("0.12"),
        max_drawdown_fraction_delta=Decimal(max_drawdown) - Decimal("0.12"),
        strategy_has_lower_drawdown=Decimal(max_drawdown) < Decimal("0.12"),
        comparison_outcome="strategy" if Decimal(excess_return) > 0 else "benchmark",
    )


def build_stability(
    suffix: str,
    *,
    returns: tuple[str, str, str],
    excess_returns: tuple[str, str, str],
    trades: tuple[int, int, int] = (1, 1, 1),
) -> WalkForwardStabilityReport:
    strategy_returns = tuple(Decimal(value) for value in returns)
    excess = tuple(Decimal(value) for value in excess_returns)
    folds = tuple(
        WalkForwardFoldStatistics(
            fold_number=index,
            total_trades=trade_count,
            strategy_return=strategy_return,
            benchmark_return=strategy_return - excess_return,
            excess_return=excess_return,
            max_drawdown_fraction=Decimal("0.10"),
            benchmark_max_drawdown_fraction=Decimal("0.12"),
            return_direction=(
                HistoricalFoldReturnDirection.POSITIVE
                if strategy_return > 0
                else HistoricalFoldReturnDirection.NEGATIVE
                if strategy_return < 0
                else HistoricalFoldReturnDirection.FLAT
            ),
        )
        for index, (strategy_return, excess_return, trade_count) in enumerate(
            zip(strategy_returns, excess, trades, strict=True),
            start=1,
        )
    )
    average_return = sum(strategy_returns, start=Decimal("0")) / Decimal("3")
    average_excess = sum(excess, start=Decimal("0")) / Decimal("3")
    ordered_returns = sorted(strategy_returns)
    ordered_excess = sorted(excess)
    positive = sum(value > 0 for value in strategy_returns)
    negative = sum(value < 0 for value in strategy_returns)
    flat = 3 - positive - negative
    outperforming = sum(value > 0 for value in excess)
    underperforming = sum(value < 0 for value in excess)
    return WalkForwardStabilityReport(
        execution_id=f"walk-forward-execution-{suffix * 16}",
        total_folds=3,
        positive_return_folds=positive,
        negative_return_folds=negative,
        flat_return_folds=flat,
        positive_return_fraction=Decimal(positive) / Decimal("3"),
        outperforming_benchmark_folds=outperforming,
        underperforming_benchmark_folds=underperforming,
        benchmark_ties=3 - outperforming - underperforming,
        average_strategy_return=average_return,
        median_strategy_return=ordered_returns[1],
        best_strategy_return=max(strategy_returns),
        worst_strategy_return=min(strategy_returns),
        strategy_return_range=max(strategy_returns) - min(strategy_returns),
        strategy_return_mean_absolute_deviation=(
            sum(
                (abs(value - average_return) for value in strategy_returns),
                start=Decimal("0"),
            )
            / Decimal("3")
        ),
        average_excess_return=average_excess,
        median_excess_return=ordered_excess[1],
        worst_max_drawdown_fraction=Decimal("0.10"),
        folds=folds,
    )


def build_policy() -> OptimizationRobustnessPlan:
    return OptimizationRobustnessPlanner().plan(
        dataset=build_dataset(),
        walk_forward_config=WalkForwardConfig(
            train_candles=4,
            test_candles=4,
            step_candles=4,
        ),
        optimization_trials=2,
    )


def test_planner_bounds_fold_count_and_total_validation_work() -> None:
    policy = build_policy()

    assert policy.total_folds == 3
    assert policy.validation_runs == 6
    assert policy.score_version == "optimization-robustness-score-v1"


def test_planner_rejects_unbounded_trial_fold_work() -> None:
    with pytest.raises(ValueError, match="maximum of 300 trial-fold runs"):
        OptimizationRobustnessPlanner().plan(
            dataset=build_dataset(candle_count=20),
            walk_forward_config=WalkForwardConfig(
                train_candles=4,
                test_candles=4,
                step_candles=4,
            ),
            optimization_trials=100,
        )


def test_planner_rejects_more_than_twelve_walk_forward_folds() -> None:
    with pytest.raises(ValueError, match="at most 12 folds"):
        OptimizationRobustnessPlanner().plan(
            dataset=build_dataset(candle_count=56),
            walk_forward_config=WalkForwardConfig(
                train_candles=4,
                test_candles=4,
                step_candles=4,
            ),
            optimization_trials=1,
        )


def test_out_of_sample_stability_beats_an_in_sample_overfit_trial() -> None:
    scorer = OptimizationRobustnessScorer()
    policy = build_policy()
    overfit = scorer.evaluate(
        trial_number=1,
        experiment=build_summary(
            "experiment-1111111111111111",
            total_return="0.80",
            excess_return="0.70",
        ),
        stability=build_stability(
            "1",
            returns=("-0.10", "-0.05", "0"),
            excess_returns=("-0.08", "-0.04", "-0.01"),
        ),
        policy=policy,
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )
    stable = scorer.evaluate(
        trial_number=2,
        experiment=build_summary(
            "experiment-2222222222222222",
            total_return="0.15",
            excess_return="0.10",
        ),
        stability=build_stability(
            "2",
            returns=("0.04", "0.03", "0.05"),
            excess_returns=("0.02", "0.01", "0.03"),
        ),
        policy=policy,
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    ranking = scorer.rank(
        evaluations=(overfit, stable),
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    assert overfit.in_sample_objective_value > stable.in_sample_objective_value
    assert overfit.generalization_gap > stable.generalization_gap
    assert ranking.best_experiment_id == stable.experiment_id
    assert ranking.entries[0].evaluation == stable


def test_equal_robustness_scores_use_experiment_id_as_the_final_tie_break() -> None:
    scorer = OptimizationRobustnessScorer()
    policy = build_policy()
    later_id = scorer.evaluate(
        trial_number=1,
        experiment=build_summary(
            "experiment-bbbbbbbbbbbbbbbb",
            total_return="0.15",
            excess_return="0.10",
        ),
        stability=build_stability(
            "4",
            returns=("0.04", "0.03", "0.05"),
            excess_returns=("0.02", "0.01", "0.03"),
        ),
        policy=policy,
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )
    earlier_id = scorer.evaluate(
        trial_number=2,
        experiment=build_summary(
            "experiment-aaaaaaaaaaaaaaaa",
            total_return="0.15",
            excess_return="0.10",
        ),
        stability=build_stability(
            "5",
            returns=("0.04", "0.03", "0.05"),
            excess_returns=("0.02", "0.01", "0.03"),
        ),
        policy=policy,
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    ranking = scorer.rank(
        evaluations=(later_id, earlier_id),
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    assert later_id.breakdown.total_score == earlier_id.breakdown.total_score
    assert ranking.best_experiment_id == earlier_id.experiment_id


def test_trial_without_any_traded_fold_is_excluded_from_ranking() -> None:
    scorer = OptimizationRobustnessScorer()
    policy = build_policy()
    no_trades = scorer.evaluate(
        trial_number=1,
        experiment=build_summary(
            "experiment-3333333333333333",
            total_return="0.40",
            excess_return="0.30",
        ),
        stability=build_stability(
            "3",
            returns=("0", "0", "0"),
            excess_returns=("0", "0", "0"),
            trades=(0, 0, 0),
        ),
        policy=policy,
        objective=ExperimentComparisonMetric.EXCESS_RETURN,
    )

    assert no_trades.eligible is False
    assert no_trades.rejection_reasons == (
        OptimizationTrialRejectionReason.INSUFFICIENT_TRADED_FOLDS,
    )
    with pytest.raises(ValueError, match="no robustness-eligible trial"):
        scorer.rank(
            evaluations=(no_trades,),
            objective=ExperimentComparisonMetric.EXCESS_RETURN,
        )
