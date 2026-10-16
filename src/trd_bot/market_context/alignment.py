from datetime import UTC, datetime
from enum import StrEnum
from itertools import pairwise
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_context.contracts import (
    MarketContextAlignmentPolicy,
    MarketContextFeatureSetDefinition,
    MarketContextInputManifest,
    MarketContextWindowReference,
    default_market_context_alignment_policy,
)
from trd_bot.market_data.events import MarketDataWindowSnapshot, MarketDataWindowState

_TIMEFRAME_ORDER = {
    Timeframe.HOUR_1: 0,
    Timeframe.HOURS_4: 1,
    Timeframe.DAY_1: 2,
}


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")
    return value.astimezone(UTC)


def floor_market_context_boundary(value: datetime, timeframe: Timeframe) -> datetime:
    """Return the UTC event-time boundary at or before ``value``."""

    normalized = _normalize_timestamp(value)
    duration_seconds = int(timeframe.duration.total_seconds())
    boundary = int(normalized.timestamp()) // duration_seconds * duration_seconds
    return datetime.fromtimestamp(boundary, tz=UTC)


class MarketContextAlignmentStatus(StrEnum):
    """Whether aligned inputs are complete enough to build a manifest."""

    READY = "ready"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"


class MarketContextAlignmentIssueCode(StrEnum):
    """Stable machine-readable reasons for a non-ready alignment."""

    NO_FINALIZED_WINDOWS = "no_finalized_windows"
    INSUFFICIENT_HISTORY = "insufficient_history"
    WINDOW_GAP = "window_gap"
    STALE_LATEST_WINDOW = "stale_latest_window"


