from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from trd_bot.research.datasets import DatasetRepository, DatasetSnapshot
from trd_bot.research.experiments import (
    ExperimentBuilder,
    ExperimentParameter,
    ExperimentRegistry,
    ExperimentSummary,
    ResearchExperiment,
)
from trd_bot.research.optimization import OptimizationScorer, OptimizationTrial
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
    OptimizationExecutionState,
    OptimizationExecutionStateMachine,
)
from trd_bot.research.pipeline import ResearchPipeline
from trd_bot.strategies import (
    StrategyParameterKind,
    StrategyParameterValue,
    StrategyRegistry,
    build_default_strategy_registry,
)

ProgressReporter = Callable[[int], None]
CancellationCheck = Callable[[], bool]


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
    """Coordinates execution of one optimization trial."""

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


class OptimizationExecutionJobRunner:
    """Resume bounded trials and persist deterministic experiment results."""

    def __init__(
        self,
        *,
        executions: OptimizationExecutionRepository,
        datasets: DatasetRepository,
        experiments: ExperimentRegistry,
        state_machine: OptimizationExecutionStateMachine | None = None,
        strategy_registry: StrategyRegistry | None = None,
        scorer: OptimizationScorer | None = None,
    ) -> None:
        self._executions = executions
        self._datasets = datasets
        self._experiments = experiments
        self._state_machine = state_machine or OptimizationExecutionStateMachine()
        self._strategy_registry = strategy_registry or build_default_strategy_registry()
        self._scorer = scorer or OptimizationScorer()

    def run(
        self,
        execution_id: str,
        *,
        report_progress: ProgressReporter,
        cancellation_requested: CancellationCheck,
    ) -> OptimizationExecution:
        execution = self._executions.get(execution_id)
        if execution is None:
            raise ValueError("optimization execution not found")
        if execution.status in {
            OptimizationExecutionState.SUCCEEDED,
            OptimizationExecutionState.FAILED,
        }:
            return execution

        if execution.status is OptimizationExecutionState.QUEUED:
            execution = self._executions.save(self._state_machine.start(execution))

        report_progress(self._progress(execution))
        if cancellation_requested():
            return self._fail(
                execution,
                error_code="optimization_cancelled",
                error_message="The optimization execution was cancelled.",
            )

        dataset = self._datasets.get(execution.dataset_id)
        if dataset is None:
            return self._fail(
                execution,
                error_code="dataset_not_found",
                error_message=(
                    "The historical dataset required for this optimization is unavailable."
                ),
            )

        for trial in execution.plan.trials[execution.completed_trials :]:
            if cancellation_requested():
                return self._fail(
                    execution,
                    error_code="optimization_cancelled",
                    error_message="The optimization execution was cancelled.",
                )

            try:
                experiment = self._execute_trial(
                    execution=execution,
                    trial=trial,
                    dataset=dataset,
                )
            except (ArithmeticError, ValueError):
                return self._fail(
                    execution,
                    error_code="trial_execution_failed",
                    error_message="An optimization trial could not be completed.",
                )

            execution = self._state_machine.record_trial(
                execution,
                experiment_id=experiment.experiment_id,
            )
            execution = self._executions.save(execution)
            report_progress(self._progress(execution))

        if cancellation_requested():
            return self._fail(
                execution,
                error_code="optimization_cancelled",
                error_message="The optimization execution was cancelled.",
            )

        try:
            summaries = tuple(
                ExperimentSummary.from_experiment(self._require_experiment(experiment_id))
                for experiment_id in execution.experiment_ids
            )
            ranking = self._scorer.rank(
                experiments=summaries,
                objective=execution.objective,
            )
        except ValueError:
            return self._fail(
                execution,
                error_code="optimization_ranking_failed",
                error_message="Optimization results could not be ranked.",
            )

        execution = self._state_machine.succeed(
            execution,
            best_experiment_id=ranking.best_experiment_id,
        )
        execution = self._executions.save(execution)
        report_progress(95)
        return execution

    def fail_active(
        self,
        execution_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> OptimizationExecution:
        """Fail an execution after its durable retry budget is exhausted."""

        execution = self._executions.get(execution_id)
        if execution is None:
            raise ValueError("optimization execution not found")
        if execution.status in {
            OptimizationExecutionState.SUCCEEDED,
            OptimizationExecutionState.FAILED,
        }:
            return execution
        if execution.status is OptimizationExecutionState.QUEUED:
            execution = self._executions.save(self._state_machine.start(execution))
        return self._fail(
            execution,
            error_code=error_code,
            error_message=error_message,
        )

    def _execute_trial(
        self,
        *,
        execution: OptimizationExecution,
        trial: OptimizationTrial,
        dataset: DatasetSnapshot,
    ) -> ResearchExperiment:
        definition = self._strategy_registry.require(
            name=execution.strategy_name,
            version=execution.strategy_version,
        )
        if definition.metadata is None:
            raise ValueError("strategy metadata is unavailable")

        values = {parameter.name: parameter.value for parameter in trial.parameters}
        typed_parameters: dict[str, StrategyParameterValue] = {}
        for parameter in definition.metadata.parameters:
            value = values[parameter.name]
            if parameter.kind is StrategyParameterKind.INTEGER:
                typed_parameters[parameter.name] = int(value)
            else:
                decimal_value = Decimal(value)
                if not decimal_value.is_finite():
                    raise ValueError("strategy parameter must be finite")
                typed_parameters[parameter.name] = decimal_value

        strategy = definition.create(typed_parameters)
        result = ResearchPipeline().run(
            dataset=dataset,
            strategy=strategy,
            horizon_candles=execution.horizon_candles,
            backtest_config=execution.backtest_config,
        )
        experiment = ExperimentBuilder(self._strategy_registry).build(
            result=result,
            parameters=self._experiment_parameters(execution, trial),
        )
        return self._experiments.save(experiment)

    @staticmethod
    def _experiment_parameters(
        execution: OptimizationExecution,
        trial: OptimizationTrial,
    ) -> tuple[ExperimentParameter, ...]:
        config = execution.backtest_config
        return (
            *trial.parameters,
            ExperimentParameter(
                name="starting_balance",
                value=_canonical_decimal(config.starting_balance),
            ),
            ExperimentParameter(
                name="allocation_fraction",
                value=_canonical_decimal(config.allocation_fraction),
            ),
            ExperimentParameter(
                name="fee_rate",
                value=_canonical_decimal(config.fee_rate),
            ),
            ExperimentParameter(
                name="slippage_rate",
                value=_canonical_decimal(config.slippage_rate),
            ),
        )

    def _require_experiment(self, experiment_id: str) -> ResearchExperiment:
        experiment = self._experiments.get(experiment_id)
        if experiment is None:
            raise ValueError("optimization experiment not found")
        return experiment

    def _fail(
        self,
        execution: OptimizationExecution,
        *,
        error_code: str,
        error_message: str,
    ) -> OptimizationExecution:
        failed = self._state_machine.fail(
            execution,
            error_code=error_code,
            error_message=error_message,
        )
        return self._executions.save(failed)

    @staticmethod
    def _progress(execution: OptimizationExecution) -> int:
        return 5 + (execution.completed_trials * 85 // execution.total_trials)


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
