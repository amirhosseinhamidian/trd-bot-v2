import hashlib
import json
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair


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


def calculate_candle_payload_checksum(candle: OHLCVCandle) -> str:
    """Hash normalized candle content while ignoring transport receipt time."""

    payload = candle.model_dump(mode="json", exclude={"received_at"})
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def build_market_data_window_id(
    *,
    source: str,
    pair: TradingPair,
    timeframe: Timeframe,
    window_start: datetime,
    window_end: datetime,
) -> str:
    """Build the stable identity shared by provisional and corrected content."""

    identity = {
        "source": _normalize_text(source),
        "pair": pair.model_dump(mode="json"),
        "timeframe": timeframe.value,
        "window_start": _normalize_timestamp(window_start).isoformat(),
        "window_end": _normalize_timestamp(window_end).isoformat(),
    }
    digest = hashlib.sha256(_canonical_json(identity).encode("utf-8")).hexdigest()
    return f"market-window-{digest[:16]}"


def build_market_data_event_idempotency_key(candle: OHLCVCandle) -> str:
    """Identify duplicate delivery without hiding a corrected payload."""

    window_id = build_market_data_window_id(
        source=candle.source,
        pair=candle.pair,
        timeframe=candle.timeframe,
        window_start=candle.open_time,
        window_end=candle.close_time,
    )
    payload_checksum = calculate_candle_payload_checksum(candle)
    digest = hashlib.sha256(f"{window_id}:{payload_checksum}".encode()).hexdigest()
    return f"market-data-event:{digest}"


class MarketDataEventKind(StrEnum):
    """Version-one market event kinds."""

    CANDLE_OBSERVED = "candle_observed"


