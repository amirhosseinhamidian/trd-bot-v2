from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.research import (
    DatasetBuilder,
    ExperimentParameter,
    InMemoryWalkForwardRunRegistry,
    WalkForwardConfig,
    WalkForwardDatasetMaterializer,
    WalkForwardExecutor,
    WalkForwardPlanner,
    WalkForwardResearchRun,
    WalkForwardRunBuilder,
    WalkForwardRunCatalogQuery,
    WalkForwardRunSortDirection,
    WalkForwardRunSortField,
    WalkForwardRunSummary,
    WalkForwardStabilityAnalyzer,
)
from trd_bot.strategies import EMACrossoverStrategy

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CREATED_AT = datetime(2026, 8, 22, 10, tzinfo=UTC)


def create_run(
    *,
    fast_period: int = 2,
    slow_period: int = 3,
    created_at: datetime = CREATED_AT,
    horizon_candles: int = 1,
) -> WalkForwardResearchRun:
    start = datetime(2026, 8, 1, 10, tzinfo=UTC)
    candles = []
    prices = ("5", "4", "3", "4", "6", "5", "3", "4", "6", "8")

    for index, price_text in enumerate(prices):
        price = Decimal(price_text)
        open_time = start + timedelta(hours=index)
        candles.append(
            OHLCVCandle(
                source="test-exchange",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                open_time=open_time,
                close_time=open_time + timedelta(hours=1),
                received_at=CREATED_AT,
                open_price=price,
                high_price=price + Decimal("1"),
                low_price=price - Decimal("1"),
                close_price=price,
                volume=Decimal("1000"),
                is_closed=True,
            )
        )

    dataset = DatasetBuilder().build(
        name="Stored walk-forward run",
        candles=candles,
        created_at=CREATED_AT,
    )
    config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )
    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)
    materialization = WalkForwardDatasetMaterializer().materialize(
        dataset=dataset,
        plan=plan,
    )
    parameters = (
        ExperimentParameter(name="slow_period", value=str(slow_period)),
        ExperimentParameter(name="fast_period", value=str(fast_period)),
    )
    result = WalkForwardExecutor().execute(
        dataset=dataset,
        materialization=materialization,
        strategy=EMACrossoverStrategy(
            fast_period=fast_period,
            slow_period=slow_period,
        ),
        strategy_parameters=parameters,
        horizon_candles=horizon_candles,
    )
    return WalkForwardRunBuilder().build(
        result=result,
        walk_forward_config=config,
        created_at=created_at,
    )


def test_run_contains_reproducible_strategy_and_fold_metadata() -> None:
    run = create_run()

    assert run.execution_id == run.result.execution_id
    assert run.result.strategy_parameters == (
        ExperimentParameter(name="fast_period", value="2"),
        ExperimentParameter(name="slow_period", value="3"),
    )
    assert run.walk_forward_config.train_candles == 4
    assert run.result.summary.total_folds == 3


def test_execution_identity_changes_with_strategy_parameters() -> None:
    first = create_run(fast_period=2, slow_period=3)
    second = create_run(fast_period=3, slow_period=4)

    assert first.result.source_dataset_id == second.result.source_dataset_id
    assert first.result.plan_id == second.result.plan_id
    assert first.execution_id != second.execution_id


def test_run_builder_rejects_config_from_another_plan() -> None:
    run = create_run()
    incompatible_config = run.walk_forward_config.model_copy(
        update={"gap_candles": 1},
    )

    with pytest.raises(ValueError, match="config does not match"):
        WalkForwardRunBuilder().build(
            result=run.result,
            walk_forward_config=incompatible_config,
            created_at=CREATED_AT,
        )


def test_registry_saves_and_retrieves_run() -> None:
    run = create_run()
    registry = InMemoryWalkForwardRunRegistry()

    saved = registry.save(run)

    assert saved == run
    assert registry.get(run.execution_id) == run
    assert registry.list_all() == (run,)


def test_registry_save_is_idempotent() -> None:
    first = create_run(created_at=CREATED_AT)
    second = create_run(
        created_at=datetime(2026, 8, 23, 10, tzinfo=UTC),
    )
    registry = InMemoryWalkForwardRunRegistry()

    registry.save(first)
    saved_again = registry.save(second)

    assert saved_again is first
    assert registry.count() == 1


def test_registry_rejects_conflicting_content() -> None:
    run = create_run()
    conflicting = run.model_copy(
        update={
            "walk_forward_config": run.walk_forward_config.model_copy(
                update={"gap_candles": 1},
            )
        },
    )
    registry = InMemoryWalkForwardRunRegistry()
    registry.save(run)

    with pytest.raises(ValueError, match="different content"):
        registry.save(conflicting)