class MarketContextTimeframeCoverage(BaseModel):
    """Alignment evidence for one required timeframe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-timeframe-coverage-v1"] = (
        "market-context-timeframe-coverage-v1"
    )
    timeframe: Timeframe
    required_windows: int = Field(ge=1)
    available_windows: int = Field(ge=0)
    matched_windows: int = Field(ge=0)
    expected_latest_window_end: datetime
    latest_observed_window_end: datetime | None
    missing_window_starts: tuple[datetime, ...] = ()
    status: MarketContextAlignmentStatus
    issue_codes: tuple[MarketContextAlignmentIssueCode, ...] = ()

    @field_validator(
        "expected_latest_window_end",
        "latest_observed_window_end",
    )
    @classmethod
    def normalize_optional_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _normalize_timestamp(value)

    @field_validator("missing_window_starts")
    @classmethod
    def normalize_missing_starts(cls, value: tuple[datetime, ...]) -> tuple[datetime, ...]:
        return tuple(_normalize_timestamp(item) for item in value)

    @model_validator(mode="after")
    def validate_coverage(self) -> Self:
        if self.timeframe not in _TIMEFRAME_ORDER:
            raise ValueError("coverage timeframe is outside the v1 alignment policy")
        if self.matched_windows > self.required_windows:
            raise ValueError("matched windows cannot exceed required windows")
        if self.available_windows < self.matched_windows:
            raise ValueError("available windows cannot be fewer than matched windows")
        if self.status is MarketContextAlignmentStatus.READY:
            if self.issue_codes or self.missing_window_starts:
                raise ValueError("ready coverage cannot contain alignment issues")
            if self.matched_windows != self.required_windows:
                raise ValueError("ready coverage must match every required window")
        elif not self.issue_codes:
            raise ValueError("non-ready coverage requires an issue code")
        return self


class MarketContextAlignmentResult(BaseModel):
    """Deterministic outcome of assembling a multi-timeframe input dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-alignment-result-v1"] = (
        "market-context-alignment-result-v1"
    )
    policy_version: Literal["market-context-alignment-policy-v1"] = (
        "market-context-alignment-policy-v1"
    )
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    as_of: datetime
    feature_set_version: str = Field(pattern=r"^market-context-features-v[1-9][0-9]*$")
    feature_set_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    status: MarketContextAlignmentStatus
    coverages: tuple[MarketContextTimeframeCoverage, ...] = Field(min_length=3, max_length=3)
    issue_codes: tuple[MarketContextAlignmentIssueCode, ...] = ()
    manifest: MarketContextInputManifest | None = None
    aligned_at: datetime

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source cannot be empty")
        return normalized

    @field_validator("as_of", "aligned_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        expected_timeframes = tuple(_TIMEFRAME_ORDER)
        if tuple(item.timeframe for item in self.coverages) != expected_timeframes:
            raise ValueError("alignment coverage must use deterministic timeframe order")
        if self.aligned_at < self.as_of:
            raise ValueError("alignment cannot precede its event-time boundary")
        if self.status is MarketContextAlignmentStatus.READY:
            if self.manifest is None:
                raise ValueError("ready alignment requires an input manifest")
            if self.issue_codes:
                raise ValueError("ready alignment cannot contain issue codes")
            if any(
                item.status is not MarketContextAlignmentStatus.READY for item in self.coverages
            ):
                raise ValueError("ready alignment requires ready timeframe coverage")
            if (
                self.manifest.source != self.source
                or self.manifest.pair != self.pair
                or self.manifest.as_of != self.as_of
            ):
                raise ValueError("alignment manifest identity is inconsistent")
        else:
            if self.manifest is not None:
                raise ValueError("non-ready alignment cannot expose an input manifest")
            if not self.issue_codes:
                raise ValueError("non-ready alignment requires an issue code")
        return self


def required_market_context_window_counts(
    feature_set: MarketContextFeatureSetDefinition,
    *,
    policy: MarketContextAlignmentPolicy | None = None,
) -> dict[Timeframe, int]:
    """Return the maximum feature lookback required for every policy timeframe."""

    selected_policy = policy or default_market_context_alignment_policy()
    if feature_set.policy_version != selected_policy.policy_version:
        raise ValueError("feature set and alignment policy versions do not match")

    counts = {timeframe: 1 for timeframe in selected_policy.timeframes}
    for requirement in feature_set.requirements:
        if requirement.timeframe not in counts:
            raise ValueError("feature requirement is outside the alignment policy")
        counts[requirement.timeframe] = max(
            counts[requirement.timeframe],
            requirement.lookback_windows,
        )
    return counts


def align_market_context_windows(
    *,
    source: str,
    pair: TradingPair,
    as_of: datetime,
    windows: tuple[MarketDataWindowSnapshot, ...],
    feature_set: MarketContextFeatureSetDefinition,
    aligned_at: datetime,
    policy: MarketContextAlignmentPolicy | None = None,
) -> MarketContextAlignmentResult:
    """Build an exact event-time dataset or explain why it is not consumable."""

    selected_policy = policy or default_market_context_alignment_policy()
    normalized_source = source.strip()
    if not normalized_source:
        raise ValueError("market-context source cannot be empty")
    normalized_as_of = _normalize_timestamp(as_of)
    normalized_aligned_at = _normalize_timestamp(aligned_at)
    if (
        floor_market_context_boundary(normalized_as_of, selected_policy.anchor_timeframe)
        != normalized_as_of
    ):
        raise ValueError("alignment as-of time must be an anchor timeframe boundary")

    counts = required_market_context_window_counts(feature_set, policy=selected_policy)
    latest_by_window: dict[str, MarketDataWindowSnapshot] = {}
    for window in windows:
        if window.state is not MarketDataWindowState.FINALIZED:
            raise ValueError("market-context alignment accepts finalized windows only")
        if window.source != normalized_source or window.pair != pair:
            raise ValueError("market-context alignment cannot mix market streams")
        if window.timeframe not in counts:
            raise ValueError("market-context window is outside the alignment policy")
        current = latest_by_window.get(window.window_id)
        if current is None or window.version > current.version:
            latest_by_window[window.window_id] = window

    references: list[MarketContextWindowReference] = []
    coverages: list[MarketContextTimeframeCoverage] = []
    all_issues: list[MarketContextAlignmentIssueCode] = []

    for timeframe in selected_policy.timeframes:
        required = counts[timeframe]
        expected_end = floor_market_context_boundary(normalized_as_of, timeframe)
        eligible = sorted(
            (
                window
                for window in latest_by_window.values()
                if window.timeframe is timeframe and window.window_end <= expected_end
            ),
            key=lambda item: (item.window_start, item.version),
        )
        candidates = eligible[-required:]
        expected_starts = tuple(
            expected_end - timeframe.duration * offset for offset in range(required, 0, -1)
        )
        observed_starts = {window.window_start for window in candidates}
        missing_starts = tuple(
            window_start for window_start in expected_starts if window_start not in observed_starts
        )
        matched = required - len(missing_starts)
        latest_end = candidates[-1].window_end if candidates else None

        issues: tuple[MarketContextAlignmentIssueCode, ...]
        status: MarketContextAlignmentStatus
        if not candidates:
            status = MarketContextAlignmentStatus.INSUFFICIENT_DATA
            issues = (MarketContextAlignmentIssueCode.NO_FINALIZED_WINDOWS,)
        elif len(candidates) < required:
            status = MarketContextAlignmentStatus.INSUFFICIENT_DATA
            issues = (MarketContextAlignmentIssueCode.INSUFFICIENT_HISTORY,)
        elif any(
            current.window_end != following.window_start
            for current, following in pairwise(candidates)
        ):
            status = MarketContextAlignmentStatus.INSUFFICIENT_DATA
            issues = (MarketContextAlignmentIssueCode.WINDOW_GAP,)
        elif latest_end != expected_end:
            status = MarketContextAlignmentStatus.STALE
            issues = (MarketContextAlignmentIssueCode.STALE_LATEST_WINDOW,)
        elif missing_starts:
            status = MarketContextAlignmentStatus.INSUFFICIENT_DATA
            issues = (MarketContextAlignmentIssueCode.WINDOW_GAP,)
        else:
            status = MarketContextAlignmentStatus.READY
            issues = ()
            references.extend(
                MarketContextWindowReference.from_snapshot(window) for window in candidates
            )

        coverages.append(
            MarketContextTimeframeCoverage(
                timeframe=timeframe,
                required_windows=required,
                available_windows=len(eligible),
                matched_windows=matched,
                expected_latest_window_end=expected_end,
                latest_observed_window_end=latest_end,
                missing_window_starts=missing_starts,
                status=status,
                issue_codes=issues,
            )
        )
        for issue in issues:
            if issue not in all_issues:
                all_issues.append(issue)

    if any(item.status is MarketContextAlignmentStatus.INSUFFICIENT_DATA for item in coverages):
        overall_status = MarketContextAlignmentStatus.INSUFFICIENT_DATA
    elif any(item.status is MarketContextAlignmentStatus.STALE for item in coverages):
        overall_status = MarketContextAlignmentStatus.STALE
    else:
        overall_status = MarketContextAlignmentStatus.READY

    manifest = None
    if overall_status is MarketContextAlignmentStatus.READY:
        latest_finalization = max(reference.finalized_at for reference in references)
        manifest_created_at = max(normalized_as_of, latest_finalization)
        if normalized_aligned_at < manifest_created_at:
            raise ValueError("alignment time cannot precede input window finalization")
        manifest = MarketContextInputManifest.build(
            source=normalized_source,
            pair=pair,
            as_of=normalized_as_of,
            windows=tuple(references),
            created_at=manifest_created_at,
        )

    return MarketContextAlignmentResult(
        source=normalized_source,
        pair=pair,
        as_of=normalized_as_of,
        feature_set_version=feature_set.feature_set_version,
        feature_set_checksum=feature_set.definition_checksum,
        status=overall_status,
        coverages=tuple(coverages),
        issue_codes=tuple(all_issues),
        manifest=manifest,
        aligned_at=normalized_aligned_at,
    )
