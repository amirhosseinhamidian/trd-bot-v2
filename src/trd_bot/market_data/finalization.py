import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.events import MarketDataWindowSnapshot, MarketDataWindowState
from trd_bot.market_data.storage import VersionedMarketDataWatermark


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("finalization timestamps must include timezone information")
    return value.astimezone(UTC)


def _stable_id(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class MarketDataFinalizationFreshnessOutcome(StrEnum):
    WITHIN_TARGET = "within_target"
    MISSED_TARGET = "missed_target"


class MarketDataWindowFinalization(BaseModel):
    """Immutable evidence binding a final window version to one watermark revision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-window-finalization-v1"] = (
        "market-data-window-finalization-v1"
    )
    finalization_id: str = Field(pattern=r"^market-finalization-[a-f0-9]{16}$")
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    provisional_version: int = Field(ge=1)
    finalized_version: int = Field(ge=2)
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    watermark_id: str = Field(pattern=r"^market-watermark-[a-f0-9]{16}$")
    watermark_version: int = Field(ge=1)
    policy_version: str = Field(min_length=1, max_length=50)
    window_end: datetime
    watermark_time: datetime
    finalized_at: datetime
    freshness_seconds: Decimal = Field(ge=0)
    freshness_target_seconds: int = Field(ge=1)
    freshness_outcome: MarketDataFinalizationFreshnessOutcome

    @field_validator("window_end", "watermark_time", "finalized_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.finalized_version != self.provisional_version + 1:
            raise ValueError("finalized window version must follow its provisional version")
        if self.window_end > self.watermark_time:
            raise ValueError("finalized window must have passed the recorded watermark")
        expected_freshness = Decimal(str((self.finalized_at - self.window_end).total_seconds()))
        if expected_freshness < 0 or self.freshness_seconds != expected_freshness:
            raise ValueError("window finalization freshness is inconsistent")
        expected_outcome = (
            MarketDataFinalizationFreshnessOutcome.WITHIN_TARGET
            if self.freshness_seconds <= Decimal(self.freshness_target_seconds)
            else MarketDataFinalizationFreshnessOutcome.MISSED_TARGET
        )
        if self.freshness_outcome is not expected_outcome:
            raise ValueError("window finalization freshness outcome is inconsistent")
        expected_id = self.build_finalization_id(
            window_id=self.window_id,
            finalized_version=self.finalized_version,
            watermark_id=self.watermark_id,
        )
        if self.finalization_id != expected_id:
            raise ValueError("window finalization ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        provisional: MarketDataWindowSnapshot,
        finalized: MarketDataWindowSnapshot,
        watermark: VersionedMarketDataWatermark,
        freshness_target_seconds: int,
    ) -> Self:
        if provisional.state is not MarketDataWindowState.PROVISIONAL:
            raise ValueError("finalization evidence requires a provisional source version")
        if finalized.state is not MarketDataWindowState.FINALIZED:
            raise ValueError("finalization evidence requires a finalized target version")
        if (
            finalized.window_id != provisional.window_id
            or finalized.version != provisional.version + 1
            or finalized.event_id != provisional.event_id
            or finalized.payload_checksum != provisional.payload_checksum
        ):
            raise ValueError("finalized snapshot does not preserve provisional lineage")
        stream = watermark.watermark
        if (
            stream.source != provisional.source
            or stream.pair != provisional.pair
            or stream.timeframe is not provisional.timeframe
        ):
            raise ValueError("finalization watermark does not match the window stream")
        if finalized.finalized_at is None:
            raise ValueError("finalized snapshot is missing its finalization time")

        freshness = Decimal(str((finalized.finalized_at - provisional.window_end).total_seconds()))
        outcome = (
            MarketDataFinalizationFreshnessOutcome.WITHIN_TARGET
            if freshness <= Decimal(freshness_target_seconds)
            else MarketDataFinalizationFreshnessOutcome.MISSED_TARGET
        )
        return cls(
            finalization_id=cls.build_finalization_id(
                window_id=provisional.window_id,
                finalized_version=finalized.version,
                watermark_id=watermark.watermark_id,
            ),
            window_id=provisional.window_id,
            source=provisional.source,
            pair=provisional.pair,
            timeframe=provisional.timeframe,
            provisional_version=provisional.version,
            finalized_version=finalized.version,
            event_id=provisional.event_id,
            payload_checksum=provisional.payload_checksum,
            watermark_id=watermark.watermark_id,
            watermark_version=watermark.version,
            policy_version=watermark.policy_version,
            window_end=provisional.window_end,
            watermark_time=stream.watermark_time,
            finalized_at=finalized.finalized_at,
            freshness_seconds=freshness,
            freshness_target_seconds=freshness_target_seconds,
            freshness_outcome=outcome,
        )

    @staticmethod
    def build_finalization_id(
        *,
        window_id: str,
        finalized_version: int,
        watermark_id: str,
    ) -> str:
        return "market-finalization-" + _stable_id(
            {
                "window_id": window_id,
                "finalized_version": finalized_version,
                "watermark_id": watermark_id,
            }
        )
