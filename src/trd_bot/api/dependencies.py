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
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemySystemMetricRepository,
    SqlAlchemyWalkForwardExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
    get_database_session,
)
from trd_bot.monitoring import (
    ArchitectureRecommendationRepository,
    SystemMetricRepository,
)
from trd_bot.research import (
    AcceptancePolicyPresetCatalog,
    DatasetRepository,
    ExperimentExecutionRepository,
    ExperimentRegistry,
    WalkForwardRunRegistry,
)
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecutionRepository,
)

_acceptance_policy_preset_catalog = AcceptancePolicyPresetCatalog()
DatabaseSessionDependency = Annotated[Session, Depends(get_database_session)]


def get_dataset_repository(
    session: DatabaseSessionDependency,
) -> DatasetRepository:
    """Return the request-scoped dataset repository."""

    return SqlAlchemyDatasetRepository(session)


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


def get_experiment_execution_task() -> ExperimentExecutionTask:
    """Return the production experiment background task."""

    return run_experiment_execution_job


def get_walk_forward_execution_task() -> WalkForwardExecutionTask:
    """Return the production walk-forward background task."""

    return run_walk_forward_execution_job
