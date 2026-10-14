import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataEventReason,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
)
from trd_bot.market_data.storage import (
    PersistedMarketDataEventDecision,
    VersionedMarketDataWatermark,
)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("replay timestamps must include timezone information")
    return value.astimezone(UTC)


def _stable_id(value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class MarketDataReplayRequest(BaseModel):
    """Immutable authorization to replay one persisted revision-required decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-replay-request-v1"] = "market-data-replay-request-v1"
    replay_id: str = Field(pattern=r"^market-replay-[a-f0-9]{16}$")
    decision_id: str = Field(pattern=r"^market-decision-[a-f0-9]{16}$")
    observation_id: str = Field(pattern=r"^market-raw-[a-f0-9]{16}$")
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    reason: MarketDataEventReason
    requested_by: str = Field(min_length=1, max_length=100)
    requested_at: datetime

    @field_validator("requested_by")
    @classmethod
    def normalize_requested_by(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("replay requester cannot be empty")
        return normalized

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.reason not in {
            MarketDataEventReason.LATE_ARRIVAL,
            MarketDataEventReason.FINALIZED_WINDOW_CONFLICT,
        }:
            raise ValueError("replay request requires a revision-required reason")
        expected = self.build_replay_id(self.decision_id)
        if self.replay_id != expected:
            raise ValueError("market-data replay ID is inconsistent")
        return self

    @classmethod
    def from_decision(
        cls,
        record: PersistedMarketDataEventDecision,
        *,
        requested_by: str,
        requested_at: datetime,
    ) -> Self:
        decision = record.decision
        if not decision.requires_replay:
            raise ValueError("only revision-required decisions can be replayed")
        return cls(
            replay_id=cls.build_replay_id(record.decision_id),
            decision_id=record.decision_id,
            observation_id=record.observation_id,
            event_id=decision.event_id,
            window_id=decision.window_id,
            reason=decision.reason,
            requested_by=requested_by,
            requested_at=requested_at,
        )

    @staticmethod
    def build_replay_id(decision_id: str) -> str:
        return "market-replay-" + _stable_id({"decision_id": decision_id})


class MarketDataRevisionKind(StrEnum):
    LATE_INSERT = "late_insert"
    CORRECTION = "correction"


class MarketDataWindowRevision(BaseModel):
    """Immutable evidence for one replay-created finalized window version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-window-revision-v1"] = "market-data-window-revision-v1"
    revision_id: str = Field(pattern=r"^market-revision-[a-f0-9]{16}$")
    replay_id: str = Field(pattern=r"^market-replay-[a-f0-9]{16}$")
    decision_id: str = Field(pattern=r"^market-decision-[a-f0-9]{16}$")
    observation_id: str = Field(pattern=r"^market-raw-[a-f0-9]{16}$")
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    reason: MarketDataEventReason
    kind: MarketDataRevisionKind
    previous_version: int | None = Field(default=None, ge=1)
    previous_event_id: str | None = Field(
        default=None,
        pattern=r"^market-event-[a-f0-9]{16}$",
    )
    previous_payload_checksum: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    revised_version: int = Field(ge=1)
    revised_payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    watermark_id: str = Field(pattern=r"^market-watermark-[a-f0-9]{16}$")
    watermark_version: int = Field(ge=1)
    watermark_time: datetime
    applied_at: datetime

    @field_validator("watermark_time", "applied_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_revision(self) -> Self:
        has_previous = self.previous_version is not None
        if has_previous != (self.previous_event_id is not None):
            raise ValueError("revision previous event lineage is incomplete")
        if has_previous != (self.previous_payload_checksum is not None):
            raise ValueError("revision previous payload lineage is incomplete")
        if self.kind is MarketDataRevisionKind.LATE_INSERT:
            if has_previous or self.revised_version != 1:
                raise ValueError("late insert must create the first window version")
        else:
            if self.previous_version is None:
                raise ValueError("correction requires a previous window version")
            if self.revised_version != self.previous_version + 1:
                raise ValueError("correction must follow the previous window version")
        expected = self.build_revision_id(
            replay_id=self.replay_id,
            revised_version=self.revised_version,
        )
        if self.revision_id != expected:
            raise ValueError("market-data revision ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        request: MarketDataReplayRequest,
        event: MarketDataEvent,
        previous: MarketDataWindowSnapshot | None,
        revised: MarketDataWindowSnapshot,
        watermark: VersionedMarketDataWatermark,
        applied_at: datetime,
    ) -> Self:
        if revised.state is not MarketDataWindowState.FINALIZED:
            raise ValueError("replay revision must produce a finalized snapshot")
        if revised.event_id != event.event_id or revised.window_id != event.window_id:
            raise ValueError("revised snapshot does not match the replay event")
        if request.event_id != event.event_id or request.window_id != event.window_id:
            raise ValueError("replay request does not match its event")
        kind = (
            MarketDataRevisionKind.LATE_INSERT
            if previous is None
            else MarketDataRevisionKind.CORRECTION
        )
        return cls(
            revision_id=cls.build_revision_id(
                replay_id=request.replay_id,
                revised_version=revised.version,
            ),
            replay_id=request.replay_id,
            decision_id=request.decision_id,
            observation_id=request.observation_id,
            event_id=event.event_id,
            window_id=event.window_id,
            reason=request.reason,
            kind=kind,
            previous_version=None if previous is None else previous.version,
            previous_event_id=None if previous is None else previous.event_id,
            previous_payload_checksum=(None if previous is None else previous.payload_checksum),
            revised_version=revised.version,
            revised_payload_checksum=revised.payload_checksum,
            watermark_id=watermark.watermark_id,
            watermark_version=watermark.version,
            watermark_time=watermark.watermark.watermark_time,
            applied_at=applied_at,
        )

    @staticmethod
    def build_revision_id(*, replay_id: str, revised_version: int) -> str:
        return "market-revision-" + _stable_id(
            {"replay_id": replay_id, "revised_version": revised_version}
        )


def build_revised_market_data_window(
    *,
    event: MarketDataEvent,
    previous: MarketDataWindowSnapshot | None,
    watermark: VersionedMarketDataWatermark,
    revised_at: datetime,
) -> MarketDataWindowSnapshot:
    """Create a finalized append-only revision without changing the watermark."""

    normalized = _normalize_timestamp(revised_at)
    stream = watermark.watermark
    if (
        stream.source != event.source
        or stream.pair != event.pair
        or stream.timeframe is not event.timeframe
    ):
        raise ValueError("replay watermark does not match the event stream")
    if event.event_time > stream.watermark_time:
        raise ValueError("replay event has not passed the recorded watermark")
    if not event.candle.is_closed:
        raise ValueError("open candle cannot create a finalized replay revision")
    if normalized < event.event_time:
        raise ValueError("replay application cannot precede the event window")
    if previous is not None and previous.window_id != event.window_id:
        raise ValueError("previous snapshot does not match the replay window")

    return MarketDataWindowSnapshot(
        window_id=event.window_id,
        version=1 if previous is None else previous.version + 1,
        state=MarketDataWindowState.FINALIZED,
        source=event.source,
        pair=event.pair,
        timeframe=event.timeframe,
        window_start=event.candle.open_time,
        window_end=event.candle.close_time,
        event_id=event.event_id,
        payload_checksum=event.payload_checksum,
        candle=event.candle,
        created_at=normalized if previous is None else previous.created_at,
        finalized_at=normalized,
    )
