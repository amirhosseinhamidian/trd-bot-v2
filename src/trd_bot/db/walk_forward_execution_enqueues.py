from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.walk_forward_execution_repositories import (
    SqlAlchemyWalkForwardExecutionRepository,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobKind
from trd_bot.research.walk_forward_execution_jobs import (
    WalkForwardExecutionEnqueueError,
    WalkForwardExecutionEnqueueResult,
    WalkForwardExecutionJobPayload,
    validate_walk_forward_execution_enqueue,
)
from trd_bot.research.walk_forward_executions import WalkForwardExecution


class SqlAlchemyWalkForwardExecutionEnqueuer:
    """Commit one walk-forward execution and its idempotent job atomically."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._executions = SqlAlchemyWalkForwardExecutionRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        execution: WalkForwardExecution,
        job: BackgroundJob,
    ) -> WalkForwardExecutionEnqueueResult:
        validate_walk_forward_execution_enqueue(execution=execution, job=job)

        try:
            stored_job, created = self._jobs.stage(job)
            if not created:
                return self._existing_result(stored_job)

            stored_execution, execution_created = self._executions.stage(execution)
            if not execution_created:
                raise WalkForwardExecutionEnqueueError("walk-forward execution ID already exists")
            self._session.commit()
            return WalkForwardExecutionEnqueueResult(
                execution=stored_execution,
                job=stored_job,
                created=True,
            )
        except IntegrityError as error:
            self._session.rollback()
            existing = self._find_existing(job)
            if existing is not None:
                return existing
            raise WalkForwardExecutionEnqueueError(
                "walk-forward execution and job could not be committed"
            ) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise WalkForwardExecutionEnqueueError(
                "walk-forward execution and job could not be committed"
            ) from error
        except Exception:
            self._session.rollback()
            raise

    def _find_existing(
        self,
        job: BackgroundJob,
    ) -> WalkForwardExecutionEnqueueResult | None:
        if job.idempotency_key is None:
            return None
        existing_job = self._jobs.get_by_idempotency_key(
            kind=BackgroundJobKind.WALK_FORWARD_EXECUTION,
            idempotency_key=job.idempotency_key,
        )
        if existing_job is None:
            return None
        return self._existing_result(existing_job)

    def _existing_result(
        self,
        job: BackgroundJob,
    ) -> WalkForwardExecutionEnqueueResult:
        payload = WalkForwardExecutionJobPayload.model_validate(job.payload)
        execution = self._executions.get(payload.execution_id)
        if execution is None:
            raise WalkForwardExecutionEnqueueError("walk-forward job exists without its execution")
        return WalkForwardExecutionEnqueueResult(
            execution=execution,
            job=job,
            created=False,
        )
