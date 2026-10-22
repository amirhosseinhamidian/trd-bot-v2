from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyOptimizationExecutionEnqueuer,
    SqlAlchemyOptimizationExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import (
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.research.datasets import DatasetBuilder
from trd_bot.research.optimization import OptimizationParameterGrid, OptimizationPlanner
from trd_bot.research.optimization_executions import (
    OptimizationExecutionBuilder,
    OptimizationExecutionState,
)
from trd_bot.research.optimization_jobs import (
    OptimizationExecutionJobPayload,
    build_optimization_execution_idempotency_key,
)
from trd_bot.research.optimization_robustness import OptimizationRobustnessPlanner
from trd_bot.research.walk_forward import WalkForwardConfig


def test_durable_worker_executes_and_links_an_optimization_job(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'optimization.db'}")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    start = datetime(2026, 8, 1, tzinfo=UTC)
    prices = tuple("10" if index % 2 == 0 else "20" for index in range(16))
    candles = tuple(
        OHLCVCandle(
            source="test-exchange",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=start + timedelta(hours=index),
            close_time=start + timedelta(hours=index + 1),
            received_at=start,
            open_price=Decimal(price),
            high_price=Decimal(price) + Decimal("1"),
            low_price=Decimal(price) - Decimal("1"),
            close_price=Decimal(price),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index, price in enumerate(prices)
    )
    dataset = DatasetBuilder().build(name="Durable optimization dataset", candles=candles)
    plan = OptimizationPlanner().plan(
        strategy_name="ema-crossover",
        strategy_version="1.0.0",
        parameter_grid=(
            OptimizationParameterGrid(name="fast_period", values=("2", "3")),
            OptimizationParameterGrid(name="slow_period", values=("4",)),
        ),
    )
    execution = OptimizationExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        plan=plan,
        horizon_candles=1,
        backtest_config=BacktestConfig(
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        robustness_plan=OptimizationRobustnessPlanner().plan(
            dataset=dataset,
            walk_forward_config=WalkForwardConfig(
                train_candles=4,
                test_candles=4,
                step_candles=4,
            ),
            optimization_trials=plan.total_trials,
        ),
    )
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
        payload=OptimizationExecutionJobPayload(
            execution_id=execution.execution_id,
        ).model_dump(mode="json"),
        idempotency_key=build_optimization_execution_idempotency_key(execution),
        max_attempts=3,
        now=execution.created_at,
    )

    with factory() as session:
        SqlAlchemyDatasetRepository(session).save(dataset)
        submission = SqlAlchemyOptimizationExecutionEnqueuer(session).enqueue(
            execution=execution,
            job=job,
        )

    with factory() as session:
        completed_job = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="optimization-worker-a",
            lease_duration=timedelta(minutes=5),
        ).run_once()

    assert completed_job is not None
    assert completed_job.status is BackgroundJobStatus.SUCCEEDED
    assert completed_job.result_reference == submission.execution.execution_id

    with factory() as session:
        completed_execution = SqlAlchemyOptimizationExecutionRepository(session).get(
            submission.execution.execution_id,
        )
        assert completed_execution is not None
        assert completed_execution.status is OptimizationExecutionState.SUCCEEDED
        assert completed_execution.completed_trials == 2
        assert completed_execution.best_experiment_id in completed_execution.experiment_ids
        assert completed_execution.robustness_ranking is not None
        assert completed_execution.robustness_ranking.eligible_trials == 2
        assert SqlAlchemyExperimentRegistry(session).count() == 2
        assert SqlAlchemyWalkForwardRunRegistry(session).count() == 2

    engine.dispose()
