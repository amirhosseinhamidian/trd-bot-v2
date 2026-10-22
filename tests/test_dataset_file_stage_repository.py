from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetFileImportEnqueuer,
    SqlAlchemyDatasetFileStageRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain import Timeframe, TradingPair
from trd_bot.jobs import BackgroundJob, BackgroundJobBuilder, BackgroundJobKind
from trd_bot.research import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileImportJobPayload,
    DatasetFileStage,
    DatasetFileStageBuilder,
    build_dataset_file_import_idempotency_key,
)

NOW = datetime(2026, 10, 10, 8, tzinfo=UTC)
CSV = b"""timestamp,open,high,low,close,volume
2026-08-20T10:00:00+00:00,100,102,99,101,1500
"""


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory() as database_session:
        yield database_session
    engine.dispose()


def build_stage(*, now: datetime = NOW, ttl: timedelta = timedelta(hours=24)) -> DatasetFileStage:
    request = DatasetFileCommitRequest(
        name="BTC stage",
        source="manual-file",
        pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        timeframe=Timeframe.HOUR_1,
        column_mapping=DatasetColumnMapping(
            open_time="timestamp",
            open_price="open",
            high_price="high",
            low_price="low",
            close_price="close",
            volume="volume",
        ),
        preview_checksum="0" * 64,
    )
    return DatasetFileStageBuilder().build(
        file_name="candles.csv",
        content=CSV,
        request=request,
        now=now,
        ttl=ttl,
    )


def build_job(stage: DatasetFileStage) -> BackgroundJob:
    return BackgroundJobBuilder().build(
        kind=BackgroundJobKind.DATASET_FILE_IMPORT,
        payload=DatasetFileImportJobPayload(
            stage_id=stage.stage_id,
            file_checksum=stage.file_checksum,
        ).model_dump(mode="json"),
        idempotency_key=build_dataset_file_import_idempotency_key(stage),
        now=stage.created_at,
    )


def test_atomically_persists_stage_and_job(session: Session) -> None:
    stage = build_stage()

    result = SqlAlchemyDatasetFileImportEnqueuer(session).enqueue(
        stage=stage,
        job=build_job(stage),
    )

    assert result.created is True
    assert SqlAlchemyDatasetFileStageRepository(session).get(stage.stage_id) == stage
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_duplicate_intent_reuses_job_without_storing_duplicate_bytes(session: Session) -> None:
    enqueuer = SqlAlchemyDatasetFileImportEnqueuer(session)
    first_stage = build_stage()
    first = enqueuer.enqueue(stage=first_stage, job=build_job(first_stage))
    duplicate_stage = build_stage()
    duplicate = enqueuer.enqueue(stage=duplicate_stage, job=build_job(duplicate_stage))

    assert duplicate.created is False
    assert duplicate.job.job_id == first.job.job_id
    assert SqlAlchemyDatasetFileStageRepository(session).get(first_stage.stage_id) == first_stage
    assert SqlAlchemyDatasetFileStageRepository(session).get(duplicate_stage.stage_id) is None
    assert SqlAlchemyBackgroundJobRepository(session).count() == 1


def test_enqueue_opportunistically_removes_expired_stages(session: Session) -> None:
    expired = build_stage(now=NOW - timedelta(days=2), ttl=timedelta(hours=1))
    SqlAlchemyDatasetFileStageRepository(session).save(expired)
    current = build_stage()

    SqlAlchemyDatasetFileImportEnqueuer(session).enqueue(
        stage=current,
        job=build_job(current),
    )

    stages = SqlAlchemyDatasetFileStageRepository(session)
    assert stages.get(expired.stage_id) is None
    assert stages.get(current.stage_id) == current


def test_repository_cleanup_removes_only_expired_stages(session: Session) -> None:
    expired = build_stage(now=NOW - timedelta(days=2), ttl=timedelta(hours=1))
    current = build_stage()
    repository = SqlAlchemyDatasetFileStageRepository(session)
    repository.save(expired)
    repository.save(current)

    removed = repository.delete_expired(now=NOW)

    assert removed == 1
    assert repository.get(expired.stage_id) is None
    assert repository.get(current.stage_id) == current
