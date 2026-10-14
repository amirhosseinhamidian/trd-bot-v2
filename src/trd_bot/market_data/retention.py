import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, Self
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-data retention timestamps must include timezone information")
    return value.astimezone(UTC)


def _stable_id(prefix: str, value: object) -> str:
    canonical = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:16]}"


class MarketDataRetentionMode(StrEnum):
    DRY_RUN = "dry_run"
    EXECUTE = "execute"


class MarketDataRetentionOutcome(StrEnum):
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class MarketDataRetentionHoldKind(StrEnum):
    LEGAL = "legal"
    INCIDENT = "incident"


class MarketDataRetentionCutoffs(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_observations_before: datetime
    normalized_events_before: datetime
    inbox_receipts_before: datetime
    delivered_outbox_before: datetime
    failed_outbox_before: datetime
    provisional_windows_finalized_before: datetime
    revision_evidence_before: datetime
    orphan_watermarks_before: datetime

    @field_validator("*")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)


class MarketDataRetentionCounts(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    raw_observations: int = Field(default=0, ge=0)
    normalized_events: int = Field(default=0, ge=0)
    event_decisions: int = Field(default=0, ge=0)
    inbox_receipts: int = Field(default=0, ge=0)
    delivered_outbox: int = Field(default=0, ge=0)
    failed_outbox: int = Field(default=0, ge=0)
    provisional_windows: int = Field(default=0, ge=0)
    replay_requests: int = Field(default=0, ge=0)
    window_revisions: int = Field(default=0, ge=0)
    orphan_watermarks: int = Field(default=0, ge=0)

    @property
    def total(self) -> int:
        return sum(
            (
                self.raw_observations,
                self.normalized_events,
                self.event_decisions,
                self.inbox_receipts,
                self.delivered_outbox,
                self.failed_outbox,
                self.provisional_windows,
                self.replay_requests,
                self.window_revisions,
                self.orphan_watermarks,
            )
        )


class MarketDataRetentionHold(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-retention-hold-v1"] = "market-data-retention-hold-v1"
    hold_id: str = Field(pattern=r"^market-retention-hold-[a-f0-9]{16}$")
    kind: MarketDataRetentionHoldKind
    reason: str = Field(min_length=1, max_length=500)
    placed_by: str = Field(min_length=1, max_length=100)
    placed_at: datetime
    released_by: str | None = Field(default=None, min_length=1, max_length=100)
    released_at: datetime | None = None

    @field_validator("reason", "placed_by", "released_by")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("market-data retention hold text cannot be empty")
        return normalized

    @field_validator("placed_at", "released_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_lifecycle(self) -> Self:
        if (self.released_by is None) != (self.released_at is None):
            raise ValueError("retention hold release actor and time must be stored together")
        if self.released_at is not None and self.released_at < self.placed_at:
            raise ValueError("retention hold release cannot precede placement")
        return self

    @property
    def active(self) -> bool:
        return self.released_at is None

    @classmethod
    def place(
        cls,
        *,
        kind: MarketDataRetentionHoldKind,
        reason: str,
        placed_by: str,
        placed_at: datetime,
    ) -> Self:
        normalized = _normalize_timestamp(placed_at)
        return cls(
            hold_id=_stable_id(
                "market-retention-hold",
                {
                    "nonce": uuid4().hex,
                    "kind": kind.value,
                    "placed_at": normalized.isoformat(),
                },
            ),
            kind=kind,
            reason=reason,
            placed_by=placed_by,
            placed_at=normalized,
        )

    def release(self, *, released_by: str, released_at: datetime) -> Self:
        if not self.active:
            raise ValueError("market-data retention hold is already released")
        return type(self).model_validate(
            self.model_copy(
                update={
                    "released_by": released_by,
                    "released_at": _normalize_timestamp(released_at),
                }
            ).model_dump()
        )


class MarketDataRetentionRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-data-retention-run-v1"] = "market-data-retention-run-v1"
    run_id: str = Field(pattern=r"^market-retention-run-[a-f0-9]{16}$")
    policy_version: Literal["market-data-service-level-policy-v1"] = (
        "market-data-service-level-policy-v1"
    )
    mode: MarketDataRetentionMode
    outcome: MarketDataRetentionOutcome
    requested_by: str = Field(min_length=1, max_length=100)
    requested_at: datetime
    completed_at: datetime
    batch_limit: int = Field(ge=1, le=500)
    cutoffs: MarketDataRetentionCutoffs
    selected: MarketDataRetentionCounts
    deleted_count: int = Field(ge=0)
    blocking_hold_ids: tuple[str, ...] = ()
    error_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("requested_by")
    @classmethod
    def normalize_requested_by(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("market-data retention requester cannot be empty")
        return normalized

    @field_validator("requested_at", "completed_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.completed_at < self.requested_at:
            raise ValueError("retention completion cannot precede its request")
        if self.selected.total > self.batch_limit:
            raise ValueError("retention selection cannot exceed the shared batch limit")
        if self.mode is MarketDataRetentionMode.DRY_RUN and self.deleted_count != 0:
            raise ValueError("retention dry-run cannot delete rows")
        if self.outcome is MarketDataRetentionOutcome.COMPLETED:
            expected = 0 if self.mode is MarketDataRetentionMode.DRY_RUN else self.selected.total
            if (
                self.blocking_hold_ids
                or self.error_code is not None
                or self.deleted_count != expected
            ):
                raise ValueError("completed retention outcome is inconsistent")
        elif self.outcome is MarketDataRetentionOutcome.BLOCKED:
            if (
                not self.blocking_hold_ids
                or self.selected.total != 0
                or self.deleted_count != 0
                or self.error_code is not None
            ):
                raise ValueError("blocked retention outcome is inconsistent")
        elif (
            self.error_code is None
            or self.blocking_hold_ids
            or self.selected.total != 0
            or self.deleted_count != 0
        ):
            raise ValueError("failed retention outcome is inconsistent")
        return self

    @classmethod
    def build_run_id(cls, *, requested_by: str, requested_at: datetime) -> str:
        return _stable_id(
            "market-retention-run",
            {
                "nonce": uuid4().hex,
                "requested_by": requested_by.strip(),
                "requested_at": _normalize_timestamp(requested_at).isoformat(),
            },
        )


class MarketDataRetentionManager(Protocol):
    def place_hold(
        self,
        *,
        kind: MarketDataRetentionHoldKind,
        reason: str,
        requested_by: str,
        now: datetime | None = None,
    ) -> MarketDataRetentionHold: ...

    def release_hold(
        self,
        hold_id: str,
        *,
        requested_by: str,
        now: datetime | None = None,
    ) -> MarketDataRetentionHold: ...

    def list_active_holds(self) -> tuple[MarketDataRetentionHold, ...]: ...

    def list_runs(self, *, limit: int = 20) -> tuple[MarketDataRetentionRun, ...]: ...

    def run(
        self,
        *,
        mode: MarketDataRetentionMode,
        requested_by: str,
        batch_limit: int,
        now: datetime | None = None,
    ) -> MarketDataRetentionRun: ...
