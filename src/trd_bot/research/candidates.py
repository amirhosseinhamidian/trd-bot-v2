import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.strategies.signals import SignalDirection, StrategySignal


class CandidateAction(StrEnum):
    """Research action represented by one candidate."""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"
    NO_TRADE = "no_trade"


class CandidateStatus(StrEnum):
    """Candidate lifecycle before simulated position creation."""

    CANDIDATE = "candidate"
    SELECTED = "selected"
    STALE = "stale"
    INVALIDATED = "invalidated"


class CandidateEvidence(BaseModel):
    """One traceable piece of evidence supporting a candidate."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    value: Decimal | None = None
    note: str | None = Field(default=None, min_length=1, max_length=500)

    @model_validator(mode="after")
    def evidence_must_have_content(self) -> Self:
        if self.value is None and self.note is None:
            raise ValueError("candidate evidence requires a value or note")

        return self


class CandidateEntryZone(BaseModel):
    """Inclusive paper-entry price zone."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    lower_price: Decimal = Field(gt=0)
    upper_price: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def validate_zone(self) -> Self:
        if self.upper_price < self.lower_price:
            raise ValueError("entry zone upper price cannot be lower than lower price")

        return self


class CandidateTarget(BaseModel):
    """One ordered research target used by the paper exit engine later."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    label: str = Field(min_length=1, max_length=50)
    price: Decimal = Field(gt=0)


class CandidateTradePlan(BaseModel):
    """Price-only trade plan attached to directional candidates."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    entry_zone: CandidateEntryZone
    invalidation_price: Decimal = Field(gt=0)
    targets: tuple[CandidateTarget, ...]

    @model_validator(mode="after")
    def validate_targets(self) -> Self:
        if not self.targets:
            raise ValueError("directional candidate requires at least one target")

        labels = [target.label for target in self.targets]
        if len(labels) != len(set(labels)):
            raise ValueError("candidate target labels must be unique")

        prices = [target.price for target in self.targets]
        if len(prices) != len(set(prices)):
            raise ValueError("candidate target prices must be unique")

        return self


