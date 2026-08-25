from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionRepository,
    SqlAlchemyExperimentRegistry,
    get_session_factory,
)
from trd_bot.research import ExperimentExecutionRunner

ExperimentExecutionTask = Callable[[str], None]


def run_experiment_execution_with_session_factory(
    execution_id: str,
    session_factory: sessionmaker[Session],
) -> None:
    """Run one historical experiment using an explicit session factory."""

    with session_factory() as session:
        runner = ExperimentExecutionRunner(
            executions=SqlAlchemyExperimentExecutionRepository(session),
            datasets=SqlAlchemyDatasetRepository(session),
            experiments=SqlAlchemyExperimentRegistry(session),
        )

        runner.run(execution_id)


def run_experiment_execution_job(
    execution_id: str,
) -> None:
    """Run one historical experiment using the configured database."""

    run_experiment_execution_with_session_factory(
        execution_id,
        get_session_factory(),
    )
