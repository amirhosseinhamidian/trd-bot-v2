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
from trd_bot.research.optimization import (
    OptimizationRankingResult,
    OptimizationScorer,
    OptimizationTrial,
)
from trd_bot.research.optimization_executions import (
    OptimizationExecution,
    OptimizationExecutionRepository,
    OptimizationExecutionState,
    OptimizationExecutionStateMachine,
)
from trd_bot.research.optimization_robustness import (
    OptimizationRobustnessRankingResult,
    OptimizationRobustnessScorer,
    OptimizationTrialEvaluation,
)
from trd_bot.research.pipeline import ResearchPipeline
from trd_bot.research.walk_forward import (
    WalkForwardDatasetMaterializer,
    WalkForwardExecutor,
    WalkForwardMaterialization,
    WalkForwardPlanner,
)
from trd_bot.research.walk_forward_reporting import WalkForwardStabilityAnalyzer
from trd_bot.research.walk_forward_runs import (
    WalkForwardRunBuilder,
    WalkForwardRunRegistry,
)
from trd_bot.strategies import (
    StrategyParameterKind,
    StrategyParameterValue,
    StrategyRegistry,
    build_default_strategy_registry,
)
from trd_bot.strategies.base import BaseStrategy

ProgressReporter = Callable[[int], None]
CancellationCheck = Callable[[], bool]


