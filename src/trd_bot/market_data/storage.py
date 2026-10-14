import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.events import MarketDataEvent, MarketDataWatermark


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("text cannot be empty")
    return normalized


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _sha256(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class MarketDataRawObservation(BaseModel):
    """Immutable provider observation retained before normalization."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-raw-observation-v1"] = "market-data-raw-observation-v1"
    observation_id: str = Field(pattern=r"^market-raw-[a-f0-9]{16}$")
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    window_start: datetime
    window_end: datetime
    observed_at: datetime
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    payload: dict[str, JsonValue]
    created_at: datetime

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("window_start", "window_end", "observed_at", "created_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        if self.window_end <= self.window_start:
            raise ValueError("observation window end must be after its start")

        expected_checksum = _sha256(self.payload)
        if self.payload_checksum != expected_checksum:
            raise ValueError("raw observation payload checksum is inconsistent")

        expected_id = self.build_observation_id(
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            observed_at=self.observed_at,
            payload_checksum=self.payload_checksum,
        )
        if self.observation_id != expected_id:
            raise ValueError("raw observation ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        window_start: datetime,
        window_end: datetime,
        observed_at: datetime,
        payload: dict[str, JsonValue],
        created_at: datetime,
    ) -> Self:
        checksum = _sha256(payload)
        return cls(
            observation_id=cls.build_observation_id(
                source=source,
                pair=pair,
                timeframe=timeframe,
                observed_at=observed_at,
                payload_checksum=checksum,
            ),
            source=source,
            pair=pair,
            timeframe=timeframe,
            window_start=window_start,
            window_end=window_end,
            observed_at=observed_at,
            payload_checksum=checksum,
            payload=payload,
            created_at=created_at,
        )

    @staticmethod
    def build_observation_id(
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        observed_at: datetime,
        payload_checksum: str,
    ) -> str:
        identity = {
            "source": _normalize_text(source),
            "pair": pair.model_dump(mode="json"),
            "timeframe": timeframe.value,
            "observed_at": _normalize_timestamp(observed_at).isoformat(),
            "payload_checksum": payload_checksum,
        }
        return f"market-raw-{_sha256(identity)[:16]}"


class PersistedMarketDataEvent(BaseModel):
    """Normalized event plus immutable lineage to its raw observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event: MarketDataEvent
    raw_observation_id: str = Field(pattern=r"^market-raw-[a-f0-9]{16}$")
    persisted_at: datetime

    @field_validator("persisted_at")
    @classmethod
    def normalize_persisted_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)


