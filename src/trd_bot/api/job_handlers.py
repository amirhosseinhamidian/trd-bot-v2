import asyncio
from collections.abc import Mapping

from pydantic import BaseModel, ValidationError

from trd_bot.api.background_jobs import (
    fail_experiment_execution_with_session_factory,
    fail_walk_forward_execution_with_session_factory,
    run_experiment_execution_with_session_factory,
    run_walk_forward_execution_with_session_factory,
)
from trd_bot.db import (
    SqlAlchemyDatasetFileStageRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyHistoricalDatasetCommitter,
    SqlAlchemyOptimizationExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
    get_session_factory,
)
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.db.market_data_import_repositories import (
    SqlAlchemyMarketDataImportRepository,
)
from trd_bot.db.market_data_polling import SqlAlchemyMarketDataPollJobRunner
from trd_bot.db.market_data_replay import (
    MarketDataReplayError,
    MarketDataReplayRejectedError,
    SqlAlchemyMarketDataReplayRunner,
)
from trd_bot.jobs import (
    PRODUCTION_BACKGROUND_JOB_KINDS,
    BackgroundJobContext,
    BackgroundJobHandlerError,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
)
from trd_bot.market_data import (
    MarketDataPollingFailedError,
    MarketDataPollJobPayload,
    MarketDataProviderCatalog,
    MarketDataReplayJobPayload,
)
from trd_bot.research.dataset_file_jobs import (
    DatasetFileImportJobError,
    DatasetFileImportJobPayload,
    DatasetFileImportJobRunner,
)
from trd_bot.research.experiment_execution_jobs import ExperimentExecutionJobPayload
from trd_bot.research.experiment_executions import ExperimentExecutionStatus
from trd_bot.research.historical_dataset_jobs import (
    HistoricalDatasetJobPayload,
    HistoricalDatasetJobRunner,
)
from trd_bot.research.optimization_executions import OptimizationExecutionState
from trd_bot.research.optimization_jobs import OptimizationExecutionJobPayload
from trd_bot.research.optimization_worker import OptimizationExecutionJobRunner
from trd_bot.research.walk_forward_execution_jobs import WalkForwardExecutionJobPayload
from trd_bot.research.walk_forward_executions import WalkForwardExecutionStatus


def _validate_job_payload[JobPayload: BaseModel](
    model: type[JobPayload],
    payload: Mapping[str, object],
    *,
    error_code: str,
    error_message: str,
) -> JobPayload:
    try:
        return model.model_validate(payload)
    except ValidationError as error:
        raise BackgroundJobHandlerError(
            error_code=error_code,
            error_message=error_message,
            retryable=False,
        ) from error


def run_experiment_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = _validate_job_payload(
        ExperimentExecutionJobPayload,
        payload,
        error_code="invalid_experiment_job_payload",
        error_message="Experiment execution job payload is invalid.",
    )

    def report_progress(progress: int) -> None:
        context.heartbeat(max(progress, context.job.progress_percent))

    report_progress(5)
    session_factory = get_session_factory()
    try:
        execution = run_experiment_execution_with_session_factory(
            request.execution_id,
            session_factory,
            report_progress=report_progress,
            cancellation_requested=context.cancellation_requested,
        )
    except Exception as error:
        if context.job.attempt_count < context.job.max_attempts:
            raise
        terminal = fail_experiment_execution_with_session_factory(
            request.execution_id,
            session_factory,
            error_code="experiment_attempts_exhausted",
            error_message="Experiment execution stopped after exhausting its retry budget.",
        )
        error_code = "experiment_attempts_exhausted"
        error_message = "Experiment execution stopped after exhausting its retry budget."
        if terminal.status is ExperimentExecutionStatus.SUCCEEDED:
            error_code = "experiment_handoff_attempts_exhausted"
            error_message = "Experiment candidate handoff exhausted its retry budget."
        raise BackgroundJobHandlerError(
            error_code=error_code,
            error_message=error_message,
            retryable=False,
        ) from error

    if execution.status is ExperimentExecutionStatus.FAILED:
        raise BackgroundJobHandlerError(
            error_code=execution.error_code or "experiment_execution_failed",
            error_message=execution.error_message or "Experiment execution failed.",
            retryable=False,
        )
    report_progress(98)
    return execution.execution_id


