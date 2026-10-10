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
from trd_bot.research.experiment_executions import (
    ExperimentExecution,
    ExperimentExecutionStatus,
)
from trd_bot.research.walk_forward_execution_runner import (
    WalkForwardExecutionRunner,
)

WalkForwardExecutionTask = Callable[[str], None]


def run_experiment_execution_with_session_factory(
    execution_id: str,
    session_factory: sessionmaker[Session],
    *,
    report_progress: Callable[[int], None] | None = None,
    cancellation_requested: Callable[[], bool] | None = None,
) -> ExperimentExecution:
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

        if report_progress is None and cancellation_requested is None:
            completed_execution = runner.run(execution_id)
        else:
            completed_execution = runner.run(
                execution_id,
                report_progress=report_progress,
                cancellation_requested=cancellation_requested,
            )

        if completed_execution.status is not ExperimentExecutionStatus.SUCCEEDED:
            return completed_execution

        candidate_application = CandidateApplicationOrchestrator(
            recorder=SqlAlchemyCandidateLifecycleRecorder(session),
        )
        candidate_handoff = ExperimentCandidateHandoff(
            datasets=dataset_repository,
            experiments=experiment_registry,
            application=candidate_application,
        )

        candidate_handoff.run(completed_execution)
        return completed_execution


def fail_experiment_execution_with_session_factory(
    execution_id: str,
    session_factory: sessionmaker[Session],
    *,
    error_code: str,
    error_message: str,
) -> ExperimentExecution:
    """Fail a non-terminal execution after its durable retry budget is exhausted."""

    with session_factory() as session:
        runner = ExperimentExecutionRunner(
            executions=SqlAlchemyExperimentExecutionRepository(session),
            datasets=SqlAlchemyDatasetRepository(session),
            experiments=SqlAlchemyExperimentRegistry(session),
        )
        return runner.fail_active(
            execution_id,
            error_code=error_code,
            error_message=error_message,
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