class MarketDataEvent(BaseModel):
    """Immutable normalized event envelope for one candle observation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-event-v1"] = "market-data-event-v1"
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    kind: Literal[MarketDataEventKind.CANDLE_OBSERVED] = MarketDataEventKind.CANDLE_OBSERVED

    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    event_time: datetime
    observed_at: datetime

    payload_version: Literal["ohlcv-candle-v1"] = "ohlcv-candle-v1"
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    idempotency_key: str = Field(
        min_length=82,
        max_length=82,
        pattern=r"^market-data-event:[a-f0-9]{64}$",
    )
    candle: OHLCVCandle

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("event_time", "observed_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.source != self.candle.source:
            raise ValueError("event source does not match candle source")
        if self.pair != self.candle.pair:
            raise ValueError("event pair does not match candle pair")
        if self.timeframe is not self.candle.timeframe:
            raise ValueError("event timeframe does not match candle timeframe")
        if self.event_time != self.candle.close_time:
            raise ValueError("candle event time must equal candle close time")
        if self.observed_at != self.candle.received_at:
            raise ValueError("event observation time must equal candle receipt time")

        expected_checksum = calculate_candle_payload_checksum(self.candle)
        if self.payload_checksum != expected_checksum:
            raise ValueError("event payload checksum is inconsistent")

        expected_key = build_market_data_event_idempotency_key(self.candle)
        if self.idempotency_key != expected_key:
            raise ValueError("event idempotency key is inconsistent")

        expected_event_id = f"market-event-{expected_key.rsplit(':', maxsplit=1)[1][:16]}"
        if self.event_id != expected_event_id:
            raise ValueError("event ID is inconsistent")

        return self

    @classmethod
    def from_candle(cls, candle: OHLCVCandle) -> Self:
        """Build the canonical v1 event for a normalized candle."""

        idempotency_key = build_market_data_event_idempotency_key(candle)
        digest = idempotency_key.rsplit(":", maxsplit=1)[1]
        return cls(
            event_id=f"market-event-{digest[:16]}",
            source=candle.source,
            pair=candle.pair,
            timeframe=candle.timeframe,
            event_time=candle.close_time,
            observed_at=candle.received_at,
            payload_checksum=calculate_candle_payload_checksum(candle),
            idempotency_key=idempotency_key,
            candle=candle,
        )

    @property
    def window_id(self) -> str:
        return build_market_data_window_id(
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            window_start=self.candle.open_time,
            window_end=self.candle.close_time,
        )


class MarketDataArrivalClass(StrEnum):
    """Relationship between event time and the stream watermark."""

    ON_TIME = "on_time"
    LATE = "late"


class MarketDataWatermark(BaseModel):
    """Monotonic event-time progress for one exact market-data stream."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-watermark-v1"] = "market-data-watermark-v1"
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    high_water_event_time: datetime
    allowed_lateness_seconds: int = Field(ge=0)
    watermark_time: datetime
    calculated_at: datetime

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("high_water_event_time", "watermark_time", "calculated_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_watermark(self) -> Self:
        expected = self.high_water_event_time - timedelta(seconds=self.allowed_lateness_seconds)
        if self.watermark_time != expected:
            raise ValueError("watermark time is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        high_water_event_time: datetime,
        allowed_lateness_seconds: int,
        calculated_at: datetime,
    ) -> Self:
        normalized_high_water = _normalize_timestamp(high_water_event_time)
        return cls(
            source=source,
            pair=pair,
            timeframe=timeframe,
            high_water_event_time=normalized_high_water,
            allowed_lateness_seconds=allowed_lateness_seconds,
            watermark_time=normalized_high_water - timedelta(seconds=allowed_lateness_seconds),
            calculated_at=calculated_at,
        )

    def classify(self, event: MarketDataEvent) -> MarketDataArrivalClass:
        self._require_same_stream(event)
        if event.event_time <= self.watermark_time:
            return MarketDataArrivalClass.LATE
        return MarketDataArrivalClass.ON_TIME

    def advance(
        self,
        event: MarketDataEvent,
        *,
        calculated_at: datetime,
    ) -> Self:
        """Return a watermark that never moves backwards."""

        self._require_same_stream(event)
        normalized_calculated_at = _normalize_timestamp(calculated_at)
        if normalized_calculated_at < self.calculated_at:
            raise ValueError("watermark calculation time cannot move backwards")
        high_water = max(self.high_water_event_time, event.event_time)
        return type(self).build(
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            high_water_event_time=high_water,
            allowed_lateness_seconds=self.allowed_lateness_seconds,
            calculated_at=normalized_calculated_at,
        )

    def _require_same_stream(self, event: MarketDataEvent) -> None:
        if (
            event.source != self.source
            or event.pair != self.pair
            or event.timeframe is not self.timeframe
        ):
            raise ValueError("event does not belong to watermark stream")


class MarketDataWindowState(StrEnum):
    """Lifecycle state of one immutable window version."""

    PROVISIONAL = "provisional"
    FINALIZED = "finalized"


class MarketDataWindowSnapshot(BaseModel):
    """One immutable version of a normalized market-data window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-window-v1"] = "market-data-window-v1"
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    version: int = Field(ge=1)
    state: MarketDataWindowState

    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    window_start: datetime
    window_end: datetime

    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    candle: OHLCVCandle

    created_at: datetime
    finalized_at: datetime | None = None

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("window_start", "window_end", "created_at", "finalized_at")
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_snapshot(self) -> Self:
        expected_window_id = build_market_data_window_id(
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            window_start=self.window_start,
            window_end=self.window_end,
        )
        if self.window_id != expected_window_id:
            raise ValueError("window ID is inconsistent")
        if self.source != self.candle.source:
            raise ValueError("window source does not match candle source")
        if self.pair != self.candle.pair or self.timeframe is not self.candle.timeframe:
            raise ValueError("window market identity does not match candle")
        if self.window_start != self.candle.open_time or self.window_end != self.candle.close_time:
            raise ValueError("window bounds do not match candle bounds")
        if self.payload_checksum != calculate_candle_payload_checksum(self.candle):
            raise ValueError("window payload checksum is inconsistent")
        expected_event = MarketDataEvent.from_candle(self.candle)
        if self.event_id != expected_event.event_id:
            raise ValueError("window event ID is inconsistent")

        if self.state is MarketDataWindowState.PROVISIONAL:
            if self.finalized_at is not None:
                raise ValueError("provisional window cannot have finalization time")
        else:
            if self.finalized_at is None:
                raise ValueError("finalized window requires finalization time")
            if not self.candle.is_closed:
                raise ValueError("open candle cannot finalize a market-data window")
            if self.finalized_at < self.created_at:
                raise ValueError("window finalization cannot precede creation")

        return self

    @classmethod
    def from_event(
        cls,
        event: MarketDataEvent,
        *,
        version: int,
        created_at: datetime,
    ) -> Self:
        return cls(
            window_id=event.window_id,
            version=version,
            state=MarketDataWindowState.PROVISIONAL,
            source=event.source,
            pair=event.pair,
            timeframe=event.timeframe,
            window_start=event.candle.open_time,
            window_end=event.candle.close_time,
            event_id=event.event_id,
            payload_checksum=event.payload_checksum,
            candle=event.candle,
            created_at=created_at,
        )

    def finalize(
        self,
        watermark: MarketDataWatermark,
        *,
        finalized_at: datetime,
    ) -> Self:
        """Create a new final version without mutating the provisional snapshot."""

        if self.state is MarketDataWindowState.FINALIZED:
            raise ValueError("market-data window is already finalized")
        if not self.candle.is_closed:
            raise ValueError("open candle cannot finalize a market-data window")
        watermark._require_same_stream(MarketDataEvent.from_candle(self.candle))
        if self.window_end > watermark.watermark_time:
            raise ValueError("market-data window has not passed the watermark")

        return type(self)(
            window_id=self.window_id,
            version=self.version + 1,
            state=MarketDataWindowState.FINALIZED,
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            window_start=self.window_start,
            window_end=self.window_end,
            event_id=self.event_id,
            payload_checksum=self.payload_checksum,
            candle=self.candle,
            created_at=self.created_at,
            finalized_at=finalized_at,
        )


class MarketDataEventDisposition(StrEnum):
    """Mutation intent produced by the pure event-decision policy."""

    ACCEPTED = "accepted"
    DUPLICATE = "duplicate"
    REVISION_REQUIRED = "revision_required"


class MarketDataEventReason(StrEnum):
    """Stable machine-readable reasons for event processing decisions."""

    NEW_WINDOW = "new_window"
    PROVISIONAL_UPDATE = "provisional_update"
    DUPLICATE_PAYLOAD = "duplicate_payload"
    LATE_ARRIVAL = "late_arrival"
    FINALIZED_WINDOW_CONFLICT = "finalized_window_conflict"


class MarketDataEventDecision(BaseModel):
    """Auditable result of evaluating one event against current window state."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-event-decision-v1"] = "market-data-event-decision-v1"
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    arrival: MarketDataArrivalClass
    disposition: MarketDataEventDisposition
    reason: MarketDataEventReason
    existing_window_version: int | None = Field(default=None, ge=1)
    proposed_window_version: int | None = Field(default=None, ge=1)
    requires_replay: bool = False
    decided_at: datetime

    @field_validator("decided_at")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_decision(self) -> Self:
        if self.disposition is MarketDataEventDisposition.DUPLICATE:
            if self.proposed_window_version is not None or self.requires_replay:
                raise ValueError("duplicate decision cannot propose a new version or replay")
        elif self.proposed_window_version is None:
            raise ValueError("mutating decision requires a proposed window version")

        requires_replay = self.disposition is MarketDataEventDisposition.REVISION_REQUIRED
        if self.requires_replay is not requires_replay:
            raise ValueError("decision replay flag is inconsistent")
        return self