def test_run_summary_excludes_fold_details() -> None:
    run = create_run()
    summary = WalkForwardRunSummary.from_run(run)
    payload = summary.model_dump()

    assert summary.execution_id == run.execution_id
    assert summary.strategy_parameters == run.result.strategy_parameters
    assert summary.total_folds == run.result.summary.total_folds
    assert summary.total_signals == run.result.summary.total_signals
    assert summary.average_excess_return == run.result.summary.average_excess_return
    assert "result" not in payload
    assert "fold_results" not in payload


def test_stability_report_contains_every_fold() -> None:
    run = create_run()

    report = WalkForwardStabilityAnalyzer().analyze(run)

    assert report.execution_id == run.execution_id

    assert report.total_folds == len(run.result.fold_results)

    assert [fold.fold_number for fold in report.folds] == [
        1,
        2,
        3,
    ]

    assert report.interpretation == "historical_research_only"


def test_stability_return_outcome_counts_equal_total_folds() -> None:
    report = WalkForwardStabilityAnalyzer().analyze(create_run())

    assert (
        report.positive_return_folds + report.negative_return_folds + report.flat_return_folds
        == report.total_folds
    )

    assert report.positive_return_fraction == (
        Decimal(report.positive_return_folds) / Decimal(report.total_folds)
    )


def test_stability_benchmark_outcome_counts_equal_total_folds() -> None:
    report = WalkForwardStabilityAnalyzer().analyze(create_run())

    assert (
        report.outperforming_benchmark_folds
        + report.underperforming_benchmark_folds
        + report.benchmark_ties
        == report.total_folds
    )


def test_stability_report_calculates_return_distribution() -> None:
    run = create_run()

    report = WalkForwardStabilityAnalyzer().analyze(run)

    strategy_returns = tuple(
        fold.result.performance_report.total_return for fold in run.result.fold_results
    )

    assert report.best_strategy_return == max(strategy_returns)

    assert report.worst_strategy_return == min(strategy_returns)

    assert report.strategy_return_range == (max(strategy_returns) - min(strategy_returns))

    assert report.strategy_return_mean_absolute_deviation >= 0


def test_stability_fold_metrics_match_pipeline_results() -> None:
    run = create_run()

    report = WalkForwardStabilityAnalyzer().analyze(run)

    for fold_result, statistics in zip(
        run.result.fold_results,
        report.folds,
        strict=True,
    ):
        performance = fold_result.result.performance_report

        benchmark = fold_result.result.benchmark_result.performance_report

        assert statistics.total_trades == performance.total_trades

        assert statistics.strategy_return == performance.total_return

        assert statistics.benchmark_return == benchmark.total_return

        assert statistics.excess_return == (performance.total_return - benchmark.total_return)

        assert statistics.max_drawdown_fraction == performance.max_drawdown_fraction


def test_registry_filters_runs_and_counts_matches() -> None:
    first = create_run(horizon_candles=1)

    second = create_run(
        horizon_candles=2,
        created_at=datetime(
            2026,
            8,
            23,
            10,
            tzinfo=UTC,
        ),
    )

    registry = InMemoryWalkForwardRunRegistry()

    registry.save(first)
    registry.save(second)

    query = WalkForwardRunCatalogQuery(
        strategy_name=" ema-crossover ",
        horizon_candles=2,
    )

    assert registry.count() == 2
    assert registry.count_matching(query) == 1

    assert registry.search_page(
        query=query,
        limit=10,
        offset=0,
    ) == (second,)


def test_registry_sorts_runs_by_horizon_descending() -> None:
    runs = tuple(create_run(horizon_candles=horizon) for horizon in (1, 2, 3))

    registry = InMemoryWalkForwardRunRegistry()

    for run in runs:
        registry.save(run)

    query = WalkForwardRunCatalogQuery(
        sort_by=(WalkForwardRunSortField.HORIZON_CANDLES),
        sort_direction=(WalkForwardRunSortDirection.DESCENDING),
    )

    assert registry.search_page(
        query=query,
        limit=10,
        offset=0,
    ) == tuple(reversed(runs))


def test_registry_paginates_runs() -> None:
    first = create_run(
        fast_period=2,
        slow_period=3,
        created_at=CREATED_AT,
    )
    second = create_run(
        fast_period=3,
        slow_period=4,
        created_at=datetime(2026, 8, 23, 10, tzinfo=UTC),
    )
    registry = InMemoryWalkForwardRunRegistry()
    registry.save(first)
    registry.save(second)

    assert registry.count() == 2
    assert registry.list_page(limit=1, offset=0) == (first,)
    assert registry.list_page(limit=1, offset=1) == (second,)
    assert registry.list_page(limit=10, offset=2) == ()


@pytest.mark.parametrize(("limit", "offset"), [(0, 0), (1, -1)])
def test_registry_rejects_invalid_pagination(limit: int, offset: int) -> None:
    registry = InMemoryWalkForwardRunRegistry()

    with pytest.raises(ValueError):
        registry.list_page(limit=limit, offset=offset)
