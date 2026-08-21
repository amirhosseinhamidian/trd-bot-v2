import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime

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


class InvalidDatasetError(ValueError):
    """Raised when market data fails quality validation."""

    def __init__(self, report: DataQualityReport) -> None:
        self.report = report

        issue_codes = ", ".join(issue.code.value for issue in report.issues)

        super().__init__(f"Dataset failed quality checks: {issue_codes}")


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
    ) -> DatasetSnapshot:
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
            created_at=datetime.now(UTC),
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