def normalize_candidate_timestamp(value: datetime) -> datetime:
    """Normalize candidate timestamps to timezone-aware UTC."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("candidate timestamp must include timezone information")

    return value.astimezone(UTC)


def build_candidate_id(
    *,
    experiment_id: str,
    signal_id: str,
    action: CandidateAction,
    horizon_candles: int,
) -> str:
    """Build the deterministic identity of one experiment-backed candidate."""

    identity = "::".join(
        (
            experiment_id,
            signal_id,
            action.value,
            str(horizon_candles),
        )
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"candidate-{digest[:16]}"


class ResearchCandidate(BaseModel):
    """Traceable research opportunity derived from an immutable strategy signal."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    candidate_id: str = Field(pattern=r"^candidate-[a-f0-9]{16}$")

    experiment_id: str = Field(pattern=r"^experiment-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1, max_length=100)
    signal_id: str = Field(pattern=r"^signal-[a-f0-9]{16}$")

    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)

    pair: TradingPair
    timeframe: Timeframe
    horizon_candles: int = Field(ge=1)

    observed_at: datetime
    source_generated_at: datetime
    created_at: datetime
    valid_until: datetime

    source_direction: SignalDirection
    action: CandidateAction
    signal_score: Decimal = Field(ge=-1, le=1)
    confidence: Decimal = Field(ge=0, le=1)

    rationale: str = Field(min_length=1, max_length=1000)
    evidence: tuple[CandidateEvidence, ...]

    trade_plan: CandidateTradePlan | None = None

    status: CandidateStatus = CandidateStatus.CANDIDATE
    status_changed_at: datetime | None = None

    @field_validator(
        "observed_at",
        "source_generated_at",
        "created_at",
        "valid_until",
        "status_changed_at",
    )
    @classmethod
    def timestamps_must_be_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is None:
            return None

        return normalize_candidate_timestamp(value)

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.source_generated_at < self.observed_at:
            raise ValueError("signal generation cannot precede candidate observation")

        if self.created_at < self.source_generated_at:
            raise ValueError("candidate creation cannot precede source signal generation")

        if self.valid_until <= self.created_at:
            raise ValueError("candidate validity must extend beyond creation time")

        expected_id = build_candidate_id(
            experiment_id=self.experiment_id,
            signal_id=self.signal_id,
            action=self.action,
            horizon_candles=self.horizon_candles,
        )
        if self.candidate_id != expected_id:
            raise ValueError("candidate ID does not match its identity")

        if not self.evidence:
            raise ValueError("candidate requires at least one evidence item")

        evidence_keys = [(item.source, item.name) for item in self.evidence]
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("candidate evidence identities must be unique")

        self._validate_source_direction()
        self._validate_trade_plan()
        self._validate_status()

        return self

    def _validate_source_direction(self) -> None:
        if self.source_direction is SignalDirection.LONG and self.signal_score <= 0:
            raise ValueError("long source signal score must be greater than zero")

        if self.source_direction is SignalDirection.SHORT and self.signal_score >= 0:
            raise ValueError("short source signal score must be lower than zero")

        if self.source_direction is SignalDirection.NEUTRAL and self.signal_score != 0:
            raise ValueError("neutral source signal score must be zero")

        expected_action = {
            SignalDirection.LONG: CandidateAction.LONG,
            SignalDirection.SHORT: CandidateAction.SHORT,
            SignalDirection.NEUTRAL: CandidateAction.NEUTRAL,
        }[self.source_direction]

        if self.action not in (expected_action, CandidateAction.NO_TRADE):
            raise ValueError("candidate action cannot reverse its source signal")

    def _validate_trade_plan(self) -> None:
        directional = self.action in (
            CandidateAction.LONG,
            CandidateAction.SHORT,
        )

        if directional and self.trade_plan is None:
            raise ValueError("directional candidate requires a trade plan")

        if not directional and self.trade_plan is not None:
            raise ValueError("non-directional candidate cannot contain a trade plan")

        if self.trade_plan is None:
            return

        zone = self.trade_plan.entry_zone
        invalidation = self.trade_plan.invalidation_price
        target_prices = [target.price for target in self.trade_plan.targets]

        if self.action is CandidateAction.LONG:
            if invalidation >= zone.lower_price:
                raise ValueError("long invalidation must be below the entry zone")

            if any(price <= zone.upper_price for price in target_prices):
                raise ValueError("long targets must be above the entry zone")

            if any(later <= earlier for earlier, later in pairwise(target_prices)):
                raise ValueError("long targets must be ordered from lower to higher")

        if self.action is CandidateAction.SHORT:
            if invalidation <= zone.upper_price:
                raise ValueError("short invalidation must be above the entry zone")

            if any(price >= zone.lower_price for price in target_prices):
                raise ValueError("short targets must be below the entry zone")

            if any(later >= earlier for earlier, later in pairwise(target_prices)):
                raise ValueError("short targets must be ordered from higher to lower")

    def _validate_status(self) -> None:
        if self.status is CandidateStatus.CANDIDATE:
            if self.status_changed_at is not None:
                raise ValueError("fresh candidate cannot have status_changed_at")
            return

        if self.status_changed_at is None:
            raise ValueError("non-fresh candidate requires status_changed_at")

        if self.status_changed_at < self.created_at:
            raise ValueError("candidate status change cannot precede creation")

    def is_selectable(self, *, at: datetime) -> bool:
        """Return whether a candidate can be selected for paper simulation."""

        checked_at = normalize_candidate_timestamp(at)

        return (
            self.status is CandidateStatus.CANDIDATE
            and self.action in (CandidateAction.LONG, CandidateAction.SHORT)
            and self.created_at <= checked_at < self.valid_until
        )

    def select(self, *, selected_at: datetime) -> Self:
        """Select one still-valid directional candidate idempotently."""

        if self.status is CandidateStatus.SELECTED:
            return self

        if self.status is not CandidateStatus.CANDIDATE:
            raise ValueError("only fresh candidates can be selected")

        normalized_time = normalize_candidate_timestamp(selected_at)

        if not self.is_selectable(at=normalized_time):
            raise ValueError("candidate is not selectable at the requested time")

        return type(self).model_validate(
            {
                **self.model_dump(),
                "status": CandidateStatus.SELECTED,
                "status_changed_at": normalized_time,
            }
        )

    def mark_stale(self, *, stale_at: datetime) -> Self:
        """Mark an expired candidate stale idempotently."""

        if self.status is CandidateStatus.STALE:
            return self

        if self.status not in (
            CandidateStatus.CANDIDATE,
            CandidateStatus.SELECTED,
        ):
            raise ValueError("terminal candidate cannot become stale")

        normalized_time = normalize_candidate_timestamp(stale_at)

        if normalized_time < self.valid_until:
            raise ValueError("candidate cannot become stale before valid_until")

        return type(self).model_validate(
            {
                **self.model_dump(),
                "status": CandidateStatus.STALE,
                "status_changed_at": normalized_time,
            }
        )

    def invalidate(self, *, invalidated_at: datetime) -> Self:
        """Invalidate a candidate before simulated position creation."""

        if self.status is CandidateStatus.INVALIDATED:
            return self

        if self.status not in (
            CandidateStatus.CANDIDATE,
            CandidateStatus.SELECTED,
        ):
            raise ValueError("terminal candidate cannot be invalidated")

        normalized_time = normalize_candidate_timestamp(invalidated_at)

        if normalized_time < self.created_at:
            raise ValueError("candidate invalidation cannot precede creation")

        return type(self).model_validate(
            {
                **self.model_dump(),
                "status": CandidateStatus.INVALIDATED,
                "status_changed_at": normalized_time,
            }
        )


