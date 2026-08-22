from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
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


class WalkForwardRunSortField(StrEnum):
    """Supported walk-forward run catalog sort fields."""

    CREATED_AT = "created_at"
    HORIZON_CANDLES = "horizon_candles"


class WalkForwardRunSortDirection(StrEnum):
    """Supported walk-forward run catalog sort directions."""

    ASCENDING = "asc"
    DESCENDING = "desc"


class WalkForwardRunCatalogQuery(BaseModel):
    """Normalized filters and ordering for stored walk-forward runs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source_dataset_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    plan_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    strategy_name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
    )

    strategy_version: str | None = Field(
        default=None,
        min_length=1,
        max_length=30,
    )

    horizon_candles: int | None = Field(
        default=None,
        ge=1,
    )
    created_at_from: datetime | None = None
    created_at_to: datetime | None = None

    sort_by: WalkForwardRunSortField = WalkForwardRunSortField.CREATED_AT

    sort_direction: WalkForwardRunSortDirection = WalkForwardRunSortDirection.ASCENDING

    @field_validator(
        "source_dataset_id",
        "plan_id",
        "strategy_name",
        "strategy_version",
        mode="before",
    )
    @classmethod
    def normalize_text_filter(
        cls,
        value: object,
    ) -> object:
        if isinstance(value, str):
            return value.strip()

        return value

    @field_validator("created_at_from", "created_at_to")
    @classmethod
    def created_time_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("created time must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_created_time_range(self) -> Self:
        if (
            self.created_at_from is not None
            and self.created_at_to is not None
            and self.created_at_to < self.created_at_from
        ):
            raise ValueError("created_at_to must be on or after created_at_from")
        return self


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

    def save(
        self,
        run: WalkForwardResearchRun,
    ) -> WalkForwardResearchRun: ...

    def get(
        self,
        execution_id: str,
    ) -> WalkForwardResearchRun | None: ...

    def count(self) -> int: ...

    def count_matching(
        self,
        query: WalkForwardRunCatalogQuery,
    ) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]: ...

    def search_page(
        self,
        *,
        query: WalkForwardRunCatalogQuery,
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

    def count_matching(
        self,
        query: WalkForwardRunCatalogQuery,
    ) -> int:
        return len(self._filter(query))

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]:
        return self.search_page(
            query=WalkForwardRunCatalogQuery(),
            limit=limit,
            offset=offset,
        )

    def search_page(
        self,
        *,
        query: WalkForwardRunCatalogQuery,
        limit: int,
        offset: int,
    ) -> tuple[WalkForwardResearchRun, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        if offset < 0:
            raise ValueError("offset cannot be negative")

        runs = self._sort(
            self._filter(query),
            query,
        )

        return runs[offset : offset + limit]

    def _filter(
        self,
        query: WalkForwardRunCatalogQuery,
    ) -> tuple[WalkForwardResearchRun, ...]:
        return tuple(
            run
            for run in self._runs.values()
            if (
                query.source_dataset_id is None
                or run.result.source_dataset_id == query.source_dataset_id
            )
            and (query.plan_id is None or run.result.plan_id == query.plan_id)
            and (query.strategy_name is None or run.result.strategy_name == query.strategy_name)
            and (
                query.strategy_version is None
                or run.result.strategy_version == query.strategy_version
            )
            and (
                query.horizon_candles is None or run.result.horizon_candles == query.horizon_candles
            )
            and (query.created_at_from is None or run.created_at >= query.created_at_from)
            and (query.created_at_to is None or run.created_at <= query.created_at_to)
        )

    @staticmethod
    def _sort(
        runs: tuple[WalkForwardResearchRun, ...],
        query: WalkForwardRunCatalogQuery,
    ) -> tuple[WalkForwardResearchRun, ...]:
        reverse = query.sort_direction is WalkForwardRunSortDirection.DESCENDING

        if query.sort_by is WalkForwardRunSortField.HORIZON_CANDLES:
            ordered = sorted(
                runs,
                key=lambda run: (
                    run.result.horizon_candles,
                    run.execution_id,
                ),
                reverse=reverse,
            )

        else:
            ordered = sorted(
                runs,
                key=lambda run: (
                    run.created_at,
                    run.execution_id,
                ),
                reverse=reverse,
            )

        return tuple(ordered)

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
