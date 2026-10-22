from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

import trd_bot.api.background_jobs as background_jobs


@pytest.fixture
def session_factory() -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    try:
        yield sessionmaker(bind=engine)
    finally:
        engine.dispose()


def test_experiment_background_runtime_hands_completed_execution_to_candidates(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:

    execution_repository = object()
    dataset_repository = object()
    experiment_registry = object()
    lifecycle_recorder = object()
    candidate_application = object()

    from types import SimpleNamespace

    from trd_bot.research.experiment_executions import (
        ExperimentExecutionStatus,
    )

    completed_execution = SimpleNamespace(
        status=ExperimentExecutionStatus.SUCCEEDED,
    )

    observed: dict[str, object] = {}

    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentExecutionRepository",
        lambda value: (
            observed.setdefault("execution_repository_session", value),
            execution_repository,
        )[1],
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyDatasetRepository",
        lambda value: (
            observed.setdefault("dataset_repository_session", value),
            dataset_repository,
        )[1],
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentRegistry",
        lambda value: (
            observed.setdefault("experiment_registry_session", value),
            experiment_registry,
        )[1],
    )

    class RecordingExperimentExecutionRunner:
        def __init__(
            self,
            *,
            executions: object,
            datasets: object,
            experiments: object,
        ) -> None:
            assert executions is execution_repository
            assert datasets is dataset_repository
            assert experiments is experiment_registry

        def run(self, execution_id: str) -> object:
            observed["execution_id"] = execution_id
            return completed_execution

    def recording_lifecycle_recorder(value: object) -> object:
        observed["recorder_session"] = value
        return lifecycle_recorder

    def recording_candidate_application(*, recorder: object) -> object:
        assert recorder is lifecycle_recorder
        return candidate_application

    class RecordingCandidateHandoff:
        def __init__(
            self,
            *,
            datasets: object,
            experiments: object,
            application: object,
        ) -> None:
            assert datasets is dataset_repository
            assert experiments is experiment_registry
            assert application is candidate_application

        def run(self, execution: object) -> None:
            observed["handoff_execution"] = execution

    monkeypatch.setattr(
        background_jobs,
        "ExperimentExecutionRunner",
        RecordingExperimentExecutionRunner,
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyCandidateLifecycleRecorder",
        recording_lifecycle_recorder,
        raising=False,
    )
    monkeypatch.setattr(
        background_jobs,
        "CandidateApplicationOrchestrator",
        recording_candidate_application,
        raising=False,
    )
    monkeypatch.setattr(
        background_jobs,
        "ExperimentCandidateHandoff",
        RecordingCandidateHandoff,
        raising=False,
    )

    background_jobs.run_experiment_execution_with_session_factory(
        "execution-1111111111111111",
        session_factory,
    )

    assert observed["execution_id"] == "execution-1111111111111111"

    runtime_session = observed["execution_repository_session"]

    assert isinstance(runtime_session, Session)
    assert observed["dataset_repository_session"] is runtime_session
    assert observed["experiment_registry_session"] is runtime_session

    assert observed["recorder_session"] is runtime_session
    assert observed["handoff_execution"] is completed_execution


def test_failed_experiment_execution_does_not_enter_candidate_stage(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    from types import SimpleNamespace

    from trd_bot.research.experiment_executions import (
        ExperimentExecutionStatus,
    )

    observed: dict[str, object] = {}

    failed_execution = SimpleNamespace(
        status=ExperimentExecutionStatus.FAILED,
    )

    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentExecutionRepository",
        lambda value: object(),
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyDatasetRepository",
        lambda value: object(),
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentRegistry",
        lambda value: object(),
    )

    class FailedExperimentExecutionRunner:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(self, execution_id: str) -> object:
            observed["execution_id"] = execution_id
            return failed_execution

    def unexpected_lifecycle_recorder(value: object) -> object:
        del value
        observed["candidate_stage_started"] = True
        return object()

    monkeypatch.setattr(
        background_jobs,
        "ExperimentExecutionRunner",
        FailedExperimentExecutionRunner,
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyCandidateLifecycleRecorder",
        unexpected_lifecycle_recorder,
    )

    background_jobs.run_experiment_execution_with_session_factory(
        "execution-2222222222222222",
        session_factory,
    )

    assert observed["execution_id"] == "execution-2222222222222222"
    assert "candidate_stage_started" not in observed


def test_candidate_failure_does_not_change_succeeded_experiment_and_can_retry(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
) -> None:
    from tests.test_candidate_application import build_execution_parameters
    from trd_bot.research.experiment_executions import (
        ExperimentExecutionBuilder,
        ExperimentExecutionStateMachine,
        ExperimentExecutionStatus,
    )

    parameters = build_execution_parameters()

    queued = ExperimentExecutionBuilder().build(
        dataset_id="dataset-retry-test",
        parameters=parameters,
    )

    state_machine = ExperimentExecutionStateMachine()
    running = state_machine.start(queued)
    succeeded = state_machine.succeed(
        running,
        experiment_id="experiment-1111111111111111",
    )

    attempts = {"count": 0}

    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentExecutionRepository",
        lambda value: object(),
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyDatasetRepository",
        lambda value: object(),
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyExperimentRegistry",
        lambda value: object(),
    )

    class ExistingSucceededExperimentRunner:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(self, execution_id: str) -> object:
            assert execution_id == "execution-retry-test"
            return succeeded

    def dummy_recorder(value: object) -> object:
        del value
        return object()

    def dummy_application(*, recorder: object) -> object:
        del recorder
        return object()

    class RetryableCandidateHandoff:
        def __init__(self, **kwargs: object) -> None:
            del kwargs

        def run(self, execution: object) -> object:
            assert execution is succeeded

            attempts["count"] += 1

            if attempts["count"] == 1:
                raise RuntimeError("synthetic candidate failure")

            return object()

    monkeypatch.setattr(
        background_jobs,
        "ExperimentExecutionRunner",
        ExistingSucceededExperimentRunner,
    )
    monkeypatch.setattr(
        background_jobs,
        "SqlAlchemyCandidateLifecycleRecorder",
        dummy_recorder,
    )
    monkeypatch.setattr(
        background_jobs,
        "CandidateApplicationOrchestrator",
        dummy_application,
    )
    monkeypatch.setattr(
        background_jobs,
        "ExperimentCandidateHandoff",
        RetryableCandidateHandoff,
    )

    with pytest.raises(
        RuntimeError,
        match="synthetic candidate failure",
    ):
        background_jobs.run_experiment_execution_with_session_factory(
            "execution-retry-test",
            session_factory,
        )

    assert succeeded.status is ExperimentExecutionStatus.SUCCEEDED
    assert attempts["count"] == 1

    # Retry the same completed experiment execution.
    background_jobs.run_experiment_execution_with_session_factory(
        "execution-retry-test",
        session_factory,
    )

    assert succeeded.status is ExperimentExecutionStatus.SUCCEEDED
    assert attempts["count"] == 2
