import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting.benchmarks import ComparisonOutcome
from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.datasets import DatasetBuilder, DatasetSnapshot
from trd_bot.research.experiments import ExperimentParameter
from trd_bot.research.pipeline import (
    DEFAULT_RESEARCH_BACKTEST_CONFIG,
    ResearchPipeline,
    ResearchPipelineResult,
)
from trd_bot.strategies.base import BaseStrategy
from trd_bot.strategies.signals import StrategySignal, build_signal_id


class WalkForwardMode(StrEnum):
    """Supported training-window behaviors."""

    ROLLING = "rolling"
    EXPANDING = "expanding"


class WalkForwardConfig(BaseModel):
    """Configuration for chronological train and test folds."""

    model_config = ConfigDict(frozen=True)

    train_candles: int = Field(ge=2)
    test_candles: int = Field(ge=1)
    step_candles: int = Field(ge=1)
    gap_candles: int = Field(default=0, ge=0)
    mode: WalkForwardMode = WalkForwardMode.ROLLING

    @model_validator(mode="after")
    def prevent_overlapping_test_windows(self) -> Self:
        if self.step_candles < self.test_candles:
            raise ValueError("step candles must be at least test candles")
        return self


class WalkForwardFold(BaseModel):
    """One chronological train-gap-test split using exclusive end indexes."""

    model_config = ConfigDict(frozen=True)

    fold_number: int = Field(ge=1)
    train_start_index: int = Field(ge=0)
    train_end_index: int = Field(ge=1)
    test_start_index: int = Field(ge=1)
    test_end_index: int = Field(ge=1)
    train_start_time: datetime
    train_end_time: datetime
    test_start_time: datetime
    test_end_time: datetime

    @field_validator(
        "train_start_time",
        "train_end_time",
        "test_start_time",
        "test_end_time",
    )
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_chronology(self) -> Self:
        if self.train_start_index >= self.train_end_index:
            raise ValueError("training window must contain at least one candle")
        if self.train_end_index > self.test_start_index:
            raise ValueError("training window cannot overlap test window")
        if self.test_start_index >= self.test_end_index:
            raise ValueError("test window must contain at least one candle")
        if self.train_start_time >= self.train_end_time:
            raise ValueError("training timestamps must be chronological")
        if self.train_end_time > self.test_start_time:
            raise ValueError("training time cannot extend into test time")
        if self.test_start_time >= self.test_end_time:
            raise ValueError("test timestamps must be chronological")
        return self


