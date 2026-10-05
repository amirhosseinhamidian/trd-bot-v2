import pytest

from tests.test_candidate_application import build_execution_parameters
from tests.test_experiment_replay import build_experiment
from trd_bot.research.candidate_application import (
    CandidateApplicationResult,
    CandidateApplicationStatus,
)
from trd_bot.research.datasets import (
    DatasetSnapshot,
    InMemoryDatasetRepository,
)
from trd_bot.research.experiment_candidate_handoff import (
    ExperimentCandidateHandoff,
)
from trd_bot.research.experiment_executions import (
    ExperimentExecutionBuilder,
    ExperimentExecutionStateMachine,
    HistoricalExecutionParameters,
)
from trd_bot.research.experiments import (
    InMemoryExperimentRegistry,
    ResearchExperiment,
)


class RecordingCandidateApplication:
    def __init__(self) -> None:
        self.call: dict[str, object] | None = None
        self.result: CandidateApplicationResult | None = None

    def run(
        self,
        *,
        experiment: ResearchExperiment,
        dataset: DatasetSnapshot,
        parameters: HistoricalExecutionParameters,
    ) -> CandidateApplicationResult:
        self.call = {
            "experiment": experiment,
            "dataset": dataset,
            "parameters": parameters,
        }

        self.result = CandidateApplicationResult(
            status=CandidateApplicationStatus.NO_CANDIDATES,
            experiment_id=experiment.experiment_id,
            dataset_id=dataset.dataset_id,
            generated_candidate_count=0,
            evaluated_at=None,
            ranking=None,
            lifecycle=None,
            journal=None,
        )

        return self.result


def test_hands_succeeded_execution_to_candidate_application() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()

    datasets.save(dataset)
    experiments.save(experiment)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=parameters,
    )

    state_machine = ExperimentExecutionStateMachine()
    running = state_machine.start(queued)
    succeeded = state_machine.succeed(
        running,
        experiment_id=experiment.experiment_id,
    )

    application = RecordingCandidateApplication()

    result = ExperimentCandidateHandoff(
        datasets=datasets,
        experiments=experiments,
        application=application,
    ).run(succeeded)

    assert result is application.result
    assert application.call is not None

    assert application.call["dataset"] == dataset
    assert application.call["experiment"] == experiment

    # Important: do not reconstruct execution parameters.
    assert application.call["parameters"] is succeeded.parameters


def test_rejects_non_succeeded_executions_before_candidate_processing() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()

    datasets.save(dataset)
    experiments.save(experiment)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=parameters,
    )

    state_machine = ExperimentExecutionStateMachine()
    running = state_machine.start(queued)
    failed = state_machine.fail(
        running,
        error_code="test_failure",
        error_message="Synthetic execution failure.",
    )

    for execution in (queued, running, failed):
        application = RecordingCandidateApplication()

        with pytest.raises(
            ValueError,
            match="candidate handoff requires a succeeded execution",
        ):
            ExperimentCandidateHandoff(
                datasets=datasets,
                experiments=experiments,
                application=application,
            ).run(execution)

        assert application.call is None


def test_does_not_run_candidate_application_when_dataset_is_missing() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()
    experiments.save(experiment)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=parameters,
    )
    running = ExperimentExecutionStateMachine().start(queued)
    succeeded = ExperimentExecutionStateMachine().succeed(
        running,
        experiment_id=experiment.experiment_id,
    )

    application = RecordingCandidateApplication()

    with pytest.raises(
        ValueError,
        match="candidate handoff dataset not found",
    ):
        ExperimentCandidateHandoff(
            datasets=datasets,
            experiments=experiments,
            application=application,
        ).run(succeeded)

    assert application.call is None


def test_does_not_run_candidate_application_when_experiment_is_missing() -> None:
    dataset, experiment = build_experiment()
    parameters = build_execution_parameters()

    datasets = InMemoryDatasetRepository()
    experiments = InMemoryExperimentRegistry()
    datasets.save(dataset)

    queued = ExperimentExecutionBuilder().build(
        dataset_id=dataset.dataset_id,
        parameters=parameters,
    )
    running = ExperimentExecutionStateMachine().start(queued)
    succeeded = ExperimentExecutionStateMachine().succeed(
        running,
        experiment_id=experiment.experiment_id,
    )

    application = RecordingCandidateApplication()

    with pytest.raises(
        ValueError,
        match="candidate handoff experiment not found",
    ):
        ExperimentCandidateHandoff(
            datasets=datasets,
            experiments=experiments,
            application=application,
        ).run(succeeded)

    assert application.call is None