class CandidateBuilder:
    """Build reproducible candidates from historical strategy signals."""

    @staticmethod
    def from_signal(
        *,
        signal: StrategySignal,
        experiment_id: str,
        horizon_candles: int,
        confidence: Decimal,
        created_at: datetime,
        valid_until: datetime,
        trade_plan: CandidateTradePlan | None = None,
        action: CandidateAction | None = None,
        rationale: str | None = None,
    ) -> ResearchCandidate:
        source_action = {
            SignalDirection.LONG: CandidateAction.LONG,
            SignalDirection.SHORT: CandidateAction.SHORT,
            SignalDirection.NEUTRAL: CandidateAction.NEUTRAL,
        }[signal.direction]

        resolved_action = action or source_action

        if resolved_action not in (source_action, CandidateAction.NO_TRADE):
            raise ValueError("candidate action cannot reverse its source signal")

        evidence = (
            CandidateEvidence(
                source="strategy_signal",
                name="reason",
                note=signal.reason,
            ),
            *(
                CandidateEvidence(
                    source="strategy_feature",
                    name=feature.name,
                    value=feature.value,
                )
                for feature in signal.features
            ),
        )

        candidate_id = build_candidate_id(
            experiment_id=experiment_id,
            signal_id=signal.signal_id,
            action=resolved_action,
            horizon_candles=horizon_candles,
        )

        return ResearchCandidate(
            candidate_id=candidate_id,
            experiment_id=experiment_id,
            dataset_id=signal.dataset_id,
            signal_id=signal.signal_id,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            pair=signal.pair,
            timeframe=signal.timeframe,
            horizon_candles=horizon_candles,
            observed_at=signal.candle_close_time,
            source_generated_at=signal.generated_at,
            created_at=created_at,
            valid_until=valid_until,
            source_direction=signal.direction,
            action=resolved_action,
            signal_score=signal.score,
            confidence=confidence,
            rationale=rationale or signal.reason,
            evidence=evidence,
            trade_plan=trade_plan,
        )
