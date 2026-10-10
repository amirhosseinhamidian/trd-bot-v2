from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.models import DatasetFileStageRow
from trd_bot.jobs import BackgroundJob, BackgroundJobKind
from trd_bot.research.dataset_file_imports import DatasetFileCommitRequest
from trd_bot.research.dataset_file_jobs import (
    DatasetFileImportEnqueueError,
    DatasetFileImportEnqueueResult,
    DatasetFileStage,
    validate_dataset_file_import_enqueue,
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyDatasetFileStageRepository:
    """Persist bounded staged uploads until a worker consumes or expires them."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, stage: DatasetFileStage) -> DatasetFileStage:
        stored, created = self.stage(stage)
        if not created:
            return stored
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            existing = self.get(stage.stage_id)
            if existing is not None and existing == stage:
                return existing
            raise ValueError("dataset file stage could not be persisted") from error
        return stage

    def stage(self, stage: DatasetFileStage) -> tuple[DatasetFileStage, bool]:
        existing = self.get(stage.stage_id)
        if existing is not None:
            if existing != stage:
                raise ValueError("dataset file stage ID already exists with different content")
            return existing, False
        self._session.add(
            DatasetFileStageRow(
                stage_id=stage.stage_id,
                file_name=stage.file_name,
                file_checksum=stage.file_checksum,
                file_size_bytes=len(stage.content),
                content_bytes=stage.content,
                request_json=stage.request.model_dump_json(),
                created_at=stage.created_at,
                expires_at=stage.expires_at,
            )
        )
        return stage, True

    def get(self, stage_id: str) -> DatasetFileStage | None:
        row = self._session.get(DatasetFileStageRow, stage_id, populate_existing=True)
        if row is None:
            return None
        return DatasetFileStage(
            stage_id=row.stage_id,
            file_name=row.file_name,
            file_checksum=row.file_checksum,
            content=row.content_bytes,
            request=DatasetFileCommitRequest.model_validate_json(row.request_json),
            created_at=_utc(row.created_at),
            expires_at=_utc(row.expires_at),
        )

    def delete(self, stage_id: str) -> bool:
        result = self._session.connection().execute(
            delete(DatasetFileStageRow).where(DatasetFileStageRow.stage_id == stage_id)
        )
        self._session.commit()
        return bool(result.rowcount)

    def delete_expired(self, *, now: datetime | None = None) -> int:
        observed_at = _utc(now or datetime.now(UTC))
        result = self._session.connection().execute(
            delete(DatasetFileStageRow).where(DatasetFileStageRow.expires_at <= observed_at)
        )
        self._session.commit()
        return int(result.rowcount or 0)


class SqlAlchemyDatasetFileImportEnqueuer:
    """Commit one temporary upload and its idempotent durable job atomically."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._stages = SqlAlchemyDatasetFileStageRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        stage: DatasetFileStage,
        job: BackgroundJob,
    ) -> DatasetFileImportEnqueueResult:
        validate_dataset_file_import_enqueue(stage=stage, job=job)
        try:
            self._session.execute(
                delete(DatasetFileStageRow).where(
                    DatasetFileStageRow.expires_at <= stage.created_at
                )
            )
            stored_job, created = self._jobs.stage(job)
            if not created:
                self._session.commit()
                return DatasetFileImportEnqueueResult(job=stored_job, created=False)
            _, stage_created = self._stages.stage(stage)
            if not stage_created:
                raise DatasetFileImportEnqueueError("dataset file stage ID already exists")
            self._session.commit()
            return DatasetFileImportEnqueueResult(job=stored_job, created=True)
        except IntegrityError as error:
            self._session.rollback()
            existing = self._find_existing(job)
            if existing is not None:
                return existing
            raise DatasetFileImportEnqueueError(
                "dataset file stage and job could not be committed"
            ) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise DatasetFileImportEnqueueError(
                "dataset file stage and job could not be committed"
            ) from error
        except Exception:
            self._session.rollback()
            raise

    def _find_existing(
        self,
        job: BackgroundJob,
    ) -> DatasetFileImportEnqueueResult | None:
        if job.idempotency_key is None:
            return None
        existing = self._jobs.get_by_idempotency_key(
            kind=BackgroundJobKind.DATASET_FILE_IMPORT,
            idempotency_key=job.idempotency_key,
        )
        if existing is None:
            return None
        return DatasetFileImportEnqueueResult(job=existing, created=False)
