from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    SqlAlchemyDatasetRepository,
    SqlAlchemyExperimentExecutionRepository,
    SqlAlchemyExperimentRegistry,
    SqlAlchemyWalkForwardExecutionRepository,
    SqlAlchemyWalkForwardRunRegistry,
    get_session_factory,
)
from trd_bot.research import ExperimentExecutionRunner
from trd_bot.research.walk_forward_execution_runner import (
    WalkForwardExecutionRunner,
)

ExperimentExecutionTask = Callable[[str], None]
WalkForwardExecutionTask = Callable[[str], None]


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


def run_walk_forward_execution_with_session_factory(
    execution_id: str,
    session_factory: sessionmaker[Session],
) -> None:
    """Run one walk-forward execution using an explicit session factory."""

    with session_factory() as session:
        runner = WalkForwardExecutionRunner(
            executions=SqlAlchemyWalkForwardExecutionRepository(session),
            datasets=SqlAlchemyDatasetRepository(session),
            runs=SqlAlchemyWalkForwardRunRegistry(session),
        )

        runner.run(execution_id)


def run_walk_forward_execution_job(
    execution_id: str,
) -> None:
    """Run one walk-forward execution using the configured database."""

    run_walk_forward_execution_with_session_factory(
        execution_id,
        get_session_factory(),
    )
