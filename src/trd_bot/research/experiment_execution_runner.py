from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.datasets import DatasetRepository
from trd_bot.research.experiment_executions import (
    ExperimentExecution,
    ExperimentExecutionRepository,
    ExperimentExecutionStateMachine,
    ExperimentExecutionStatus,
)
from trd_bot.research.experiments import (
    ExperimentBuilder,
    ExperimentParameter,
    ExperimentRegistry,
)
from trd_bot.research.pipeline import ResearchPipeline
from trd_bot.strategies import StrategyRegistry, build_default_strategy_registry


class ExperimentExecutionRunner:
    """Execute one queued historical experiment and persist its lifecycle."""

    def __init__(
        self,
        *,
        executions: ExperimentExecutionRepository,
        datasets: DatasetRepository,
        experiments: ExperimentRegistry,
        state_machine: ExperimentExecutionStateMachine | None = None,
        strategy_registry: StrategyRegistry | None = None,
    ) -> None:
        self._executions = executions
        self._datasets = datasets
        self._experiments = experiments
        self._state_machine = state_machine or ExperimentExecutionStateMachine()
        self._strategy_registry = strategy_registry or build_default_strategy_registry()

    def run(
        self,
        execution_id: str,
    ) -> ExperimentExecution:
        execution = self._executions.get(execution_id)

        if execution is None:
            raise ValueError("experiment execution not found")

        if execution.status is not ExperimentExecutionStatus.QUEUED:
            return execution

        running = self._state_machine.start(execution)
        running = self._executions.save(running)

        dataset = self._datasets.get(running.dataset_id)

        if dataset is None:
            return self._fail(
                running,
                error_code="dataset_not_found",
                error_message=(
                    "The historical dataset required for this execution is no longer available."
                ),
            )

        running = self._state_machine.update_progress(
            running,
            progress_percent=20,
        )

        running = self._executions.save(running)

        try:
            parameters = running.parameters

            strategy = self._strategy_registry.create(
                name=running.strategy_name,
                version=running.strategy_version,
                parameters=parameters.strategy_parameters(),
            )

            result = ResearchPipeline().run(
                dataset=dataset,
                strategy=strategy,
                horizon_candles=parameters.horizon_candles,
                backtest_config=BacktestConfig(
                    starting_balance=parameters.starting_balance,
                    allocation_fraction=parameters.allocation_fraction,
                    fee_rate=parameters.fee_rate,
                    slippage_rate=parameters.slippage_rate,
                ),
            )

            running = self._state_machine.update_progress(
                running,
                progress_percent=90,
            )

            running = self._executions.save(running)

            experiment = ExperimentBuilder(self._strategy_registry).build(
                result=result,
                parameters=tuple(
                    ExperimentParameter(
                        name=name,
                        value=value,
                    )
                    for name, value in parameters.experiment_parameter_pairs()
                ),
            )

            stored_experiment = self._experiments.save(experiment)

            succeeded = self._state_machine.succeed(
                running,
                experiment_id=stored_experiment.experiment_id,
            )

            return self._executions.save(succeeded)

        except Exception:
            return self._fail(
                running,
                error_code="execution_failed",
                error_message=("The historical experiment could not be completed."),
            )

    def _fail(
        self,
        execution: ExperimentExecution,
        *,
        error_code: str,
        error_message: str,
    ) -> ExperimentExecution:
        failed = self._state_machine.fail(
            execution,
            error_code=error_code,
            error_message=error_message,
        )

        return self._executions.save(failed)