def decide_market_data_event(
    event: MarketDataEvent,
    *,
    watermark: MarketDataWatermark,
    existing_window: MarketDataWindowSnapshot | None,
    decided_at: datetime,
) -> MarketDataEventDecision:
    """Evaluate duplicate, correction and late-event behavior without persistence."""

    arrival = watermark.classify(event)

    if existing_window is not None and existing_window.window_id != event.window_id:
        raise ValueError("existing window does not match event window")

    if existing_window is not None and existing_window.payload_checksum == event.payload_checksum:
        return MarketDataEventDecision(
            event_id=event.event_id,
            window_id=event.window_id,
            arrival=arrival,
            disposition=MarketDataEventDisposition.DUPLICATE,
            reason=MarketDataEventReason.DUPLICATE_PAYLOAD,
            existing_window_version=existing_window.version,
            decided_at=decided_at,
        )

    existing_version = None if existing_window is None else existing_window.version
    proposed_version = 1 if existing_window is None else existing_window.version + 1

    if existing_window is not None and existing_window.state is MarketDataWindowState.FINALIZED:
        return MarketDataEventDecision(
            event_id=event.event_id,
            window_id=event.window_id,
            arrival=arrival,
            disposition=MarketDataEventDisposition.REVISION_REQUIRED,
            reason=MarketDataEventReason.FINALIZED_WINDOW_CONFLICT,
            existing_window_version=existing_window.version,
            proposed_window_version=proposed_version,
            requires_replay=True,
            decided_at=decided_at,
        )

    if arrival is MarketDataArrivalClass.LATE:
        return MarketDataEventDecision(
            event_id=event.event_id,
            window_id=event.window_id,
            arrival=arrival,
            disposition=MarketDataEventDisposition.REVISION_REQUIRED,
            reason=MarketDataEventReason.LATE_ARRIVAL,
            existing_window_version=existing_version,
            proposed_window_version=proposed_version,
            requires_replay=True,
            decided_at=decided_at,
        )

    return MarketDataEventDecision(
        event_id=event.event_id,
        window_id=event.window_id,
        arrival=arrival,
        disposition=MarketDataEventDisposition.ACCEPTED,
        reason=(
            MarketDataEventReason.NEW_WINDOW
            if existing_window is None
            else MarketDataEventReason.PROVISIONAL_UPDATE
        ),
        existing_window_version=existing_version,
        proposed_window_version=proposed_version,
        decided_at=decided_at,
    )
