from datetime import UTC, datetime
from decimal import Decimal
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting.models import BacktestConfig
from trd_bot.research.experiments import ExperimentParameter
from trd_bot.research.walk_forward import (
    WalkForwardConfig,
    WalkForwardExecutionResult,
    build_walk_forward_plan_id,
)


class WalkForwardResearchRun(BaseModel):
    """Immutable stored record of one offline walk-forward execution."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(pattern=r"^walk-forward-execution-[a-f0-9]{16}$")
    created_at: datetime
    walk_forward_config: WalkForwardConfig
    result: WalkForwardExecutionResult

    @field_validator("created_at")
    @classmethod
    def created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created time must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_run(self) -> Self:
        if self.execution_id != self.result.execution_id:
            raise ValueError("stored execution ID does not match result")

        expected_plan_id = build_walk_forward_plan_id(
            dataset_id=self.result.source_dataset_id,
            config=self.walk_forward_config,
        )
        if self.result.plan_id != expected_plan_id:
            raise ValueError("walk-forward config does not match result plan")
        return self


class WalkForwardRunSummary(BaseModel):
    """Lightweight walk-forward record for dashboard lists."""

    model_config = ConfigDict(frozen=True)

    execution_id: str = Field(pattern=r"^walk-forward-execution-[a-f0-9]{16}$")
    created_at: datetime
    source_dataset_id: str = Field(min_length=1)
    plan_id: str = Field(pattern=r"^walk-forward-[a-f0-9]{16}$")
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)
    horizon_candles: int = Field(ge=1)
    strategy_parameters: tuple[ExperimentParameter, ...]
    walk_forward_config: WalkForwardConfig
    backtest_config: BacktestConfig
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

    @classmethod
    def from_run(cls, run: WalkForwardResearchRun) -> Self:
        result = run.result
        summary = result.summary
        return cls(
            execution_id=run.execution_id,
            created_at=run.created_at,
            source_dataset_id=result.source_dataset_id,
            plan_id=result.plan_id,
            strategy_name=result.strategy_name,
            strategy_version=result.strategy_version,
            horizon_candles=result.horizon_candles,
            strategy_parameters=result.strategy_parameters,
            walk_forward_config=run.walk_forward_config,
            backtest_config=result.backtest_config,
            total_folds=summary.total_folds,
            total_signals=summary.total_signals,
            folds_with_trades=summary.folds_with_trades,
            strategy_wins=summary.strategy_wins,
            benchmark_wins=summary.benchmark_wins,
            ties=summary.ties,
            average_strategy_return=summary.average_strategy_return,
            average_benchmark_return=summary.average_benchmark_return,
            average_excess_return=summary.average_excess_return,
            worst_max_drawdown_fraction=summary.worst_max_drawdown_fraction,
        )


class WalkForwardRunBuilder:
    """Build reproducible records around walk-forward results."""

    def build(
        self,
        *,
        result: WalkForwardExecutionResult,
        walk_forward_config: WalkForwardConfig,
        created_at: datetime | None = None,
    ) -> WalkForwardResearchRun:
        return WalkForwardResearchRun(
            execution_id=result.execution_id,
            created_at=created_at or datetime.now(UTC),
            walk_forward_config=walk_forward_config,
            result=result,
        )


class WalkForwardRunRegistry(Protocol):
    """Persistence contract for offline walk-forward research runs."""

    def save(self, run: WalkForwardResearchRun) -> WalkForwardResearchRun: ...

    def get(self, execution_id: str) -> WalkForwardResearchRun | None: ...

    def count(self) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]: ...


class InMemoryWalkForwardRunRegistry:
    """Store offline walk-forward research runs in memory."""

    def __init__(self) -> None:
        self._runs: dict[str, WalkForwardResearchRun] = {}

    def save(self, run: WalkForwardResearchRun) -> WalkForwardResearchRun:
        existing = self._runs.get(run.execution_id)
        if existing is not None:
            if not self._same_run(first=existing, second=run):
                raise ValueError("walk-forward execution ID already has different content")
            return existing

        self._runs[run.execution_id] = run
        return run

    def get(self, execution_id: str) -> WalkForwardResearchRun | None:
        return self._runs.get(execution_id)

    def list_all(self) -> tuple[WalkForwardResearchRun, ...]:
        return tuple(
            sorted(
                self._runs.values(),
                key=lambda run: (run.created_at, run.execution_id),
            )
        )

    def count(self) -> int:
        return len(self._runs)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
        return self.list_all()[offset : offset + limit]

    @staticmethod
    def _same_run(
        *,
        first: WalkForwardResearchRun,
        second: WalkForwardResearchRun,
    ) -> bool:
        return (
            first.walk_forward_config == second.walk_forward_config
            and first.result == second.result
        )