class _OptimizationCancellationRequested(RuntimeError):
    pass


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
        walk_forward_runs: WalkForwardRunRegistry | None = None,
        state_machine: OptimizationExecutionStateMachine | None = None,
        strategy_registry: StrategyRegistry | None = None,
        scorer: OptimizationScorer | None = None,
        robustness_scorer: OptimizationRobustnessScorer | None = None,
        walk_forward_planner: WalkForwardPlanner | None = None,
        walk_forward_materializer: WalkForwardDatasetMaterializer | None = None,
        walk_forward_executor: WalkForwardExecutor | None = None,
        stability_analyzer: WalkForwardStabilityAnalyzer | None = None,
    ) -> None:
        self._executions = executions
        self._datasets = datasets
        self._experiments = experiments
        self._walk_forward_runs = walk_forward_runs
        self._state_machine = state_machine or OptimizationExecutionStateMachine()
        self._strategy_registry = strategy_registry or build_default_strategy_registry()
        self._scorer = scorer or OptimizationScorer()
        self._robustness_scorer = robustness_scorer or OptimizationRobustnessScorer()
        self._walk_forward_planner = walk_forward_planner or WalkForwardPlanner()
        self._walk_forward_materializer = (
            walk_forward_materializer or WalkForwardDatasetMaterializer()
        )
        self._walk_forward_executor = walk_forward_executor or WalkForwardExecutor()
        self._stability_analyzer = stability_analyzer or WalkForwardStabilityAnalyzer()

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

        materialization = self._prepare_walk_forward(execution, dataset)
        if execution.robustness_plan is not None and materialization is None:
            return self._fail(
                execution,
                error_code="invalid_robustness_plan",
                error_message="Optimization walk-forward evidence could not be prepared.",
            )

        for trial in execution.plan.trials[execution.completed_trials :]:
            if cancellation_requested():
                return self._fail(
                    execution,
                    error_code="optimization_cancelled",
                    error_message="The optimization execution was cancelled.",
                )

            try:
                strategy = self._build_strategy(execution, trial)
                experiment = self._execute_trial(
                    execution=execution,
                    trial=trial,
                    dataset=dataset,
                    strategy=strategy,
                )
            except (ArithmeticError, ValueError):
                return self._fail(
                    execution,
                    error_code="trial_execution_failed",
                    error_message="An optimization trial could not be completed.",
                )

            evaluation: OptimizationTrialEvaluation | None = None
            if execution.robustness_plan is not None:
                assert materialization is not None
                try:
                    evaluation = self._evaluate_robustness(
                        execution=execution,
                        trial=trial,
                        dataset=dataset,
                        strategy=strategy,
                        experiment=experiment,
                        materialization=materialization,
                        report_progress=report_progress,
                        cancellation_requested=cancellation_requested,
                    )
                except _OptimizationCancellationRequested:
                    return self._fail(
                        execution,
                        error_code="optimization_cancelled",
                        error_message="The optimization execution was cancelled.",
                    )
                except (ArithmeticError, ValueError):
                    return self._fail(
                        execution,
                        error_code="robustness_evaluation_failed",
                        error_message=(
                            "An optimization walk-forward evaluation could not be completed."
                        ),
                    )

            execution = self._state_machine.record_trial(
                execution,
                experiment_id=experiment.experiment_id,
                evaluation=evaluation,
            )
            execution = self._executions.save(execution)
            report_progress(self._progress(execution))

        if cancellation_requested():
            return self._fail(
                execution,
                error_code="optimization_cancelled",
                error_message="The optimization execution was cancelled.",
            )

        ranking = self._rank(execution)
        if ranking is None:
            error_code = "optimization_ranking_failed"
            error_message = "Optimization results could not be ranked."
            if execution.robustness_plan is not None and not any(
                evaluation.eligible for evaluation in execution.trial_evaluations
            ):
                error_code = "no_robust_trial"
                error_message = "No optimization trial passed the robustness policy."
            return self._fail(
                execution,
                error_code=error_code,
                error_message=error_message,
            )

        execution = self._state_machine.succeed(
            execution,
            best_experiment_id=ranking.best_experiment_id,
            robustness_ranking=(
                ranking if isinstance(ranking, OptimizationRobustnessRankingResult) else None
            ),
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
        strategy: BaseStrategy,
    ) -> ResearchExperiment:
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

    def _build_strategy(
        self,
        execution: OptimizationExecution,
        trial: OptimizationTrial,
    ) -> BaseStrategy:
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

        return definition.create(typed_parameters)

    def _prepare_walk_forward(
        self,
        execution: OptimizationExecution,
        dataset: DatasetSnapshot,
    ) -> WalkForwardMaterialization | None:
        policy = execution.robustness_plan
        if policy is None:
            return None
        if self._walk_forward_runs is None:
            raise ValueError("robust optimization requires a walk-forward run registry")
        try:
            plan = self._walk_forward_planner.plan(
                dataset=dataset,
                config=policy.walk_forward_config,
            )
            if plan.plan_id != policy.walk_forward_plan_id:
                raise ValueError("walk-forward plan identity changed after enqueue")
            if len(plan.folds) != policy.total_folds:
                raise ValueError("walk-forward fold count changed after enqueue")
            return self._walk_forward_materializer.materialize(
                dataset=dataset,
                plan=plan,
            )
        except (ArithmeticError, ValueError):
            return None

    def _evaluate_robustness(
        self,
        *,
        execution: OptimizationExecution,
        trial: OptimizationTrial,
        dataset: DatasetSnapshot,
        strategy: BaseStrategy,
        experiment: ResearchExperiment,
        materialization: WalkForwardMaterialization,
        report_progress: ProgressReporter,
        cancellation_requested: CancellationCheck,
    ) -> OptimizationTrialEvaluation:
        policy = execution.robustness_plan
        if policy is None or self._walk_forward_runs is None:
            raise ValueError("robustness evaluation is not configured")

        def fold_completed(completed_folds: int, total_folds: int) -> None:
            if cancellation_requested():
                raise _OptimizationCancellationRequested
            if total_folds != policy.total_folds:
                raise ValueError("walk-forward executor reported an unexpected fold count")
            report_progress(
                self._fold_progress(
                    execution,
                    completed_folds=completed_folds,
                )
            )

        result = self._walk_forward_executor.execute(
            dataset=dataset,
            materialization=materialization,
            strategy=strategy,
            strategy_parameters=trial.parameters,
            horizon_candles=execution.horizon_candles,
            backtest_config=execution.backtest_config,
            on_fold_completed=fold_completed,
        )
        run = WalkForwardRunBuilder().build(
            result=result,
            walk_forward_config=policy.walk_forward_config,
            created_at=execution.created_at,
        )
        stored_run = self._walk_forward_runs.save(run)
        stability = self._stability_analyzer.analyze(stored_run)
        return self._robustness_scorer.evaluate(
            trial_number=trial.trial_number,
            experiment=ExperimentSummary.from_experiment(experiment),
            stability=stability,
            policy=policy,
            objective=execution.objective,
        )

    def _rank(
        self,
        execution: OptimizationExecution,
    ) -> OptimizationRankingResult | OptimizationRobustnessRankingResult | None:
        try:
            if execution.robustness_plan is not None:
                return self._robustness_scorer.rank(
                    evaluations=execution.trial_evaluations,
                    objective=execution.objective,
                )
            summaries = tuple(
                ExperimentSummary.from_experiment(self._require_experiment(experiment_id))
                for experiment_id in execution.experiment_ids
            )
            return self._scorer.rank(
                experiments=summaries,
                objective=execution.objective,
            )
        except ValueError:
            return None

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

    @staticmethod
    def _fold_progress(
        execution: OptimizationExecution,
        *,
        completed_folds: int,
    ) -> int:
        policy = execution.robustness_plan
        if policy is None:
            return OptimizationExecutionJobRunner._progress(execution)
        completed_units = execution.completed_trials * policy.total_folds + completed_folds
        total_units = execution.total_trials * policy.total_folds
        return 5 + (completed_units * 85 // total_units)


def _canonical_decimal(value: Decimal) -> str:
    return format(value.normalize(), "f")