def run_walk_forward_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = _validate_job_payload(
        WalkForwardExecutionJobPayload,
        payload,
        error_code="invalid_walk_forward_job_payload",
        error_message="Walk-forward execution job payload is invalid.",
    )

    def report_progress(progress: int) -> None:
        context.heartbeat(max(progress, context.job.progress_percent))

    report_progress(1)
    session_factory = get_session_factory()
    try:
        execution = run_walk_forward_execution_with_session_factory(
            request.execution_id,
            session_factory,
            report_progress=report_progress,
            cancellation_requested=context.cancellation_requested,
        )
    except Exception as error:
        if context.job.attempt_count < context.job.max_attempts:
            raise
        fail_walk_forward_execution_with_session_factory(
            request.execution_id,
            session_factory,
            error_code="walk_forward_attempts_exhausted",
            error_message="Walk-forward execution stopped after exhausting its retry budget.",
        )
        raise BackgroundJobHandlerError(
            error_code="walk_forward_attempts_exhausted",
            error_message="Walk-forward execution stopped after exhausting its retry budget.",
            retryable=False,
        ) from error

    if execution.status is WalkForwardExecutionStatus.FAILED:
        raise BackgroundJobHandlerError(
            error_code=execution.error_code or "walk_forward_execution_failed",
            error_message=execution.error_message or "Walk-forward execution failed.",
            retryable=False,
        )
    report_progress(99)
    return execution.execution_id


def run_market_data_import_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str | None:
    request = _validate_job_payload(
        HistoricalDatasetJobPayload,
        payload,
        error_code="invalid_market_data_import_job_payload",
        error_message="Market data import job payload is invalid.",
    )
    import_id = (
        f"market-data-import-{context.job.job_id.removeprefix('job-')}-{context.job.attempt_count}"
    )

    def report_progress(progress: int) -> None:
        context.heartbeat(progress)

    with get_session_factory()() as session:
        runner = HistoricalDatasetJobRunner(
            connections=SqlAlchemyMarketDataConnectionRepository(session),
            providers=MarketDataProviderCatalog(),
            datasets=SqlAlchemyDatasetRepository(session),
            history=SqlAlchemyMarketDataImportRepository(session),
            committer=SqlAlchemyHistoricalDatasetCommitter(session),
        )
        record = asyncio.run(
            runner.run(
                payload=request,
                import_id=import_id,
                created_at=context.job.updated_at,
                report_progress=report_progress,
                cancellation_requested=context.cancellation_requested,
            )
        )
    return None if record is None else record.import_id


def run_market_data_poll_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = _validate_job_payload(
        MarketDataPollJobPayload,
        payload,
        error_code="invalid_market_data_poll_job_payload",
        error_message="Market-data poll job payload is invalid.",
    )
    context.heartbeat(5)
    runner = SqlAlchemyMarketDataPollJobRunner(
        session_factory=get_session_factory(),
        providers=MarketDataProviderCatalog(),
    )
    try:
        run = asyncio.run(
            runner.run(
                payload=request,
                job_id=context.job.job_id,
                job_attempt=context.job.attempt_count,
            )
        )
    except MarketDataPollingFailedError as error:
        raise BackgroundJobHandlerError(
            error_code=error.error_code,
            error_message=error.error_message,
            retryable=error.retryable,
        ) from error
    context.heartbeat(95)
    return run.run_id


