from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.background_jobs import (
    run_walk_forward_execution_with_session_factory,
)
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyWalkForwardExecutionEnqueuer,
    SqlAlchemyWalkForwardExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
)
from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.jobs import (
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.research.datasets import DatasetBuilder
from trd_bot.research.experiment_executions import (
    EMACrossoverExecutionParameters,
)
from trd_bot.research.walk_forward import WalkForwardConfig, WalkForwardPlanner
from trd_bot.research.walk_forward_execution_jobs import (
    WalkForwardExecutionJobPayload,
    build_walk_forward_execution_idempotency_key,
)
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecutionBuilder,
    WalkForwardExecutionStatus,
)


def build_candles() -> tuple[OHLCVCandle, ...]:
    start_time = datetime(2026, 8, 1, tzinfo=UTC)
    candles: list[OHLCVCandle] = []

    for index in range(10):
        open_time = start_time + timedelta(hours=index)
        close_time = open_time + timedelta(hours=1)
        price = Decimal("100") + Decimal(index)

        candles.append(
            OHLCVCandle.model_validate(
                {
                    "source": "walk-forward-background-test",
                    "pair": {
                        "base_asset": "BTC",
                        "quote_asset": "USDT",
                        "market_type": "spot",
                    },
                    "timeframe": "1h",
                    "open_time": open_time,
                    "close_time": close_time,
                    "received_at": close_time,
                    "open_price": price,
                    "high_price": price + Decimal("1"),
                    "low_price": price - Decimal("1"),
                    "close_price": price + Decimal("0.5"),
                    "volume": Decimal("1000"),
                    "is_closed": True,
                }
            )
        )

    return tuple(candles)


def test_background_job_uses_independent_session_and_persists_result() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    DatabaseBase.metadata.create_all(engine)

    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )

    dataset = DatasetBuilder().build(
        name="Walk-forward background dataset",
        candles=build_candles(),
    )

    walk_forward_config = WalkForwardConfig(
        train_candles=4,
        test_candles=2,
        step_candles=2,
    )

    plan = WalkForwardPlanner().plan(
        dataset=dataset,
        config=walk_forward_config,
    )

    execution = WalkForwardExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=EMACrossoverExecutionParameters(
            fast_period=2,
            slow_period=3,
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        walk_forward_config=walk_forward_config,
        total_folds=len(plan.folds),
    )

    try:
        with session_factory() as setup_session:
            SqlAlchemyDatasetRepository(setup_session).save(dataset)
            SqlAlchemyWalkForwardExecutionRepository(setup_session).save(execution)

        run_walk_forward_execution_with_session_factory(
            execution.execution_id,
            session_factory,
        )

        with session_factory() as verification_session:
            stored_execution = SqlAlchemyWalkForwardExecutionRepository(verification_session).get(
                execution.execution_id
            )

            assert stored_execution is not None
            assert stored_execution.status is WalkForwardExecutionStatus.SUCCEEDED
            assert stored_execution.completed_folds == len(plan.folds)
            assert len(stored_execution.fold_checkpoints) == len(plan.folds)
            assert stored_execution.progress_percent == 100
            assert stored_execution.walk_forward_run_id is not None

            stored_run = SqlAlchemyWalkForwardRunRegistry(verification_session).get(
                stored_execution.walk_forward_run_id
            )

            assert stored_run is not None
            assert stored_run.result.source_dataset_id == dataset.dataset_id

    finally:
        engine.dispose()


def test_durable_worker_executes_atomically_enqueued_walk_forward_job(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    DatabaseBase.metadata.create_all(engine)
    session_factory = sessionmaker(
        bind=engine,
        class_=Session,
        expire_on_commit=False,
    )
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: session_factory)

    dataset = DatasetBuilder().build(
        name="Durable walk-forward dataset",
        candles=build_candles(),
    )
    config = WalkForwardConfig(train_candles=4, test_candles=2, step_candles=2)
    plan = WalkForwardPlanner().plan(dataset=dataset, config=config)
    execution = WalkForwardExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=EMACrossoverExecutionParameters(
            fast_period=2,
            slow_period=3,
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        walk_forward_config=config,
        total_folds=len(plan.folds),
    )
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.WALK_FORWARD_EXECUTION,
        payload=WalkForwardExecutionJobPayload(
            execution_id=execution.execution_id,
        ).model_dump(mode="json"),
        idempotency_key=build_walk_forward_execution_idempotency_key(execution),
    )

    try:
        with session_factory() as session:
            SqlAlchemyDatasetRepository(session).save(dataset)
            submission = SqlAlchemyWalkForwardExecutionEnqueuer(session).enqueue(
                execution=execution,
                job=job,
            )

        with session_factory() as session:
            completed_job = BackgroundJobWorker(
                repository=SqlAlchemyBackgroundJobRepository(session),
                handlers=build_background_job_handler_registry(),
                worker_id="walk-forward-worker-a",
                lease_duration=timedelta(minutes=5),
            ).run_once()

        assert completed_job is not None
        assert completed_job.job_id == submission.job.job_id
        assert completed_job.status is BackgroundJobStatus.SUCCEEDED
        assert completed_job.result_reference == execution.execution_id

        with session_factory() as session:
            completed_execution = SqlAlchemyWalkForwardExecutionRepository(session).get(
                execution.execution_id
            )
            assert completed_execution is not None
            assert completed_execution.status is WalkForwardExecutionStatus.SUCCEEDED
            assert len(completed_execution.fold_checkpoints) == len(plan.folds)
    finally:
        engine.dispose()
