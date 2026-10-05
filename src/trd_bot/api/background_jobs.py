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
from trd_bot.db.candidate_lifecycle_persistence import (
    SqlAlchemyCandidateLifecycleRecorder,
)
from trd_bot.research import ExperimentExecutionRunner
from trd_bot.research.candidate_application import (
    CandidateApplicationOrchestrator,
)
from trd_bot.research.experiment_candidate_handoff import (
    ExperimentCandidateHandoff,
)
from trd_bot.research.experiment_executions import ExperimentExecutionStatus
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
        execution_repository = SqlAlchemyExperimentExecutionRepository(session)
        dataset_repository = SqlAlchemyDatasetRepository(session)
        experiment_registry = SqlAlchemyExperimentRegistry(session)

        runner = ExperimentExecutionRunner(
            executions=execution_repository,
            datasets=dataset_repository,
            experiments=experiment_registry,
        )

        completed_execution = runner.run(execution_id)

        if completed_execution.status is not ExperimentExecutionStatus.SUCCEEDED:
            return

        candidate_application = CandidateApplicationOrchestrator(
            recorder=SqlAlchemyCandidateLifecycleRecorder(session),
        )
        candidate_handoff = ExperimentCandidateHandoff(
            datasets=dataset_repository,
            experiments=experiment_registry,
            application=candidate_application,
        )

        candidate_handoff.run(completed_execution)


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
