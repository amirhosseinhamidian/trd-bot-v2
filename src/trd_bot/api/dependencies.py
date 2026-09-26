from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from trd_bot.api.background_jobs import (
    ExperimentExecutionTask,
    WalkForwardExecutionTask,
    run_experiment_execution_job,
    run_walk_forward_execution_job,
)
from trd_bot.db import (
    SqlAlchemyArchitectureRecommendationRepository,
    SqlAlchemyBackgroundJobRepository,
    SqlAlchemyCandidateJournalRepository,
    SqlAlchemyCandidateProjectionRepository,
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyHistoricalDatasetCommitter,
    SqlAlchemyMonitoringRuntimeStateRepository,
    SqlAlchemyOptimizationExecutionEnqueuer,
    SqlAlchemyOptimizationExecutionRepository,
    SqlAlchemySimulatedPortfolioRepository,
    SqlAlchemySystemMetricRepository,
    SqlAlchemyWalkForwardExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
    get_database_session,
)
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.db.market_data_import_repositories import (
    SqlAlchemyMarketDataImportRepository,
)
from trd_bot.jobs import BackgroundJobRepository
from trd_bot.market_data import (
    MarketDataConnectionRepository,
    MarketDataProviderCatalog,
)
from trd_bot.market_data.import_history import MarketDataImportRepository
from trd_bot.monitoring import (
    ArchitectureRecommendationRepository,
    MonitoringRuntimeStateRepository,
    SystemMetricRepository,
)
from trd_bot.paper import SimulatedPortfolioRepository
from trd_bot.research.datasets import DatasetRepository
from trd_bot.research.experiment_executions import ExperimentExecutionRepository
from trd_bot.research.experiments import ExperimentRegistry
from trd_bot.research.historical_dataset_commits import HistoricalDatasetCommitter
from trd_bot.research.optimization_executions import OptimizationExecutionRepository
from trd_bot.research.optimization_jobs import OptimizationExecutionEnqueuer
from trd_bot.research.optimization_runner import OptimizationRunner
from trd_bot.research.policy_presets import AcceptancePolicyPresetCatalog
from trd_bot.research.walk_forward_executions import WalkForwardExecutionRepository
from trd_bot.research.walk_forward_runs import WalkForwardRunRegistry

_acceptance_policy_preset_catalog = AcceptancePolicyPresetCatalog()
_market_data_provider_catalog = MarketDataProviderCatalog()
DatabaseSessionDependency = Annotated[Session, Depends(get_database_session)]


def get_market_data_connection_repository(
    session: DatabaseSessionDependency,
) -> MarketDataConnectionRepository:
    """Return the request-scoped market-data connection repository."""

    return SqlAlchemyMarketDataConnectionRepository(session)


def get_background_job_repository(
    session: DatabaseSessionDependency,
) -> BackgroundJobRepository:
    """Return the request-scoped durable background job repository."""

    return SqlAlchemyBackgroundJobRepository(session)


def get_market_data_import_repository(
    session: DatabaseSessionDependency,
) -> MarketDataImportRepository:
    """Return the request-scoped historical import audit repository."""

    return SqlAlchemyMarketDataImportRepository(session)


def get_market_data_provider_catalog() -> MarketDataProviderCatalog:
    """Return the explicit allowlist of read-only market-data providers."""

    return _market_data_provider_catalog


def get_dataset_repository(
    session: DatabaseSessionDependency,
) -> DatasetRepository:
    """Return the request-scoped dataset repository."""

    return SqlAlchemyDatasetRepository(session)


def get_historical_dataset_committer(
    session: DatabaseSessionDependency,
) -> HistoricalDatasetCommitter:
    """Return the atomic dataset snapshot and import-history committer."""

    return SqlAlchemyHistoricalDatasetCommitter(session)


def get_experiment_registry(
    session: DatabaseSessionDependency,
) -> ExperimentRegistry:
    """Return the request-scoped experiment registry."""

    return SqlAlchemyExperimentRegistry(session)


def get_experiment_execution_repository(
    session: DatabaseSessionDependency,
) -> ExperimentExecutionRepository:
    """Return the request-scoped experiment execution repository."""

    return SqlAlchemyExperimentExecutionRepository(session)


def get_walk_forward_execution_repository(
    session: DatabaseSessionDependency,
) -> WalkForwardExecutionRepository:
    """Return the request-scoped walk-forward execution repository."""

    return SqlAlchemyWalkForwardExecutionRepository(session)


def get_walk_forward_run_registry(
    session: DatabaseSessionDependency,
) -> WalkForwardRunRegistry:
    """Return the request-scoped walk-forward run registry."""

    return SqlAlchemyWalkForwardRunRegistry(session)


def get_simulated_portfolio_repository(
    session: DatabaseSessionDependency,
) -> SimulatedPortfolioRepository:
    """Return the request-scoped offline portfolio repository."""

    return SqlAlchemySimulatedPortfolioRepository(session)


def get_candidate_journal_repository(
    session: DatabaseSessionDependency,
) -> SqlAlchemyCandidateJournalRepository:
    """Return the request-scoped immutable candidate journal repository."""

    return SqlAlchemyCandidateJournalRepository(session)


def get_candidate_projection_repository(
    session: DatabaseSessionDependency,
) -> SqlAlchemyCandidateProjectionRepository:
    """Return the request-scoped persisted candidate projection repository."""

    return SqlAlchemyCandidateProjectionRepository(session)


def get_acceptance_policy_preset_catalog() -> AcceptancePolicyPresetCatalog:
    """Return the built-in read-only historical policy catalog."""

    return _acceptance_policy_preset_catalog


def get_system_metric_repository(
    session: DatabaseSessionDependency,
) -> SystemMetricRepository:
    """Return the request-scoped metric repository."""

    return SqlAlchemySystemMetricRepository(session)


def get_architecture_recommendation_repository(
    session: DatabaseSessionDependency,
) -> ArchitectureRecommendationRepository:
    """Return the request-scoped recommendation repository."""

    return SqlAlchemyArchitectureRecommendationRepository(session)


def get_monitoring_runtime_state_repository(
    session: DatabaseSessionDependency,
) -> MonitoringRuntimeStateRepository:
    """Return the request-scoped monitoring runtime state repository."""

    return SqlAlchemyMonitoringRuntimeStateRepository(session)


def get_experiment_execution_task() -> ExperimentExecutionTask:
    """Return the production experiment background task."""

    return run_experiment_execution_job


def get_walk_forward_execution_task() -> WalkForwardExecutionTask:
    """Return the production walk-forward background task."""

    return run_walk_forward_execution_job


def get_optimization_execution_repository(
    session: DatabaseSessionDependency,
) -> OptimizationExecutionRepository:
    """Return the request-scoped optimization execution repository."""

    return SqlAlchemyOptimizationExecutionRepository(session)


def get_optimization_execution_enqueuer(
    session: DatabaseSessionDependency,
) -> OptimizationExecutionEnqueuer:
    """Return the atomic optimization execution and job enqueuer."""

    return SqlAlchemyOptimizationExecutionEnqueuer(session)


def get_optimization_runner(
    repository: Annotated[
        OptimizationExecutionRepository,
        Depends(get_optimization_execution_repository),
    ],
) -> OptimizationRunner:
    """Return an optimization runner sharing the request-scoped repository."""

    return OptimizationRunner(repository)
