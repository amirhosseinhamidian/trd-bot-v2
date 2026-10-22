from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.optimization_execution_repositories import (
    SqlAlchemyOptimizationExecutionRepository,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobKind
from trd_bot.research.optimization_executions import OptimizationExecution
from trd_bot.research.optimization_jobs import (
    OptimizationExecutionEnqueueError,
    OptimizationExecutionEnqueueResult,
    OptimizationExecutionJobPayload,
    validate_optimization_execution_enqueue,
)


class SqlAlchemyOptimizationExecutionEnqueuer:
    """Commit one optimization execution and idempotent job atomically."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._executions = SqlAlchemyOptimizationExecutionRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        execution: OptimizationExecution,
        job: BackgroundJob,
    ) -> OptimizationExecutionEnqueueResult:
        validate_optimization_execution_enqueue(execution=execution, job=job)

        try:
            stored_job, created = self._jobs.stage(job)
            if not created:
                return self._existing_result(stored_job)

            stored_execution, execution_created = self._executions.stage(execution)
            if not execution_created:
                raise OptimizationExecutionEnqueueError("optimization execution ID already exists")
            self._session.commit()
            return OptimizationExecutionEnqueueResult(
                execution=stored_execution,
                job=stored_job,
                created=True,
            )
        except IntegrityError as error:
            self._session.rollback()
            existing = self._find_existing(job)
            if existing is not None:
                return existing
            raise OptimizationExecutionEnqueueError(
                "optimization execution and job could not be committed"
            ) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise OptimizationExecutionEnqueueError(
                "optimization execution and job could not be committed"
            ) from error
        except Exception:
            self._session.rollback()
            raise

    def _find_existing(
        self,
        job: BackgroundJob,
    ) -> OptimizationExecutionEnqueueResult | None:
        if job.idempotency_key is None:
            return None
        existing_job = self._jobs.get_by_idempotency_key(
            kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
            idempotency_key=job.idempotency_key,
        )
        if existing_job is None:
            return None
        return self._existing_result(existing_job)

    def _existing_result(
        self,
        job: BackgroundJob,
    ) -> OptimizationExecutionEnqueueResult:
        payload = OptimizationExecutionJobPayload.model_validate(job.payload)
        execution = self._executions.get(payload.execution_id)
        if execution is None:
            raise OptimizationExecutionEnqueueError("optimization job exists without its execution")
        return OptimizationExecutionEnqueueResult(
            execution=execution,
            job=job,
            created=False,
        )
