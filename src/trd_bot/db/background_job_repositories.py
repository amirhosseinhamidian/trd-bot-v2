from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import BackgroundJobRow
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobStatus,
)
from trd_bot.jobs import (
    BackgroundJobConflictError as BackgroundJobConflictError,
)


class SqlAlchemyBackgroundJobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue(self, job: BackgroundJob) -> tuple[BackgroundJob, bool]:
        if job.idempotency_key is not None:
            existing = self._session.scalar(
                select(BackgroundJobRow)
                .where(
                    BackgroundJobRow.kind == job.kind.value,
                    BackgroundJobRow.idempotency_key == job.idempotency_key,
                )
                .execution_options(populate_existing=True)
            )
            if existing is not None:
                return self._from_row(existing), False

        self._session.add(self._new_row(job))
        try:
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            if job.idempotency_key is None:
                raise ValueError("background job could not be enqueued") from error
            existing = self._session.scalar(
                select(BackgroundJobRow)
                .where(
                    BackgroundJobRow.kind == job.kind.value,
                    BackgroundJobRow.idempotency_key == job.idempotency_key,
                )
                .execution_options(populate_existing=True)
            )
            if existing is None:
                raise ValueError("background job could not be enqueued") from error
            return self._from_row(existing), False
        return job, True

    def get(self, job_id: str) -> BackgroundJob | None:
        row = self._session.get(BackgroundJobRow, job_id, populate_existing=True)
        return None if row is None else self._from_row(row)

    def count(self, *, statuses: Sequence[BackgroundJobStatus] | None = None) -> int:
        statement = select(func.count()).select_from(BackgroundJobRow)
        if statuses:
            statement = statement.where(
                BackgroundJobRow.status.in_([status.value for status in statuses])
            )
        return int(self._session.scalar(statement) or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        statuses: Sequence[BackgroundJobStatus] | None = None,
    ) -> tuple[BackgroundJob, ...]:
        if limit <= 0 or limit > 100:
            raise ValueError("background job page limit must be between 1 and 100")
        if offset < 0:
            raise ValueError("background job page offset cannot be negative")
        statement = select(BackgroundJobRow)
        if statuses:
            statement = statement.where(
                BackgroundJobRow.status.in_([status.value for status in statuses])
            )
        rows = self._session.scalars(
            statement.order_by(
                BackgroundJobRow.created_at.desc(),
                BackgroundJobRow.job_id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .execution_options(populate_existing=True)
        ).all()
        return tuple(self._from_row(row) for row in rows)

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> BackgroundJob | None:
        claimed_at = self._now(now)
        if not worker_id.strip() or lease_duration <= timedelta(0):
            raise ValueError("worker ID and lease duration must be valid")

        while True:
            row = self._session.scalar(
                select(BackgroundJobRow)
                .where(
                    or_(
                        and_(
                            BackgroundJobRow.status == BackgroundJobStatus.QUEUED.value,
                            BackgroundJobRow.run_after <= claimed_at,
                        ),
                        and_(
                            BackgroundJobRow.status == BackgroundJobStatus.RUNNING.value,
                            BackgroundJobRow.lease_expires_at <= claimed_at,
                        ),
                    )
                )
                .order_by(BackgroundJobRow.run_after, BackgroundJobRow.created_at)
                .with_for_update(skip_locked=True)
                .limit(1)
                .execution_options(populate_existing=True)
            )
            if row is None:
                self._session.rollback()
                return None

            current = self._from_row(row)
            if current.cancel_requested:
                self._persist(row, self._cancelled(current, claimed_at))
                continue
            if current.attempt_count >= current.max_attempts:
                exhausted = current.model_copy(
                    update={
                        "status": BackgroundJobStatus.FAILED,
                        "lease_owner": None,
                        "lease_expires_at": None,
                        "error_code": "attempts_exhausted",
                        "error_message": "background job lease expired after the final attempt",
                        "updated_at": claimed_at,
                        "finished_at": claimed_at,
                    }
                )
                self._update_row(row, exhausted)
                self._session.commit()
                continue

            claimed = current.model_copy(
                update={
                    "status": BackgroundJobStatus.RUNNING,
                    "attempt_count": current.attempt_count + 1,
                    "lease_owner": worker_id.strip(),
                    "lease_expires_at": claimed_at + lease_duration,
                    "started_at": current.started_at or claimed_at,
                    "updated_at": claimed_at,
                    "finished_at": None,
                    "error_code": None,
                    "error_message": None,
                }
            )
            claimed = BackgroundJob.model_validate(claimed.model_dump())
            self._update_row(row, claimed)
            self._session.commit()
            return claimed

    def heartbeat(
        self,
        *,
        job_id: str,
        worker_id: str,
        progress_percent: int,
        lease_duration: timedelta,
        now: datetime | None = None,
    ) -> BackgroundJob:
        heartbeat_at = self._now(now)
        if lease_duration <= timedelta(0):
            raise ValueError("background job lease duration must be positive")
        row, current = self._owned_running(job_id, worker_id, heartbeat_at)
        if progress_percent < current.progress_percent or not 0 <= progress_percent < 100:
            raise ValueError("background job progress must be monotonic and below 100")
        updated = current.model_copy(
            update={
                "progress_percent": progress_percent,
                "lease_expires_at": heartbeat_at + lease_duration,
                "updated_at": heartbeat_at,
            }
        )
        updated = BackgroundJob.model_validate(updated.model_dump())
        return self._persist(row, updated)

    def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        result_reference: str | None = None,
        now: datetime | None = None,
    ) -> BackgroundJob:
        finished_at = self._now(now)
        row, current = self._owned_running(job_id, worker_id, finished_at)
        if current.cancel_requested:
            return self._persist(row, self._cancelled(current, finished_at))
        succeeded = current.model_copy(
            update={
                "status": BackgroundJobStatus.SUCCEEDED,
                "progress_percent": 100,
                "lease_owner": None,
                "lease_expires_at": None,
                "result_reference": result_reference,
                "updated_at": finished_at,
                "finished_at": finished_at,
            }
        )
        return self._persist(row, BackgroundJob.model_validate(succeeded.model_dump()))

    def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        error_code: str,
        error_message: str,
        retryable: bool,
        retry_delay: timedelta | None = None,
        now: datetime | None = None,
    ) -> BackgroundJob:
        failed_at = self._now(now)
        delay = retry_delay or timedelta(0)
        if delay < timedelta(0):
            raise ValueError("background job retry delay cannot be negative")
        row, current = self._owned_running(job_id, worker_id, failed_at)
        if current.cancel_requested:
            return self._persist(row, self._cancelled(current, failed_at))
        if retryable and current.attempt_count < current.max_attempts:
            queued = current.model_copy(
                update={
                    "status": BackgroundJobStatus.QUEUED,
                    "progress_percent": 0,
                    "lease_owner": None,
                    "lease_expires_at": None,
                    "run_after": failed_at + delay,
                    "updated_at": failed_at,
                }
            )
            return self._persist(row, BackgroundJob.model_validate(queued.model_dump()))
        failed = current.model_copy(
            update={
                "status": BackgroundJobStatus.FAILED,
                "lease_owner": None,
                "lease_expires_at": None,
                "error_code": error_code,
                "error_message": error_message[:500],
                "updated_at": failed_at,
                "finished_at": failed_at,
            }
        )
        return self._persist(row, BackgroundJob.model_validate(failed.model_dump()))

    def request_cancel(self, job_id: str, *, now: datetime | None = None) -> BackgroundJob:
        requested_at = self._now(now)
        row = self._locked_row(job_id)
        if row is None:
            raise KeyError(job_id)
        current = self._from_row(row)
        if current.is_terminal:
            return current
        if current.status is BackgroundJobStatus.QUEUED:
            return self._persist(row, self._cancelled(current, requested_at))
        updated = current.model_copy(update={"cancel_requested": True, "updated_at": requested_at})
        return self._persist(row, BackgroundJob.model_validate(updated.model_dump()))

    def retry_failed(self, job_id: str, *, now: datetime | None = None) -> BackgroundJob:
        retried_at = self._now(now)
        row = self._locked_row(job_id)
        if row is None:
            raise KeyError(job_id)
        current = self._from_row(row)
        if current.status is not BackgroundJobStatus.FAILED:
            raise ValueError("only failed background jobs can be retried")
        if current.attempt_count >= 10:
            raise ValueError("background job reached the hard attempt limit")
        retried = current.model_copy(
            update={
                "status": BackgroundJobStatus.QUEUED,
                "progress_percent": 0,
                "max_attempts": current.attempt_count + 1,
                "run_after": retried_at,
                "cancel_requested": False,
                "result_reference": None,
                "error_code": None,
                "error_message": None,
                "updated_at": retried_at,
                "finished_at": None,
            }
        )
        return self._persist(row, BackgroundJob.model_validate(retried.model_dump()))

    def _owned_running(
        self, job_id: str, worker_id: str, now: datetime
    ) -> tuple[BackgroundJobRow, BackgroundJob]:
        row = self._locked_row(job_id)
        if row is None:
            raise KeyError(job_id)
        job = self._from_row(row)
        if (
            job.status is not BackgroundJobStatus.RUNNING
            or job.lease_owner != worker_id
            or job.lease_expires_at is None
            or job.lease_expires_at <= now
        ):
            raise BackgroundJobConflictError("background job lease is not owned by this worker")
        return row, job

    def _locked_row(self, job_id: str) -> BackgroundJobRow | None:
        return self._session.scalar(
            select(BackgroundJobRow)
            .where(BackgroundJobRow.job_id == job_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def _persist(self, row: BackgroundJobRow, job: BackgroundJob) -> BackgroundJob:
        self._update_row(row, job)
        self._session.commit()
        return job

    @staticmethod
    def _cancelled(job: BackgroundJob, now: datetime) -> BackgroundJob:
        cancelled = job.model_copy(
            update={
                "status": BackgroundJobStatus.CANCELLED,
                "lease_owner": None,
                "lease_expires_at": None,
                "cancel_requested": True,
                "updated_at": now,
                "finished_at": now,
            }
        )
        return BackgroundJob.model_validate(cancelled.model_dump())

    @staticmethod
    def _now(value: datetime | None) -> datetime:
        current = value or datetime.now(UTC)
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("background job operation time must include timezone")
        return current.astimezone(UTC)

    @staticmethod
    def _from_row(row: BackgroundJobRow) -> BackgroundJob:
        return BackgroundJob.model_validate_json(row.payload_json)

    @staticmethod
    def _new_row(job: BackgroundJob) -> BackgroundJobRow:
        row = BackgroundJobRow(job_id=job.job_id)
        SqlAlchemyBackgroundJobRepository._update_row(row, job)
        return row

    @staticmethod
    def _update_row(row: BackgroundJobRow, job: BackgroundJob) -> None:
        row.kind = job.kind.value
        row.status = job.status.value
        row.progress_percent = job.progress_percent
        row.attempt_count = job.attempt_count
        row.max_attempts = job.max_attempts
        row.idempotency_key = job.idempotency_key
        row.run_after = job.run_after
        row.lease_owner = job.lease_owner
        row.lease_expires_at = job.lease_expires_at
        row.cancel_requested = job.cancel_requested
        row.created_at = job.created_at
        row.updated_at = job.updated_at
        row.started_at = job.started_at
        row.finished_at = job.finished_at
        row.payload_json = job.model_dump_json()
