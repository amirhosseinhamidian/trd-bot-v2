from dataclasses import dataclass
from typing import Protocol

from trd_bot.research.optimization_executions import OptimizationExecution


class TrialExecutor(Protocol):
    def execute_trial(
        self,
        execution: OptimizationExecution,
        parameters: dict[str, str],
    ) -> str: ...


@dataclass(frozen=True)
class OptimizationTrialResult:
    parameters: dict[str, str]
    experiment_id: str


class OptimizationWorker:
    """Coordinates execution of optimization trials."""

    def __init__(self, trial_executor: TrialExecutor) -> None:
        self._trial_executor = trial_executor

    def run_trial(
        self,
        execution: OptimizationExecution,
        parameters: dict[str, str],
    ) -> OptimizationTrialResult:
        experiment_id = self._trial_executor.execute_trial(
            execution,
            parameters,
        )

        return OptimizationTrialResult(
            parameters=parameters,
            experiment_id=experiment_id,
        )