class WalkForwardPlan(BaseModel):
    """Deterministic collection of walk-forward folds for one dataset."""

    model_config = ConfigDict(frozen=True)

    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1)
    candle_count: int = Field(gt=0)
    config: WalkForwardConfig
    folds: tuple[WalkForwardFold, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        expected_plan_id = build_walk_forward_plan_id(
            dataset_id=self.dataset_id,
            config=self.config,
        )
        if self.plan_id != expected_plan_id:
            raise ValueError("walk-forward plan ID is inconsistent")

        previous_test_start: int | None = None
        for expected_number, fold in enumerate(self.folds, start=1):
            if fold.fold_number != expected_number:
                raise ValueError("walk-forward fold numbers must be continuous")
            if fold.test_end_index > self.candle_count:
                raise ValueError("walk-forward fold exceeds dataset size")
            if fold.test_end_index - fold.test_start_index != self.config.test_candles:
                raise ValueError("test window size does not match config")
            if fold.test_start_index - fold.train_end_index != self.config.gap_candles:
                raise ValueError("fold gap does not match config")

            train_size = fold.train_end_index - fold.train_start_index
            if self.config.mode == WalkForwardMode.ROLLING:
                if train_size != self.config.train_candles:
                    raise ValueError("rolling training window size does not match config")
            else:
                if fold.train_start_index != 0:
                    raise ValueError("expanding training window must start at index zero")
                if train_size < self.config.train_candles:
                    raise ValueError("expanding training window is smaller than config")

            if (
                previous_test_start is not None
                and fold.test_start_index - previous_test_start != self.config.step_candles
            ):
                raise ValueError("fold step does not match config")
            previous_test_start = fold.test_start_index

        return self


class WalkForwardDatasetSplit(BaseModel):
    """Materialized train and test datasets for one walk-forward fold."""

    model_config = ConfigDict(frozen=True)

    split_id: str = Field(pattern=r"^walk-forward-split-[a-f0-9]{16}$")
    source_dataset_id: str = Field(min_length=1)
    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    fold: WalkForwardFold
    train_dataset: DatasetSnapshot
    test_dataset: DatasetSnapshot

    @model_validator(mode="after")
    def validate_split(self) -> Self:
        expected_split_id = build_walk_forward_split_id(
            source_dataset_id=self.source_dataset_id,
            plan_id=self.plan_id,
            fold_number=self.fold.fold_number,
            train_dataset_id=self.train_dataset.dataset_id,
            test_dataset_id=self.test_dataset.dataset_id,
        )
        if self.split_id != expected_split_id:
            raise ValueError("walk-forward split ID is inconsistent")

        train_size = self.fold.train_end_index - self.fold.train_start_index
        test_size = self.fold.test_end_index - self.fold.test_start_index
        if self.train_dataset.candle_count != train_size:
            raise ValueError("training dataset size does not match fold")
        if self.test_dataset.candle_count != test_size:
            raise ValueError("test dataset size does not match fold")

        if self.train_dataset.start_time != self.fold.train_start_time:
            raise ValueError("training dataset start time does not match fold")
        if self.train_dataset.end_time != self.fold.train_end_time:
            raise ValueError("training dataset end time does not match fold")
        if self.test_dataset.start_time != self.fold.test_start_time:
            raise ValueError("test dataset start time does not match fold")
        if self.test_dataset.end_time != self.fold.test_end_time:
            raise ValueError("test dataset end time does not match fold")

        if self.train_dataset.end_time > self.test_dataset.start_time:
            raise ValueError("training dataset cannot overlap test dataset")
        if self.train_dataset.source != self.test_dataset.source:
            raise ValueError("training and test datasets must use the same source")
        if self.train_dataset.pair != self.test_dataset.pair:
            raise ValueError("training and test datasets must use the same pair")
        if self.train_dataset.timeframe != self.test_dataset.timeframe:
            raise ValueError("training and test datasets must use the same timeframe")
        return self


class WalkForwardMaterialization(BaseModel):
    """All materialized datasets produced from one walk-forward plan."""

    model_config = ConfigDict(frozen=True)

    source_dataset_id: str = Field(min_length=1)
    plan: WalkForwardPlan
    splits: tuple[WalkForwardDatasetSplit, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_materialization(self) -> Self:
        if self.source_dataset_id != self.plan.dataset_id:
            raise ValueError("source dataset does not match walk-forward plan")
        if len(self.splits) != len(self.plan.folds):
            raise ValueError("materialized split count does not match plan")

        for fold, split in zip(self.plan.folds, self.splits, strict=True):
            if split.source_dataset_id != self.source_dataset_id:
                raise ValueError("split source dataset does not match materialization")
            if split.plan_id != self.plan.plan_id:
                raise ValueError("split plan ID does not match materialization")
            if split.fold != fold:
                raise ValueError("materialized split does not match plan fold")
        return self


class WalkForwardFoldExecution(BaseModel):
    """Offline research result for one materialized test fold."""

    model_config = ConfigDict(frozen=True)

    split_id: str = Field(pattern=r"^walk-forward-split-[a-f0-9]{16}$")
    fold_number: int = Field(ge=1)
    test_dataset_id: str = Field(min_length=1)
    result: ResearchPipelineResult

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        if self.result.dataset_id != self.test_dataset_id:
            raise ValueError("fold result dataset does not match test dataset")
        return self


class WalkForwardExecutionSummary(BaseModel):
    """Aggregate out-of-sample metrics across all executed folds."""

    model_config = ConfigDict(frozen=True)

    total_folds: int = Field(ge=1)
    total_signals: int = Field(ge=0)
    folds_with_trades: int = Field(ge=0)
    strategy_wins: int = Field(ge=0)
    benchmark_wins: int = Field(ge=0)
    ties: int = Field(ge=0)
    average_strategy_return: Decimal
    average_benchmark_return: Decimal
    average_excess_return: Decimal
    worst_max_drawdown_fraction: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.folds_with_trades > self.total_folds:
            raise ValueError("folds with trades cannot exceed total folds")
        if self.strategy_wins + self.benchmark_wins + self.ties != self.total_folds:
            raise ValueError("comparison outcomes must equal total folds")
        if self.average_excess_return != (
            self.average_strategy_return - self.average_benchmark_return
        ):
            raise ValueError("average excess return is inconsistent")
        return self


class WalkForwardExecutionResult(BaseModel):
    """Complete deterministic result of one offline walk-forward execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(pattern=r"^walk-forward-execution-[a-f0-9]{16}$")
    source_dataset_id: str = Field(min_length=1)
    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)
    strategy_parameters: tuple[ExperimentParameter, ...] = ()
    horizon_candles: int = Field(ge=1)
    backtest_config: BacktestConfig
    fold_results: tuple[WalkForwardFoldExecution, ...] = Field(min_length=1)
    summary: WalkForwardExecutionSummary

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        expected_id = build_walk_forward_execution_id(
            plan_id=self.plan_id,
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            strategy_parameters=self.strategy_parameters,
            horizon_candles=self.horizon_candles,
            backtest_config=self.backtest_config,
            fold_run_ids=tuple(
                fold_result.result.backtest_run_id for fold_result in self.fold_results
            ),
        )
        if self.execution_id != expected_id:
            raise ValueError("walk-forward execution ID is inconsistent")
        if len(self.fold_results) != self.summary.total_folds:
            raise ValueError("fold result count does not match summary")

        ordered_parameters = tuple(
            sorted(
                self.strategy_parameters,
                key=lambda parameter: (parameter.name, parameter.value),
            )
        )
        if self.strategy_parameters != ordered_parameters:
            raise ValueError("strategy parameters must be ordered")
        parameter_names = [parameter.name for parameter in self.strategy_parameters]
        if len(parameter_names) != len(set(parameter_names)):
            raise ValueError("strategy parameter names must be unique")

        for expected_number, fold_result in enumerate(self.fold_results, start=1):
            if fold_result.fold_number != expected_number:
                raise ValueError("executed fold numbers must be continuous")
            if fold_result.result.strategy_name != self.strategy_name:
                raise ValueError("fold strategy name does not match execution")
            if fold_result.result.strategy_version != self.strategy_version:
                raise ValueError("fold strategy version does not match execution")
            if fold_result.result.backtest_config != self.backtest_config:
                raise ValueError("fold backtest config does not match execution")
        return self


def build_walk_forward_plan_id(
    *,
    dataset_id: str,
    config: WalkForwardConfig,
) -> str:
    """Build a deterministic identifier for one fold configuration."""

    config_payload = json.dumps(
        config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    identity = "::".join([dataset_id, config_payload])
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"walk-forward-{digest[:16]}"


def build_walk_forward_split_id(
    *,
    source_dataset_id: str,
    plan_id: str,
    fold_number: int,
    train_dataset_id: str,
    test_dataset_id: str,
) -> str:
    """Build a deterministic identifier for one materialized fold."""

    identity = "::".join(
        [
            source_dataset_id,
            plan_id,
            str(fold_number),
            train_dataset_id,
            test_dataset_id,
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"walk-forward-split-{digest[:16]}"


def build_walk_forward_execution_id(
    *,
    plan_id: str,
    strategy_name: str,
    strategy_version: str,
    strategy_parameters: Sequence[ExperimentParameter],
    horizon_candles: int,
    backtest_config: BacktestConfig,
    fold_run_ids: Sequence[str],
) -> str:
    """Build a deterministic identifier for one walk-forward execution."""

    config_payload = json.dumps(
        backtest_config.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
    )
    ordered_parameters = sorted(
        strategy_parameters,
        key=lambda parameter: (parameter.name, parameter.value),
    )
    parameter_identity = "::".join(
        f"{parameter.name}={parameter.value}" for parameter in ordered_parameters
    )
    identity = "::".join(
        [
            plan_id,
            strategy_name,
            strategy_version,
            parameter_identity,
            str(horizon_candles),
            config_payload,
            "::".join(fold_run_ids),
        ]
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"walk-forward-execution-{digest[:16]}"


class WalkForwardPlanner:
    """Create chronological folds without using future candles for training."""

    def plan(
        self,
        *,
        dataset: DatasetSnapshot,
        config: WalkForwardConfig,
    ) -> WalkForwardPlan:
        folds: list[WalkForwardFold] = []
        test_start_index = config.train_candles + config.gap_candles

        while test_start_index + config.test_candles <= dataset.candle_count:
            train_end_index = test_start_index - config.gap_candles
            train_start_index = (
                0
                if config.mode == WalkForwardMode.EXPANDING
                else train_end_index - config.train_candles
            )
            test_end_index = test_start_index + config.test_candles

            train_start_candle = dataset.candles[train_start_index]
            train_end_candle = dataset.candles[train_end_index - 1]
            test_start_candle = dataset.candles[test_start_index]
            test_end_candle = dataset.candles[test_end_index - 1]

            folds.append(
                WalkForwardFold(
                    fold_number=len(folds) + 1,
                    train_start_index=train_start_index,
                    train_end_index=train_end_index,
                    test_start_index=test_start_index,
                    test_end_index=test_end_index,
                    train_start_time=train_start_candle.open_time,
                    train_end_time=train_end_candle.close_time,
                    test_start_time=test_start_candle.open_time,
                    test_end_time=test_end_candle.close_time,
                )
            )
            test_start_index += config.step_candles

        if not folds:
            required_candles = config.train_candles + config.gap_candles + config.test_candles
            raise ValueError(f"dataset requires at least {required_candles} candles for one fold")

        return WalkForwardPlan(
            plan_id=build_walk_forward_plan_id(
                dataset_id=dataset.dataset_id,
                config=config,
            ),
            dataset_id=dataset.dataset_id,
            candle_count=dataset.candle_count,
            config=config,
            folds=tuple(folds),
        )


class WalkForwardDatasetMaterializer:
    """Create deterministic train and test datasets for every planned fold."""

    def __init__(self, dataset_builder: DatasetBuilder | None = None) -> None:
        self._dataset_builder = dataset_builder or DatasetBuilder()

    def materialize(
        self,
        *,
        dataset: DatasetSnapshot,
        plan: WalkForwardPlan,
    ) -> WalkForwardMaterialization:
        if plan.dataset_id != dataset.dataset_id:
            raise ValueError("walk-forward plan does not belong to dataset")
        if plan.candle_count != dataset.candle_count:
            raise ValueError("walk-forward plan candle count does not match dataset")

        splits: list[WalkForwardDatasetSplit] = []

        for fold in plan.folds:
            train_dataset = self._dataset_builder.build(
                name=f"walk-forward fold {fold.fold_number} train",
                candles=dataset.candles[fold.train_start_index : fold.train_end_index],
                created_at=dataset.created_at,
            )
            test_dataset = self._dataset_builder.build(
                name=f"walk-forward fold {fold.fold_number} test",
                candles=dataset.candles[fold.test_start_index : fold.test_end_index],
                created_at=dataset.created_at,
            )

            splits.append(
                WalkForwardDatasetSplit(
                    split_id=build_walk_forward_split_id(
                        source_dataset_id=dataset.dataset_id,
                        plan_id=plan.plan_id,
                        fold_number=fold.fold_number,
                        train_dataset_id=train_dataset.dataset_id,
                        test_dataset_id=test_dataset.dataset_id,
                    ),
                    source_dataset_id=dataset.dataset_id,
                    plan_id=plan.plan_id,
                    fold=fold,
                    train_dataset=train_dataset,
                    test_dataset=test_dataset,
                )
            )

        return WalkForwardMaterialization(
            source_dataset_id=dataset.dataset_id,
            plan=plan,
            splits=tuple(splits),
        )


class WalkForwardExecutor:
    """Execute a strategy on test folds without exposing future test candles."""

    def __init__(
        self,
        *,
        dataset_builder: DatasetBuilder | None = None,
        research_pipeline: ResearchPipeline | None = None,
    ) -> None:
        self._dataset_builder = dataset_builder or DatasetBuilder()
        self._research_pipeline = research_pipeline or ResearchPipeline()

    def execute(
        self,
        *,
        dataset: DatasetSnapshot,
        materialization: WalkForwardMaterialization,
        strategy: BaseStrategy,
        strategy_parameters: Sequence[ExperimentParameter] = (),
        horizon_candles: int = 1,
        backtest_config: BacktestConfig | None = None,
    ) -> WalkForwardExecutionResult:
        if materialization.source_dataset_id != dataset.dataset_id:
            raise ValueError("walk-forward materialization does not belong to dataset")
        if horizon_candles < 1:
            raise ValueError("horizon candles must be greater than zero")

        effective_config = backtest_config or DEFAULT_RESEARCH_BACKTEST_CONFIG
        ordered_parameters = tuple(
            sorted(
                strategy_parameters,
                key=lambda parameter: (parameter.name, parameter.value),
            )
        )
        fold_results: list[WalkForwardFoldExecution] = []

        for split in materialization.splits:
            signals = self._generate_test_signals(
                dataset=dataset,
                split=split,
                strategy=strategy,
            )
            result = self._research_pipeline.run_with_signals(
                dataset=split.test_dataset,
                strategy_name=strategy.name,
                strategy_version=strategy.version,
                signals=signals,
                horizon_candles=horizon_candles,
                backtest_config=effective_config,
            )
            fold_results.append(
                WalkForwardFoldExecution(
                    split_id=split.split_id,
                    fold_number=split.fold.fold_number,
                    test_dataset_id=split.test_dataset.dataset_id,
                    result=result,
                )
            )

        completed_folds = tuple(fold_results)
        return WalkForwardExecutionResult(
            execution_id=build_walk_forward_execution_id(
                plan_id=materialization.plan.plan_id,
                strategy_name=strategy.name,
                strategy_version=strategy.version,
                strategy_parameters=ordered_parameters,
                horizon_candles=horizon_candles,
                backtest_config=effective_config,
                fold_run_ids=tuple(
                    fold_result.result.backtest_run_id for fold_result in completed_folds
                ),
            ),
            source_dataset_id=dataset.dataset_id,
            plan_id=materialization.plan.plan_id,
            strategy_name=strategy.name,
            strategy_version=strategy.version,
            strategy_parameters=ordered_parameters,
            horizon_candles=horizon_candles,
            backtest_config=effective_config,
            fold_results=completed_folds,
            summary=self._summarize(completed_folds),
        )

    def _generate_test_signals(
        self,
        *,
        dataset: DatasetSnapshot,
        split: WalkForwardDatasetSplit,
        strategy: BaseStrategy,
    ) -> tuple[StrategySignal, ...]:
        signals: list[StrategySignal] = []

        for candle_index in range(
            split.fold.test_start_index,
            split.fold.test_end_index,
        ):
            current_candle = dataset.candles[candle_index]
            context = self._dataset_builder.build(
                name=f"walk-forward fold {split.fold.fold_number} context {candle_index}",
                candles=dataset.candles[split.fold.train_start_index : candle_index + 1],
                created_at=dataset.created_at,
            )
            current_signals = tuple(
                signal
                for signal in strategy.generate(context)
                if signal.candle_open_time == current_candle.open_time
                and signal.candle_close_time == current_candle.close_time
            )
            if len(current_signals) > 1:
                raise ValueError("strategy produced multiple signals for one test candle")
            if current_signals:
                signals.append(
                    self._rebase_signal(
                        signal=current_signals[0],
                        test_dataset=split.test_dataset,
                    )
                )

        return tuple(signals)

    @staticmethod
    def _rebase_signal(
        *,
        signal: StrategySignal,
        test_dataset: DatasetSnapshot,
    ) -> StrategySignal:
        return StrategySignal(
            signal_id=build_signal_id(
                strategy_name=signal.strategy_name,
                strategy_version=signal.strategy_version,
                dataset_id=test_dataset.dataset_id,
                candle_close_time=signal.candle_close_time,
                direction=signal.direction,
            ),
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            dataset_id=test_dataset.dataset_id,
            pair=signal.pair,
            timeframe=signal.timeframe,
            candle_open_time=signal.candle_open_time,
            candle_close_time=signal.candle_close_time,
            generated_at=signal.generated_at,
            direction=signal.direction,
            score=signal.score,
            reason=signal.reason,
            features=signal.features,
        )

    @staticmethod
    def _summarize(
        fold_results: tuple[WalkForwardFoldExecution, ...],
    ) -> WalkForwardExecutionSummary:
        total_folds = len(fold_results)
        divisor = Decimal(total_folds)
        strategy_returns = tuple(
            fold.result.performance_report.total_return for fold in fold_results
        )
        benchmark_returns = tuple(
            fold.result.benchmark_result.performance_report.total_return for fold in fold_results
        )
        average_strategy_return = sum(strategy_returns, start=Decimal("0")) / divisor
        average_benchmark_return = sum(benchmark_returns, start=Decimal("0")) / divisor

        return WalkForwardExecutionSummary(
            total_folds=total_folds,
            total_signals=sum(fold.result.generated_signals for fold in fold_results),
            folds_with_trades=sum(
                fold.result.performance_report.total_trades > 0 for fold in fold_results
            ),
            strategy_wins=sum(
                fold.result.benchmark_comparison.outcome == ComparisonOutcome.STRATEGY
                for fold in fold_results
            ),
            benchmark_wins=sum(
                fold.result.benchmark_comparison.outcome == ComparisonOutcome.BENCHMARK
                for fold in fold_results
            ),
            ties=sum(
                fold.result.benchmark_comparison.outcome == ComparisonOutcome.TIE
                for fold in fold_results
            ),
            average_strategy_return=average_strategy_return,
            average_benchmark_return=average_benchmark_return,
            average_excess_return=average_strategy_return - average_benchmark_return,
            worst_max_drawdown_fraction=max(
                (fold.result.performance_report.max_drawdown_fraction for fold in fold_results),
                default=Decimal("0"),
            ),
        )
