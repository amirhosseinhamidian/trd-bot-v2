from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

import trd_bot.api.job_handlers as job_handlers
from trd_bot.api.job_handlers import build_background_job_handler_registry
from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyDatasetFileImportEnqueuer,
    SqlAlchemyDatasetFileStageRepository,
    SqlAlchemyDatasetRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain import Timeframe, TradingPair
from trd_bot.jobs import (
    BackgroundJobBuilder,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.research import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileImportJobPayload,
    DatasetFileImportService,
    DatasetFilePreviewRequest,
    DatasetFileStageBuilder,
    build_dataset_file_import_idempotency_key,
)

NOW = datetime(2026, 10, 10, 8, tzinfo=UTC)
CSV = b"""timestamp,end,open,high,low,close,vol,closed
2026-08-20T10:00:00+00:00,2026-08-20T11:00:00+00:00,100,102,99,101,1500,true
2026-08-20T11:00:00+00:00,2026-08-20T12:00:00+00:00,101,103,100,102,1600,true
"""


def test_durable_worker_consumes_stage_and_links_the_dataset(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = create_database_engine(f"sqlite+pysqlite:///{tmp_path / 'dataset-file.db'}")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    monkeypatch.setattr(job_handlers, "get_session_factory", lambda: factory)

    preview_request = DatasetFilePreviewRequest(
        name="Durable file dataset",
        source="manual-file",
        pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        timeframe=Timeframe.HOUR_1,
        column_mapping=DatasetColumnMapping(
            open_time="timestamp",
            close_time="end",
            open_price="open",
            high_price="high",
            low_price="low",
            close_price="close",
            volume="vol",
            is_closed="closed",
        ),
    )
    preview = DatasetFileImportService().preview(
        file_name="candles.csv",
        content=CSV,
        request=preview_request,
    )
    commit_request = DatasetFileCommitRequest.model_validate(
        {
            **preview_request.model_dump(),
            "preview_checksum": preview.preview_checksum,
        }
    )
    stage = DatasetFileStageBuilder().build(
        file_name="candles.csv",
        content=CSV,
        request=commit_request,
        now=NOW,
    )
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.DATASET_FILE_IMPORT,
        payload=DatasetFileImportJobPayload(
            stage_id=stage.stage_id,
            file_checksum=stage.file_checksum,
        ).model_dump(mode="json"),
        idempotency_key=build_dataset_file_import_idempotency_key(stage),
        now=NOW,
    )

    with factory() as session:
        submission = SqlAlchemyDatasetFileImportEnqueuer(session).enqueue(
            stage=stage,
            job=job,
        )

    with factory() as session:
        completed = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=build_background_job_handler_registry(),
            worker_id="dataset-file-worker-a",
            lease_duration=timedelta(minutes=5),
        ).run_once()

    assert completed is not None
    assert completed.job_id == submission.job.job_id
    assert completed.status is BackgroundJobStatus.SUCCEEDED
    assert completed.result_reference is not None

    with factory() as session:
        stored = SqlAlchemyDatasetRepository(session).get(completed.result_reference)
        assert stored is not None
        assert stored.checksum == preview.preview_checksum
        assert SqlAlchemyDatasetFileStageRepository(session).get(stage.stage_id) is None

    engine.dispose()
