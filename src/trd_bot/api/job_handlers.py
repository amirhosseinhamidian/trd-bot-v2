import asyncio
from collections.abc import Mapping
from datetime import timedelta

from trd_bot.api.background_jobs import (
    run_experiment_execution_job,
    run_walk_forward_execution_job,
)
from trd_bot.db import (
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
from trd_bot.jobs import (
    BackgroundJobContext,
    BackgroundJobHandlerError,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
)
from trd_bot.market_data import MarketDataProviderCatalog
from trd_bot.research.historical_dataset_jobs import (
    HistoricalDatasetJobPayload,
    HistoricalDatasetJobRunner,
)
from trd_bot.research.optimization_executions import OptimizationExecutionState
from trd_bot.research.optimization_jobs import OptimizationExecutionJobPayload
from trd_bot.research.optimization_worker import OptimizationExecutionJobRunner

_MARKET_DATA_IMPORT_LEASE = timedelta(minutes=5)
_OPTIMIZATION_EXECUTION_LEASE = timedelta(minutes=5)


def _required_string(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'background job payload requires string field "{field}"')
    return value.strip()


def run_experiment_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    execution_id = _required_string(payload, "execution_id")
    if context.cancellation_requested():
        return execution_id
    run_experiment_execution_job(execution_id)
    return execution_id


def run_walk_forward_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    execution_id = _required_string(payload, "execution_id")
    if context.cancellation_requested():
        return execution_id
    run_walk_forward_execution_job(execution_id)
    return execution_id


def run_market_data_import_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str | None:
    request = HistoricalDatasetJobPayload.model_validate(payload)
    import_id = (
        f"market-data-import-{context.job.job_id.removeprefix('job-')}-{context.job.attempt_count}"
    )

    def report_progress(progress: int) -> None:
        context.heartbeat(
            progress,
            lease_duration=_MARKET_DATA_IMPORT_LEASE,
        )

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


def run_optimization_execution_job(
    context: BackgroundJobContext,
    payload: Mapping[str, object],
) -> str:
    request = OptimizationExecutionJobPayload.model_validate(payload)

    def report_progress(progress: int) -> None:
        context.heartbeat(
            progress,
            lease_duration=_OPTIMIZATION_EXECUTION_LEASE,
        )

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

    return BackgroundJobHandlerRegistry(
        {
            BackgroundJobKind.EXPERIMENT_EXECUTION: run_experiment_job,
            BackgroundJobKind.WALK_FORWARD_EXECUTION: run_walk_forward_job,
            BackgroundJobKind.MARKET_DATA_IMPORT: run_market_data_import_job,
            BackgroundJobKind.OPTIMIZATION_EXECUTION: run_optimization_execution_job,
        }
    )
