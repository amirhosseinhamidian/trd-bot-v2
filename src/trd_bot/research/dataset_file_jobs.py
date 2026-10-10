import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock
from typing import Final, Protocol
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.jobs import BackgroundJob, BackgroundJobKind, BackgroundJobStatus
from trd_bot.research.dataset_file_imports import (
    MAX_DATASET_FILE_BYTES,
    DatasetFileCommitRequest,
    DatasetFileImportError,
    DatasetFileImportService,
)
from trd_bot.research.datasets import DatasetRepository

DATASET_FILE_STAGE_TTL: Final = timedelta(hours=24)


class DatasetFileStage(BaseModel):
    """Bounded upload content held only until its durable import terminates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_id: str = Field(pattern=r"^dataset-file-stage-[a-f0-9]{20}$")
    file_name: str = Field(min_length=1, max_length=255)
    file_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    content: bytes = Field(min_length=1, max_length=MAX_DATASET_FILE_BYTES)
    request: DatasetFileCommitRequest
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("dataset file stage timestamps must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_stage(self) -> "DatasetFileStage":
        if self.expires_at <= self.created_at:
            raise ValueError("dataset file stage expiry must be after creation")
        actual_checksum = hashlib.sha256(self.content).hexdigest()
        if actual_checksum != self.file_checksum:
            raise ValueError("dataset file stage checksum does not match its content")
        return self


class DatasetFileStageBuilder:
    def build(
        self,
        *,
        file_name: str,
        content: bytes,
        request: DatasetFileCommitRequest,
        now: datetime | None = None,
        ttl: timedelta = DATASET_FILE_STAGE_TTL,
    ) -> DatasetFileStage:
        if ttl <= timedelta(0):
            raise ValueError("dataset file stage TTL must be positive")
        created_at = (now or datetime.now(UTC)).astimezone(UTC)
        descriptor = DatasetFileImportService().describe_upload(
            file_name=file_name,
            content=content,
        )
        return DatasetFileStage(
            stage_id=f"dataset-file-stage-{uuid4().hex[:20]}",
            file_name=descriptor.file_name,
            file_checksum=descriptor.file_checksum,
            content=content,
            request=request,
            created_at=created_at,
            expires_at=created_at + ttl,
        )


class DatasetFileImportJobPayload(BaseModel):
    """Minimal checksum-bound reference consumed by the durable worker."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_id: str = Field(pattern=r"^dataset-file-stage-[a-f0-9]{20}$")
    file_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")


class DatasetFileStageRepository(Protocol):
    def get(self, stage_id: str) -> DatasetFileStage | None: ...
    def delete(self, stage_id: str) -> bool: ...
    def delete_expired(self, *, now: datetime | None = None) -> int: ...


@dataclass(frozen=True)
class DatasetFileImportEnqueueResult:
    job: BackgroundJob
    created: bool


class DatasetFileImportEnqueueError(RuntimeError):
    """Raised when a staged upload and job cannot be committed atomically."""


class DatasetFileImportEnqueuer(Protocol):
    def enqueue(
        self,
        *,
        stage: DatasetFileStage,
        job: BackgroundJob,
    ) -> DatasetFileImportEnqueueResult: ...


def build_dataset_file_import_idempotency_key(stage: DatasetFileStage) -> str:
    intent = {
        "file_checksum": stage.file_checksum,
        "request": stage.request.model_dump(mode="json"),
    }
    encoded = json.dumps(
        intent,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"dataset-file:{hashlib.sha256(encoded).hexdigest()}"


def validate_dataset_file_import_enqueue(
    *,
    stage: DatasetFileStage,
    job: BackgroundJob,
) -> DatasetFileImportJobPayload:
    if job.kind is not BackgroundJobKind.DATASET_FILE_IMPORT:
        raise ValueError("dataset file stage requires a dataset-file-import job")
    if job.status is not BackgroundJobStatus.QUEUED:
        raise ValueError("dataset file import job must be queued")
    if job.idempotency_key is None:
        raise ValueError("dataset file import job requires an idempotency key")

    payload = DatasetFileImportJobPayload.model_validate(job.payload)
    if payload.stage_id != stage.stage_id:
        raise ValueError("dataset file import job does not reference its stage")
    if payload.file_checksum != stage.file_checksum:
        raise ValueError("dataset file import job checksum does not match its stage")
    if job.idempotency_key != build_dataset_file_import_idempotency_key(stage):
        raise ValueError("dataset file import job idempotency key is invalid")
    return payload


class InMemoryDatasetFileImportEnqueuer:
    """Small deterministic adapter for isolated API tests."""

    def __init__(self) -> None:
        self.stages: dict[str, DatasetFileStage] = {}
        self.jobs_by_key: dict[str, BackgroundJob] = {}
        self._lock = RLock()

    def enqueue(
        self,
        *,
        stage: DatasetFileStage,
        job: BackgroundJob,
    ) -> DatasetFileImportEnqueueResult:
        validate_dataset_file_import_enqueue(stage=stage, job=job)
        assert job.idempotency_key is not None
        with self._lock:
            existing = self.jobs_by_key.get(job.idempotency_key)
            if existing is not None:
                return DatasetFileImportEnqueueResult(job=existing, created=False)
            self.stages[stage.stage_id] = stage
            self.jobs_by_key[job.idempotency_key] = job
            return DatasetFileImportEnqueueResult(job=job, created=True)


class DatasetFileImportJobError(RuntimeError):
    def __init__(self, *, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


class DatasetFileImportJobRunner:
    """Revalidate one staged upload and persist its immutable dataset snapshot."""

    def __init__(
        self,
        *,
        stages: DatasetFileStageRepository,
        datasets: DatasetRepository,
    ) -> None:
        self._stages = stages
        self._datasets = datasets

    def run(
        self,
        payload: DatasetFileImportJobPayload,
        *,
        now: datetime | None = None,
        cancellation_requested: bool = False,
    ) -> str | None:
        observed_at = (now or datetime.now(UTC)).astimezone(UTC)
        try:
            stage = self._stages.get(payload.stage_id)
        except ValueError as error:
            self._stages.delete(payload.stage_id)
            raise DatasetFileImportJobError(
                code="dataset_file_stage_corrupt",
                message="Staged dataset upload failed its integrity check.",
            ) from error

        if stage is None:
            raise DatasetFileImportJobError(
                code="dataset_file_stage_missing",
                message="Staged dataset upload is no longer available.",
            )
        if cancellation_requested:
            self._stages.delete(stage.stage_id)
            return None
        if stage.expires_at <= observed_at:
            self._stages.delete(stage.stage_id)
            raise DatasetFileImportJobError(
                code="dataset_file_stage_expired",
                message="Staged dataset upload expired before processing.",
            )
        if stage.file_checksum != payload.file_checksum:
            self._stages.delete(stage.stage_id)
            raise DatasetFileImportJobError(
                code="dataset_file_stage_checksum_mismatch",
                message="Staged dataset upload does not match the queued checksum.",
            )

        try:
            dataset = DatasetFileImportService().build_dataset(
                file_name=stage.file_name,
                content=stage.content,
                request=stage.request,
            )
        except DatasetFileImportError as error:
            self._stages.delete(stage.stage_id)
            raise DatasetFileImportJobError(
                code=f"dataset_file_{error.code.value}",
                message=error.message,
            ) from error

        stored = self._datasets.save(dataset)
        self._stages.delete(stage.stage_id)
        return stored.dataset_id
