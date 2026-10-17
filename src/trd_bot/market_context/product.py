from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import MarketType, Timeframe, TradingPair
from trd_bot.market_context.alignment import floor_market_context_boundary
from trd_bot.market_context.contracts import (
    MarketContextAssessmentStatus,
    MarketRegimeAssessment,
)


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context product timestamps must include timezone information")
    return value.astimezone(UTC)


class MarketContextUnavailableReason(StrEnum):
    ASSESSMENT_EXPIRED = "assessment_expired"
    ASSESSMENT_NOT_READY = "assessment_not_ready"
    BOUNDARY_MISMATCH = "boundary_mismatch"


class MarketContextProductView(BaseModel):
    """Explainable latest context with a fail-closed consumption decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-product-view-v1"] = "market-context-product-view-v1"
    evaluated_at: datetime
    expected_as_of: datetime
    consumable: bool
    unavailable_reasons: tuple[MarketContextUnavailableReason, ...]
    boundary_lag_seconds: int = Field(ge=0)
    seconds_until_expiry: int = Field(ge=0)
    assessment: MarketRegimeAssessment

    @field_validator("evaluated_at", "expected_as_of")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("unavailable_reasons")
    @classmethod
    def validate_reasons(
        cls,
        value: tuple[MarketContextUnavailableReason, ...],
    ) -> tuple[MarketContextUnavailableReason, ...]:
        if value != tuple(sorted(value, key=lambda item: item.value)):
            raise ValueError("market-context unavailable reasons must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("market-context unavailable reasons must be unique")
        return value

    @model_validator(mode="after")
    def validate_consumption_decision(self) -> Self:
        expected_as_of = floor_market_context_boundary(
            self.evaluated_at,
            Timeframe.HOUR_1,
        )
        if self.expected_as_of != expected_as_of:
            raise ValueError("market-context expected boundary is inconsistent")

        expected_reasons: set[MarketContextUnavailableReason] = set()
        if self.assessment.status is not MarketContextAssessmentStatus.READY:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_NOT_READY)
        if self.assessment.expires_at <= self.evaluated_at:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_EXPIRED)
        if self.assessment.as_of != self.expected_as_of:
            expected_reasons.add(MarketContextUnavailableReason.BOUNDARY_MISMATCH)
        ordered_reasons = tuple(sorted(expected_reasons, key=lambda item: item.value))
        if self.unavailable_reasons != ordered_reasons:
            raise ValueError("market-context unavailable reasons are inconsistent")
        if self.consumable != (not ordered_reasons):
            raise ValueError("market-context consumption decision is inconsistent")

        expected_lag = max(
            0,
            int((self.expected_as_of - self.assessment.as_of).total_seconds()),
        )
        if self.boundary_lag_seconds != expected_lag:
            raise ValueError("market-context boundary lag is inconsistent")
        expected_expiry = max(
            0,
            int((self.assessment.expires_at - self.evaluated_at).total_seconds()),
        )
        if self.seconds_until_expiry != expected_expiry:
            raise ValueError("market-context expiry countdown is inconsistent")
        return self

    @classmethod
    def from_assessment(
        cls,
        assessment: MarketRegimeAssessment,
        *,
        evaluated_at: datetime,
    ) -> Self:
        now = _normalize_timestamp(evaluated_at)
        expected_as_of = floor_market_context_boundary(now, Timeframe.HOUR_1)
        reasons: set[MarketContextUnavailableReason] = set()
        if assessment.status is not MarketContextAssessmentStatus.READY:
            reasons.add(MarketContextUnavailableReason.ASSESSMENT_NOT_READY)
        if assessment.expires_at <= now:
            reasons.add(MarketContextUnavailableReason.ASSESSMENT_EXPIRED)
        if assessment.as_of != expected_as_of:
            reasons.add(MarketContextUnavailableReason.BOUNDARY_MISMATCH)
        ordered_reasons = tuple(sorted(reasons, key=lambda item: item.value))
        return cls(
            evaluated_at=now,
            expected_as_of=expected_as_of,
            consumable=not ordered_reasons,
            unavailable_reasons=ordered_reasons,
            boundary_lag_seconds=max(
                0,
                int((expected_as_of - assessment.as_of).total_seconds()),
            ),
            seconds_until_expiry=max(
                0,
                int((assessment.expires_at - now).total_seconds()),
            ),
            assessment=assessment,
        )


class MarketContextProductReader(Protocol):
    def list_latest(
        self,
        *,
        limit: int,
        offset: int,
        source: str | None = None,
        pair: TradingPair | None = None,
        market_type: MarketType | None = None,
        evaluated_at: datetime | None = None,
    ) -> tuple[tuple[MarketContextProductView, ...], int]: ...

    def get(
        self,
        assessment_id: str,
        *,
        evaluated_at: datetime | None = None,
    ) -> MarketContextProductView | None: ...
