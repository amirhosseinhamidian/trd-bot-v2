import asyncio
from collections.abc import Mapping
from datetime import timedelta

from trd_bot.api.background_jobs import (
    run_experiment_execution_job,
    run_walk_forward_execution_job,
)
from trd_bot.db import (
    SqlAlchemyDatasetRepository,
    SqlAlchemyHistoricalDatasetCommitter,
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
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
)
from trd_bot.market_data import MarketDataProviderCatalog
from trd_bot.research.historical_dataset_jobs import (
    HistoricalDatasetJobPayload,
    HistoricalDatasetJobRunner,
)

_MARKET_DATA_IMPORT_LEASE = timedelta(minutes=5)


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


def build_background_job_handler_registry() -> BackgroundJobHandlerRegistry:
    """Build the production allowlist; optimization is added in its owning stage."""

    return BackgroundJobHandlerRegistry(
        {
            BackgroundJobKind.EXPERIMENT_EXECUTION: run_experiment_job,
            BackgroundJobKind.WALK_FORWARD_EXECUTION: run_walk_forward_job,
            BackgroundJobKind.MARKET_DATA_IMPORT: run_market_data_import_job,
        }
    )
