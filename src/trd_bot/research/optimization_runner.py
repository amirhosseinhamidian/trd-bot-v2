from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
    OptimizationExecutionStateMachine,
)


class OptimizationRunner:
    """Persist explicit optimization lifecycle transitions."""

    def __init__(
        self,
        repository: OptimizationExecutionRepository,
        state_machine: OptimizationExecutionStateMachine | None = None,
    ) -> None:
        self._repository = repository
        self._state_machine = state_machine or OptimizationExecutionStateMachine()

    def create(self, execution: OptimizationExecution) -> OptimizationExecution:
        return self._repository.save(execution)

    def start(self, execution: OptimizationExecution) -> OptimizationExecution:
        return self._repository.save(self._state_machine.start(execution))

    def complete(
        self,
        execution: OptimizationExecution,
        *,
        best_experiment_id: str,
    ) -> OptimizationExecution:
        return self._repository.save(
            self._state_machine.succeed(
                execution,
                best_experiment_id=best_experiment_id,
            )
        )

    def fail(
        self,
        execution: OptimizationExecution,
        *,
        error_code: str,
        error_message: str,
    ) -> OptimizationExecution:
        return self._repository.save(
            self._state_machine.fail(
                execution,
                error_code=error_code,
                error_message=error_message,
            )
        )
