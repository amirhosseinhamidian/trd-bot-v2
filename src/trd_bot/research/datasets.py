import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data.quality import (
    DataQualityReport,
    MarketDataQualityChecker,
)


class DatasetSnapshot(BaseModel):
    """An immutable and validated market-data snapshot."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    schema_version: int = 1
    name: str = Field(min_length=1, max_length=100)

    source: str
    pair: TradingPair
    timeframe: Timeframe

    start_time: datetime
    end_time: datetime
    created_at: datetime

    candle_count: int = Field(gt=0)
    checksum: str = Field(min_length=64, max_length=64)
    candles: tuple[OHLCVCandle, ...]


class DatasetSummary(BaseModel):
    """Lightweight dataset metadata for catalog and dashboard lists."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    schema_version: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)
    source: str
    pair: TradingPair
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    created_at: datetime
    candle_count: int = Field(gt=0)
    checksum: str = Field(min_length=64, max_length=64)

    @classmethod
    def from_dataset(cls, dataset: DatasetSnapshot) -> Self:
        return cls(
            dataset_id=dataset.dataset_id,
            schema_version=dataset.schema_version,
            name=dataset.name,
            source=dataset.source,
            pair=dataset.pair,
            timeframe=dataset.timeframe,
            start_time=dataset.start_time,
            end_time=dataset.end_time,
            created_at=dataset.created_at,
            candle_count=dataset.candle_count,
            checksum=dataset.checksum,
        )


class InvalidDatasetError(ValueError):
    """Raised when market data fails quality validation."""

    def __init__(self, report: DataQualityReport) -> None:
        self.report = report

        issue_codes = ", ".join(issue.code.value for issue in report.issues)

        super().__init__(f"Dataset failed quality checks: {issue_codes}")


class DatasetRepository(Protocol):
    """Persistence contract for immutable dataset snapshots."""

    def save(self, dataset: DatasetSnapshot) -> DatasetSnapshot: ...

    def get(self, dataset_id: str) -> DatasetSnapshot | None: ...

    def count(self) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[DatasetSnapshot, ...]: ...


class InMemoryDatasetRepository:
    """Store immutable dataset snapshots in memory."""

    def __init__(self) -> None:
        self._datasets: dict[str, DatasetSnapshot] = {}

    def save(self, dataset: DatasetSnapshot) -> DatasetSnapshot:
        existing = self._datasets.get(dataset.dataset_id)
        if existing is not None:
            if not self._same_dataset(first=existing, second=dataset):
                raise ValueError("dataset ID already exists with different content")
            return existing

        self._datasets[dataset.dataset_id] = dataset
        return dataset

    def get(self, dataset_id: str) -> DatasetSnapshot | None:
        return self._datasets.get(dataset_id)

    def count(self) -> int:
        return len(self._datasets)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[DatasetSnapshot, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        datasets = tuple(
            sorted(
                self._datasets.values(),
                key=lambda dataset: (dataset.created_at, dataset.dataset_id),
            )
        )
        return datasets[offset : offset + limit]

    @staticmethod
    def _same_dataset(
        *,
        first: DatasetSnapshot,
        second: DatasetSnapshot,
    ) -> bool:
        return first.checksum == second.checksum and first.candles == second.candles


class DatasetBuilder:
    """Build immutable datasets from validated candles."""

    def __init__(
        self,
        quality_checker: MarketDataQualityChecker | None = None,
    ) -> None:
        self._quality_checker = quality_checker or MarketDataQualityChecker()

    def build(
        self,
        name: str,
        candles: Sequence[OHLCVCandle],
        *,
        created_at: datetime | None = None,
    ) -> DatasetSnapshot:
        if created_at is not None and (created_at.tzinfo is None or created_at.utcoffset() is None):
            raise ValueError("created time must include timezone information")

        report = self._quality_checker.check(candles)

        if not report.is_valid:
            raise InvalidDatasetError(report)

        checksum = self._calculate_checksum(candles)

        return DatasetSnapshot(
            dataset_id=f"dataset-{checksum[:16]}",
            name=name,
            source=candles[0].source,
            pair=candles[0].pair,
            timeframe=candles[0].timeframe,
            start_time=candles[0].open_time,
            end_time=candles[-1].close_time,
            created_at=(created_at or datetime.now(UTC)).astimezone(UTC),
            candle_count=len(candles),
            checksum=checksum,
            candles=tuple(candles),
        )

    @staticmethod
    def _calculate_checksum(
        candles: Sequence[OHLCVCandle],
    ) -> str:
        digest = hashlib.sha256()

        for candle in candles:
            candle_data = candle.model_dump(
                mode="json",
                exclude={"received_at"},
            )

            serialized_candle = json.dumps(
                candle_data,
                sort_keys=True,
                separators=(",", ":"),
            )

            digest.update(serialized_candle.encode("utf-8"))
            digest.update(b"\n")

        return digest.hexdigest()
