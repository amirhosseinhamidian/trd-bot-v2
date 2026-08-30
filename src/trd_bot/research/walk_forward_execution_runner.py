from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.datasets import DatasetRepository
from trd_bot.research.experiments import ExperimentParameter
from trd_bot.research.walk_forward import (
    WalkForwardDatasetMaterializer,
    WalkForwardExecutor,
    WalkForwardPlanner,
)
from trd_bot.research.walk_forward_executions import (
    WalkForwardExecution,
    WalkForwardExecutionRepository,
    WalkForwardExecutionStateMachine,
    WalkForwardExecutionStatus,
)
from trd_bot.research.walk_forward_runs import (
    WalkForwardRunBuilder,
    WalkForwardRunRegistry,
)
from trd_bot.strategies import StrategyRegistry, build_default_strategy_registry


class WalkForwardExecutionRunner:
    """Execute one queued walk-forward job and persist fold progress."""

    def __init__(
        self,
        *,
        executions: WalkForwardExecutionRepository,
        datasets: DatasetRepository,
        runs: WalkForwardRunRegistry,
        planner: WalkForwardPlanner | None = None,
        materializer: WalkForwardDatasetMaterializer | None = None,
        executor: WalkForwardExecutor | None = None,
        state_machine: WalkForwardExecutionStateMachine | None = None,
        strategy_registry: StrategyRegistry | None = None,
    ) -> None:
        self._executions = executions
        self._datasets = datasets
        self._runs = runs
        self._planner = planner or WalkForwardPlanner()
        self._materializer = materializer or WalkForwardDatasetMaterializer()
        self._executor = executor or WalkForwardExecutor()
        self._state_machine = state_machine or WalkForwardExecutionStateMachine()
        self._strategy_registry = strategy_registry or build_default_strategy_registry()

    def run(
        self,
        execution_id: str,
    ) -> WalkForwardExecution:
        execution = self._executions.get(execution_id)

        if execution is None:
            raise ValueError("walk-forward execution not found")

        if execution.status is not WalkForwardExecutionStatus.QUEUED:
            return execution

        running = self._state_machine.start(execution)
        running = self._executions.save(running)

        dataset = self._datasets.get(running.dataset_id)

        if dataset is None:
            return self._fail(
                running,
                error_code="dataset_not_found",
                error_message=(
                    "The historical dataset required for this walk-forward execution "
                    "is no longer available."
                ),
            )

        try:
            plan = self._planner.plan(
                dataset=dataset,
                config=running.walk_forward_config,
            )

            if len(plan.folds) != running.total_folds:
                raise ValueError("walk-forward fold count changed after the job was queued")

            materialization = self._materializer.materialize(
                dataset=dataset,
                plan=plan,
            )

            parameters = running.parameters
            strategy = self._strategy_registry.create(
                name=running.strategy_name,
                version=running.strategy_version,
                parameters=parameters.strategy_parameters(),
            )

            def save_fold_progress(
                completed_folds: int,
                total_folds: int,
            ) -> None:
                nonlocal running

                if total_folds != running.total_folds:
                    raise ValueError("walk-forward executor reported an unexpected fold count")

                progressed = self._state_machine.update_completed_folds(
                    running,
                    completed_folds=completed_folds,
                )

                running = self._executions.save(progressed)

            result = self._executor.execute(
                dataset=dataset,
                materialization=materialization,
                strategy=strategy,
                strategy_parameters=tuple(
                    ExperimentParameter(
                        name=name,
                        value=value,
                    )
                    for name, value in parameters.strategy_parameter_pairs()
                ),
                horizon_candles=parameters.horizon_candles,
                backtest_config=BacktestConfig(
                    starting_balance=parameters.starting_balance,
                    allocation_fraction=parameters.allocation_fraction,
                    fee_rate=parameters.fee_rate,
                    slippage_rate=parameters.slippage_rate,
                ),
                on_fold_completed=save_fold_progress,
            )

            run = WalkForwardRunBuilder().build(
                result=result,
                walk_forward_config=running.walk_forward_config,
            )

            stored_run = self._runs.save(run)

            succeeded = self._state_machine.succeed(
                running,
                walk_forward_run_id=stored_run.execution_id,
            )

            return self._executions.save(succeeded)

        except Exception:
            return self._fail(
                running,
                error_code="execution_failed",
                error_message=("The walk-forward execution could not be completed."),
            )

    def _fail(
        self,
        execution: WalkForwardExecution,
        *,
        error_code: str,
        error_message: str,
    ) -> WalkForwardExecution:
        failed = self._state_machine.fail(
            execution,
            error_code=error_code,
            error_message=error_message,
        )

        return self._executions.save(failed)