class MarketDataInboxReceipt(BaseModel):
    """Longer-lived deduplication tombstone for one normalized event."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-inbox-v1"] = "market-data-inbox-v1"
    idempotency_key: str = Field(
        min_length=82,
        max_length=82,
        pattern=r"^market-data-event:[a-f0-9]{64}$",
    )
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    first_seen_at: datetime
    last_seen_at: datetime
    delivery_count: int = Field(ge=1)

    @field_validator("first_seen_at", "last_seen_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.last_seen_at < self.first_seen_at:
            raise ValueError("inbox last-seen time cannot precede first-seen time")
        return self

    @classmethod
    def from_event(cls, event: MarketDataEvent) -> Self:
        return cls(
            idempotency_key=event.idempotency_key,
            event_id=event.event_id,
            payload_checksum=event.payload_checksum,
            first_seen_at=event.observed_at,
            last_seen_at=event.observed_at,
            delivery_count=1,
        )

    def record_redelivery(self, *, observed_at: datetime) -> Self:
        normalized = _normalize_timestamp(observed_at)
        if normalized < self.first_seen_at:
            raise ValueError("redelivery time cannot precede first delivery")
        return self.model_copy(
            update={
                "last_seen_at": max(self.last_seen_at, normalized),
                "delivery_count": self.delivery_count + 1,
            }
        )


class MarketDataOutboxStatus(StrEnum):
    """Durable delivery state for a market-data outbox message."""

    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"


class MarketDataOutboxMessage(BaseModel):
    """Versioned message staged for a downstream internal consumer."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-outbox-v1"] = "market-data-outbox-v1"
    outbox_id: str = Field(pattern=r"^market-outbox-[a-f0-9]{16}$")
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    topic: str = Field(min_length=1, max_length=100)
    payload_version: str = Field(min_length=1, max_length=50)
    payload: dict[str, JsonValue]
    status: MarketDataOutboxStatus = MarketDataOutboxStatus.PENDING
    attempt_count: int = Field(default=0, ge=0, le=20)
    created_at: datetime
    available_at: datetime
    updated_at: datetime
    delivered_at: datetime | None = None
    error_code: str | None = Field(default=None, max_length=100)
    error_message: str | None = Field(default=None, max_length=500)

    @field_validator("topic", "payload_version")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("created_at", "available_at", "updated_at", "delivered_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if self.available_at < self.created_at or self.updated_at < self.created_at:
            raise ValueError("outbox timestamps cannot precede creation")

        if self.status is MarketDataOutboxStatus.PENDING:
            if self.delivered_at is not None or self.error_code is not None or self.error_message:
                raise ValueError("pending outbox message cannot contain a terminal result")
        elif self.status is MarketDataOutboxStatus.DELIVERED:
            if self.delivered_at is None or self.error_code is not None or self.error_message:
                raise ValueError("delivered outbox message requires delivery time only")
        elif self.delivered_at is not None or not self.error_code or not self.error_message:
            raise ValueError("failed outbox message requires sanitized error details")

        expected_id = self.build_outbox_id(
            event_id=self.event_id,
            topic=self.topic,
            payload_version=self.payload_version,
        )
        if self.outbox_id != expected_id:
            raise ValueError("outbox ID is inconsistent")
        return self

    @classmethod
    def from_event(
        cls,
        event: MarketDataEvent,
        *,
        topic: str,
        created_at: datetime,
    ) -> Self:
        return cls(
            outbox_id=cls.build_outbox_id(
                event_id=event.event_id,
                topic=topic,
                payload_version=event.schema_version,
            ),
            event_id=event.event_id,
            topic=topic,
            payload_version=event.schema_version,
            payload=event.model_dump(mode="json"),
            created_at=created_at,
            available_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def build_outbox_id(*, event_id: str, topic: str, payload_version: str) -> str:
        identity = {
            "event_id": event_id,
            "topic": _normalize_text(topic),
            "payload_version": _normalize_text(payload_version),
        }
        return f"market-outbox-{_sha256(identity)[:16]}"


class VersionedMarketDataWatermark(BaseModel):
    """Append-only persisted revision of one stream watermark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    watermark_id: str = Field(pattern=r"^market-watermark-[a-f0-9]{16}$")
    version: int = Field(ge=1)
    policy_version: str = Field(min_length=1, max_length=50)
    watermark: MarketDataWatermark
    stored_at: datetime

    @field_validator("policy_version")
    @classmethod
    def normalize_policy_version(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("stored_at")
    @classmethod
    def normalize_stored_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_identity(self) -> Self:
        expected = self.build_watermark_id(
            watermark=self.watermark,
            version=self.version,
            policy_version=self.policy_version,
        )
        if self.watermark_id != expected:
            raise ValueError("watermark persistence ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        watermark: MarketDataWatermark,
        version: int,
        policy_version: str,
        stored_at: datetime,
    ) -> Self:
        return cls(
            watermark_id=cls.build_watermark_id(
                watermark=watermark,
                version=version,
                policy_version=policy_version,
            ),
            version=version,
            policy_version=policy_version,
            watermark=watermark,
            stored_at=stored_at,
        )

    @staticmethod
    def build_watermark_id(
        *,
        watermark: MarketDataWatermark,
        version: int,
        policy_version: str,
    ) -> str:
        identity = {
            "source": watermark.source,
            "pair": watermark.pair.model_dump(mode="json"),
            "timeframe": watermark.timeframe.value,
            "version": version,
            "policy_version": _normalize_text(policy_version),
        }
        return f"market-watermark-{_sha256(identity)[:16]}"
