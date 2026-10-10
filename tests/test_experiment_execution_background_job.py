from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionEnqueuer,
    SqlAlchemyExperimentExecutionRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain import OHLCVCandle, Timeframe, TradingPair
from trd_bot.jobs import (
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.research import (
    DatasetBuilder,
    EMACrossoverExecutionParameters,
    ExperimentExecutionBuilder,
    ExperimentExecutionJobPayload,
    ExperimentExecutionStatus,
    build_experiment_execution_idempotency_key,
)

NOW = datetime(2026, 10, 10, 10, tzinfo=UTC)


def build_candles() -> tuple[OHLCVCandle, ...]:
    return tuple(
        OHLCVCandle(
            source="durable-experiment-test",
            pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
            timeframe=Timeframe.HOUR_1,
            open_time=NOW + timedelta(hours=index),
            close_time=NOW + timedelta(hours=index + 1),
            received_at=NOW + timedelta(hours=index + 1),
            open_price=Decimal(100 + index),
            high_price=Decimal(102 + index),
            low_price=Decimal(99 + index),
            close_price=Decimal(101 + index),
            volume=Decimal(1000 + index),
            is_closed=True,
        )
        for index in range(60)
    )


def test_durable_worker_executes_the_atomically_enqueued_experiment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'experiment-job.db'}")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)
    dataset = DatasetBuilder().build(
        name="Durable experiment dataset",
        candles=build_candles(),
    )
    execution = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=EMACrossoverExecutionParameters(
            fast_period=9,
            slow_period=21,
            horizon_candles=1,
            starting_balance=Decimal("10000"),
            allocation_fraction=Decimal("0.10"),
            fee_rate=Decimal("0.001"),
            slippage_rate=Decimal("0.0005"),
        ),
        now=NOW,
    )
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
        payload=ExperimentExecutionJobPayload(
            execution_id=execution.execution_id,
        ).model_dump(mode="json"),
        idempotency_key=build_experiment_execution_idempotency_key(execution),
        now=NOW,
    )

    with factory() as session:
        SqlAlchemyDatasetRepository(session).save(dataset)
        submission = SqlAlchemyExperimentExecutionEnqueuer(session).enqueue(
            execution=execution,
            job=job,
        )

    with factory() as session:
        completed_job = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="experiment-worker-a",
            lease_duration=timedelta(minutes=5),
        ).run_once()

    assert completed_job is not None
    assert completed_job.job_id == submission.job.job_id
    assert completed_job.status is BackgroundJobStatus.SUCCEEDED
    assert completed_job.result_reference == execution.execution_id

    with factory() as session:
        completed_execution = SqlAlchemyExperimentExecutionRepository(session).get(
            execution.execution_id
        )
        assert completed_execution is not None
        assert completed_execution.status is ExperimentExecutionStatus.SUCCEEDED
        assert completed_execution.experiment_id is not None

    engine.dispose()
