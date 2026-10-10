import hashlib
from datetime import UTC, datetime, timedelta

import pytest

from trd_bot.domain import Timeframe, TradingPair
from trd_bot.jobs import BackgroundJobBuilder, BackgroundJobKind
from trd_bot.research import (
    DatasetColumnMapping,
    DatasetFileCommitRequest,
    DatasetFileImportJobError,
    DatasetFileImportJobPayload,
    DatasetFileImportJobRunner,
    DatasetFileImportService,
    DatasetFilePreviewRequest,
    DatasetFileStage,
    DatasetFileStageBuilder,
    InMemoryDatasetRepository,
    build_dataset_file_import_idempotency_key,
    validate_dataset_file_import_enqueue,
)

NOW = datetime(2026, 10, 10, 8, tzinfo=UTC)
CSV = b"""timestamp,end,open,high,low,close,vol,closed
2026-08-20T10:00:00+00:00,2026-08-20T11:00:00+00:00,100,102,99,101,1500,true
2026-08-20T11:00:00+00:00,2026-08-20T12:00:00+00:00,101,103,100,102,1600,true
"""


class MemoryStages:
    def __init__(self, stage: DatasetFileStage) -> None:
        self.items = {stage.stage_id: stage}

    def get(self, stage_id: str) -> DatasetFileStage | None:
        return self.items.get(stage_id)

    def delete(self, stage_id: str) -> bool:
        return self.items.pop(stage_id, None) is not None

    def delete_expired(self, *, now: datetime | None = None) -> int:
        observed_at = now or datetime.now(UTC)
        expired = [key for key, value in self.items.items() if value.expires_at <= observed_at]
        for key in expired:
            del self.items[key]
        return len(expired)


def preview_request() -> DatasetFilePreviewRequest:
    return DatasetFilePreviewRequest(
        name="Uploaded BTC dataset",
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


def commit_request(*, checksum: str | None = None) -> DatasetFileCommitRequest:
    request = preview_request()
    preview = DatasetFileImportService().preview(
        file_name="candles.csv",
        content=CSV,
        request=request,
    )
    return DatasetFileCommitRequest.model_validate(
        {
            **request.model_dump(),
            "preview_checksum": checksum or preview.preview_checksum,
        }
    )


def build_stage(
    *,
    request: DatasetFileCommitRequest | None = None,
    ttl: timedelta = timedelta(hours=24),
) -> DatasetFileStage:
    return DatasetFileStageBuilder().build(
        file_name="../../candles.csv",
        content=CSV,
        request=request or commit_request(),
        now=NOW,
        ttl=ttl,
    )


def payload(stage: DatasetFileStage) -> DatasetFileImportJobPayload:
    return DatasetFileImportJobPayload(
        stage_id=stage.stage_id,
        file_checksum=stage.file_checksum,
    )


def test_stage_builder_bounds_and_sanitizes_the_upload() -> None:
    stage = build_stage()

    assert stage.file_name == "candles.csv"
    assert stage.file_checksum == hashlib.sha256(CSV).hexdigest()
    assert stage.created_at == NOW
    assert stage.expires_at == NOW + timedelta(hours=24)


def test_job_payload_is_bound_to_stage_checksum_and_import_intent() -> None:
    stage = build_stage()
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.DATASET_FILE_IMPORT,
        payload=payload(stage).model_dump(mode="json"),
        idempotency_key=build_dataset_file_import_idempotency_key(stage),
        now=NOW,
    )

    validated = validate_dataset_file_import_enqueue(stage=stage, job=job)

    assert validated.stage_id == stage.stage_id
    assert validated.file_checksum == stage.file_checksum


def test_runner_revalidates_persists_and_removes_the_stage() -> None:
    stage = build_stage()
    stages = MemoryStages(stage)
    datasets = InMemoryDatasetRepository()

    dataset_id = DatasetFileImportJobRunner(stages=stages, datasets=datasets).run(
        payload(stage),
        now=NOW + timedelta(minutes=1),
    )

    assert dataset_id is not None
    stored = datasets.get(dataset_id)
    assert stored is not None
    assert stored.provenance.original_filename == "candles.csv"
    assert stages.get(stage.stage_id) is None


def test_runner_fails_closed_and_cleans_up_a_stale_preview() -> None:
    stage = build_stage(request=commit_request(checksum="0" * 64))
    stages = MemoryStages(stage)

    with pytest.raises(DatasetFileImportJobError) as captured:
        DatasetFileImportJobRunner(
            stages=stages,
            datasets=InMemoryDatasetRepository(),
        ).run(payload(stage), now=NOW + timedelta(minutes=1))

    assert captured.value.code == "dataset_file_preview_mismatch"
    assert stages.get(stage.stage_id) is None


def test_runner_rejects_and_removes_an_expired_stage() -> None:
    stage = build_stage(ttl=timedelta(minutes=1))
    stages = MemoryStages(stage)

    with pytest.raises(DatasetFileImportJobError) as captured:
        DatasetFileImportJobRunner(
            stages=stages,
            datasets=InMemoryDatasetRepository(),
        ).run(payload(stage), now=NOW + timedelta(minutes=2))

    assert captured.value.code == "dataset_file_stage_expired"
    assert stages.get(stage.stage_id) is None


def test_runner_cleans_up_a_cancelled_stage_without_persisting() -> None:
    stage = build_stage()
    stages = MemoryStages(stage)
    datasets = InMemoryDatasetRepository()

    result = DatasetFileImportJobRunner(stages=stages, datasets=datasets).run(
        payload(stage),
        now=NOW,
        cancellation_requested=True,
    )

    assert result is None
    assert datasets.count() == 0
    assert stages.get(stage.stage_id) is None
