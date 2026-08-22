from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from trd_bot.db import (
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyWalkForwardRunRegistry,
    get_database_session,
)
from trd_bot.research import (
    AcceptancePolicyPresetCatalog,
    DatasetRepository,
    ExperimentRegistry,
    WalkForwardRunRegistry,
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


def get_walk_forward_run_registry(
    session: DatabaseSessionDependency,
) -> WalkForwardRunRegistry:
    """Return the request-scoped walk-forward run registry."""

    return SqlAlchemyWalkForwardRunRegistry(session)


def get_acceptance_policy_preset_catalog() -> AcceptancePolicyPresetCatalog:
    """Return the built-in read-only historical policy catalog."""

    return _acceptance_policy_preset_catalog
