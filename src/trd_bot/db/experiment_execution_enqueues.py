from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from trd_bot.db.background_job_repositories import SqlAlchemyBackgroundJobRepository
from trd_bot.db.experiment_execution_repositories import (
    SqlAlchemyExperimentExecutionRepository,
)
from trd_bot.jobs import BackgroundJob, BackgroundJobKind
from trd_bot.research.experiment_execution_jobs import (
    ExperimentExecutionEnqueueError,
    ExperimentExecutionEnqueueResult,
    ExperimentExecutionJobPayload,
    validate_experiment_execution_enqueue,
)
from trd_bot.research.experiment_executions import ExperimentExecution


class SqlAlchemyExperimentExecutionEnqueuer:
    """Commit one experiment execution and its idempotent job atomically."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._executions = SqlAlchemyExperimentExecutionRepository(session)
        self._jobs = SqlAlchemyBackgroundJobRepository(session)

    def enqueue(
        self,
        *,
        execution: ExperimentExecution,
        job: BackgroundJob,
    ) -> ExperimentExecutionEnqueueResult:
        validate_experiment_execution_enqueue(execution=execution, job=job)

        try:
            stored_job, created = self._jobs.stage(job)
            if not created:
                return self._existing_result(stored_job)

            stored_execution, execution_created = self._executions.stage(execution)
            if not execution_created:
                raise ExperimentExecutionEnqueueError("experiment execution ID already exists")
            self._session.commit()
            return ExperimentExecutionEnqueueResult(
                execution=stored_execution,
                job=stored_job,
                created=True,
            )
        except IntegrityError as error:
            self._session.rollback()
            existing = self._find_existing(job)
            if existing is not None:
                return existing
            raise ExperimentExecutionEnqueueError(
                "experiment execution and job could not be committed"
            ) from error
        except SQLAlchemyError as error:
            self._session.rollback()
            raise ExperimentExecutionEnqueueError(
                "experiment execution and job could not be committed"
            ) from error
        except Exception:
            self._session.rollback()
            raise

    def _find_existing(
        self,
        job: BackgroundJob,
    ) -> ExperimentExecutionEnqueueResult | None:
        if job.idempotency_key is None:
            return None
        existing_job = self._jobs.get_by_idempotency_key(
            kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
            idempotency_key=job.idempotency_key,
        )
        if existing_job is None:
            return None
        return self._existing_result(existing_job)

    def _existing_result(
        self,
        job: BackgroundJob,
    ) -> ExperimentExecutionEnqueueResult:
        payload = ExperimentExecutionJobPayload.model_validate(job.payload)
        execution = self._executions.get(payload.execution_id)
        if execution is None:
            raise ExperimentExecutionEnqueueError("experiment job exists without its execution")
        return ExperimentExecutionEnqueueResult(
            execution=execution,
            job=job,
            created=False,
        )
