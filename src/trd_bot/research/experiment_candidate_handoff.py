from typing import Protocol

from trd_bot.research.candidate_application import CandidateApplicationResult
from trd_bot.research.datasets import DatasetRepository, DatasetSnapshot
from trd_bot.research.experiment_executions import (
    ExperimentExecution,
    ExperimentExecutionStatus,
    HistoricalExecutionParameters,
)
from trd_bot.research.experiments import (
    ExperimentRegistry,
    ResearchExperiment,
)


class CandidateApplication(Protocol):
    """Application boundary used after a successful experiment execution."""

    def run(
        self,
        *,
        experiment: ResearchExperiment,
        dataset: DatasetSnapshot,
        parameters: HistoricalExecutionParameters,
    ) -> CandidateApplicationResult: ...


class ExperimentCandidateHandoff:
    """Resolve a completed experiment execution into candidate processing."""

    def __init__(
        self,
        *,
        datasets: DatasetRepository,
        experiments: ExperimentRegistry,
        application: CandidateApplication,
    ) -> None:
        self._datasets = datasets
        self._experiments = experiments
        self._application = application

    def run(
        self,
        execution: ExperimentExecution,
    ) -> CandidateApplicationResult:
        if execution.status is not ExperimentExecutionStatus.SUCCEEDED:
            raise ValueError("candidate handoff requires a succeeded execution")

        if execution.experiment_id is None:
            raise ValueError("candidate handoff requires an execution experiment")

        dataset = self._datasets.get(execution.dataset_id)
        if dataset is None:
            raise ValueError("candidate handoff dataset not found")

        experiment = self._experiments.get(execution.experiment_id)
        if experiment is None:
            raise ValueError("candidate handoff experiment not found")

        return self._application.run(
            experiment=experiment,
            dataset=dataset,
            parameters=execution.parameters,
        )