def run_market_data_replay_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = _validate_job_payload(
        MarketDataReplayJobPayload,
        payload,
        error_code="invalid_market_data_replay_job_payload",
        error_message="Market-data replay job payload is invalid.",
    )
    context.heartbeat(10)
    try:
        with get_session_factory()() as session:
            revision = SqlAlchemyMarketDataReplayRunner(session).apply(
                request.replay_id,
                applied_at=context.job.updated_at,
            )
    except MarketDataReplayRejectedError as error:
        raise BackgroundJobHandlerError(
            error_code="market_data_replay_rejected",
            error_message=str(error),
            retryable=False,
        ) from error
    except MarketDataReplayError as error:
        raise BackgroundJobHandlerError(
            error_code="market_data_replay_failed",
            error_message="Market-data replay could not be committed safely.",
            retryable=True,
        ) from error
    context.heartbeat(95)
    return revision.revision_id


def run_dataset_file_import_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str | None:
    request = _validate_job_payload(
        DatasetFileImportJobPayload,
        payload,
        error_code="invalid_dataset_file_import_job_payload",
        error_message="Dataset file import job payload is invalid.",
    )
    context.heartbeat(10)

    with get_session_factory()() as session:
        runner = DatasetFileImportJobRunner(
            stages=SqlAlchemyDatasetFileStageRepository(session),
            datasets=SqlAlchemyDatasetRepository(session),
        )
        try:
            dataset_id = runner.run(
                request,
                cancellation_requested=context.cancellation_requested(),
            )
        except DatasetFileImportJobError as error:
            raise BackgroundJobHandlerError(
                error_code=error.code,
                error_message=error.message,
                retryable=False,
            ) from error

    if dataset_id is not None:
        context.heartbeat(90)
    return dataset_id


def run_optimization_execution_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = _validate_job_payload(
        OptimizationExecutionJobPayload,
        payload,
        error_code="invalid_optimization_job_payload",
        error_message="Optimization execution job payload is invalid.",
    )

    def report_progress(progress: int) -> None:
        context.heartbeat(progress)

    with get_session_factory()() as session:
        runner = OptimizationExecutionJobRunner(
            executions=SqlAlchemyOptimizationExecutionRepository(session),
            datasets=SqlAlchemyDatasetRepository(session),
            experiments=SqlAlchemyExperimentRegistry(session),
            walk_forward_runs=SqlAlchemyWalkForwardRunRegistry(session),
        )
        try:
            execution = runner.run(
                request.execution_id,
                report_progress=report_progress,
                cancellation_requested=context.cancellation_requested,
            )
        except Exception as error:
            if context.job.attempt_count < context.job.max_attempts:
                raise
            runner.fail_active(
                request.execution_id,
                error_code="optimization_attempts_exhausted",
                error_message="Optimization stopped after exhausting its retry budget.",
            )
            raise BackgroundJobHandlerError(
                error_code="optimization_attempts_exhausted",
                error_message="Optimization stopped after exhausting its retry budget.",
                retryable=False,
            ) from error

    if execution.status is OptimizationExecutionState.FAILED:
        raise BackgroundJobHandlerError(
            error_code=execution.error_code or "optimization_execution_failed",
            error_message=execution.error_message or "Optimization execution failed.",
            retryable=False,
        )
    return execution.execution_id


def build_background_job_handler_registry() -> BackgroundJobHandlerRegistry:
    """Build the production allowlist of durable job handlers."""

    registry = BackgroundJobHandlerRegistry(
        {
            BackgroundJobKind.EXPERIMENT_EXECUTION: run_experiment_job,
            BackgroundJobKind.WALK_FORWARD_EXECUTION: run_walk_forward_job,
            BackgroundJobKind.MARKET_DATA_IMPORT: run_market_data_import_job,
            BackgroundJobKind.MARKET_DATA_POLL: run_market_data_poll_job,
            BackgroundJobKind.MARKET_DATA_REPLAY: run_market_data_replay_job,
            BackgroundJobKind.DATASET_FILE_IMPORT: run_dataset_file_import_job,
            BackgroundJobKind.OPTIMIZATION_EXECUTION: run_optimization_execution_job,
        }
    )
    registry.require_exact_allowlist(PRODUCTION_BACKGROUND_JOB_KINDS)
    return registry
