import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from itertools import pairwise
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.events import MarketDataWindowSnapshot, MarketDataWindowState

_POLICY_VERSION: Final[Literal["market-context-alignment-policy-v1"]] = (
    "market-context-alignment-policy-v1"
)
_TIMEFRAME_ORDER = {
    Timeframe.HOUR_1: 0,
    Timeframe.HOURS_4: 1,
    Timeframe.DAY_1: 2,
}


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("text cannot be empty")
    return normalized


def _floor_to_boundary(value: datetime, timeframe: Timeframe) -> datetime:
    normalized = _normalize_timestamp(value)
    duration_seconds = int(timeframe.duration.total_seconds())
    boundary = int(normalized.timestamp()) // duration_seconds * duration_seconds
    return datetime.fromtimestamp(boundary, tz=UTC)


class MarketContextBoundaryConvention(StrEnum):
    """The only interval convention supported by the v1 context contract."""

    LEFT_CLOSED_RIGHT_OPEN = "left_closed_right_open"


class MarketContextAssessmentStatus(StrEnum):
    """Whether a context assessment is safe to consume."""

    READY = "ready"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"


class MarketTrendRegime(StrEnum):
    """Deterministic trend labels exposed by the v1 regime contract."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    UNDETERMINED = "undetermined"


class MarketVolatilityRegime(StrEnum):
    """Deterministic volatility labels exposed by the v1 regime contract."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    UNDETERMINED = "undetermined"


class MarketContextAlignmentPolicy(BaseModel):
    """Frozen v1 rules for building multi-timeframe market context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-alignment-policy-v1"] = _POLICY_VERSION
    policy_version: Literal["market-context-alignment-policy-v1"] = _POLICY_VERSION
    scope: Literal["crypto-spot-public-read-only"] = "crypto-spot-public-read-only"
    anchor_timeframe: Literal[Timeframe.HOUR_1] = Timeframe.HOUR_1
    context_timeframes: tuple[Timeframe, ...] = (
        Timeframe.HOURS_4,
        Timeframe.DAY_1,
    )
    timezone: Literal["UTC"] = "UTC"
    boundary_convention: Literal[MarketContextBoundaryConvention.LEFT_CLOSED_RIGHT_OPEN] = (
        MarketContextBoundaryConvention.LEFT_CLOSED_RIGHT_OPEN
    )
    finalized_windows_only: Literal[True] = True
    same_source_only: Literal[True] = True
    deterministic: Literal[True] = True

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        expected = (Timeframe.HOURS_4, Timeframe.DAY_1)
        if self.context_timeframes != expected:
            raise ValueError("v1 context timeframes must be ordered as 4h then 1d")
        anchor_seconds = int(self.anchor_timeframe.duration.total_seconds())
        if any(
            int(timeframe.duration.total_seconds()) % anchor_seconds != 0
            for timeframe in self.context_timeframes
        ):
            raise ValueError("context timeframes must be exact multiples of the anchor")
        return self

    @property
    def timeframes(self) -> tuple[Timeframe, ...]:
        return (self.anchor_timeframe, *self.context_timeframes)


def default_market_context_alignment_policy() -> MarketContextAlignmentPolicy:
    """Return the immutable v1 policy instead of sharing mutable global state."""

    return MarketContextAlignmentPolicy()


def build_market_context_window_reference_checksum(
    *,
    window_id: str,
    version: int,
    source: str,
    pair: TradingPair,
    timeframe: Timeframe,
    window_start: datetime,
    window_end: datetime,
    event_id: str,
    payload_checksum: str,
    finalized_at: datetime,
) -> str:
    """Hash lineage fields required to reproduce one finalized input window."""

    payload = {
        "event_id": event_id,
        "finalized_at": _normalize_timestamp(finalized_at).isoformat(),
        "pair": pair.model_dump(mode="json"),
        "payload_checksum": payload_checksum,
        "source": _normalize_text(source),
        "timeframe": timeframe.value,
        "version": version,
        "window_end": _normalize_timestamp(window_end).isoformat(),
        "window_id": window_id,
        "window_start": _normalize_timestamp(window_start).isoformat(),
    }
    return _checksum(payload)


class MarketContextWindowReference(BaseModel):
    """Tamper-evident pointer to an immutable finalized market-data window."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-window-reference-v1"] = (
        "market-context-window-reference-v1"
    )
    window_id: str = Field(pattern=r"^market-window-[a-f0-9]{16}$")
    version: int = Field(ge=2)
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    window_start: datetime
    window_end: datetime
    event_id: str = Field(pattern=r"^market-event-[a-f0-9]{16}$")
    payload_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    finalized_at: datetime
    reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("window_start", "window_end", "finalized_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.timeframe not in _TIMEFRAME_ORDER:
            raise ValueError("window timeframe is outside the v1 market-context policy")
        if self.window_end - self.window_start != self.timeframe.duration:
            raise ValueError("window bounds do not match its timeframe duration")
        if _floor_to_boundary(self.window_start, self.timeframe) != self.window_start:
            raise ValueError("window start is not aligned to its UTC timeframe boundary")
        if self.finalized_at < self.window_end:
            raise ValueError("window cannot be finalized before its event-time boundary")

        expected = build_market_context_window_reference_checksum(
            window_id=self.window_id,
            version=self.version,
            source=self.source,
            pair=self.pair,
            timeframe=self.timeframe,
            window_start=self.window_start,
            window_end=self.window_end,
            event_id=self.event_id,
            payload_checksum=self.payload_checksum,
            finalized_at=self.finalized_at,
        )
        if self.reference_checksum != expected:
            raise ValueError("window reference checksum is inconsistent")
        return self

    @classmethod
    def from_snapshot(cls, snapshot: MarketDataWindowSnapshot) -> Self:
        if snapshot.state is not MarketDataWindowState.FINALIZED:
            raise ValueError("market context requires a finalized window snapshot")
        if snapshot.finalized_at is None:
            raise ValueError("finalized window snapshot is missing finalization time")

        checksum = build_market_context_window_reference_checksum(
            window_id=snapshot.window_id,
            version=snapshot.version,
            source=snapshot.source,
            pair=snapshot.pair,
            timeframe=snapshot.timeframe,
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            event_id=snapshot.event_id,
            payload_checksum=snapshot.payload_checksum,
            finalized_at=snapshot.finalized_at,
        )
        return cls(
            window_id=snapshot.window_id,
            version=snapshot.version,
            source=snapshot.source,
            pair=snapshot.pair,
            timeframe=snapshot.timeframe,
            window_start=snapshot.window_start,
            window_end=snapshot.window_end,
            event_id=snapshot.event_id,
            payload_checksum=snapshot.payload_checksum,
            finalized_at=snapshot.finalized_at,
            reference_checksum=checksum,
        )


def build_market_context_input_checksum(
    *,
    policy_version: str,
    source: str,
    pair: TradingPair,
    as_of: datetime,
    windows: tuple[MarketContextWindowReference, ...],
) -> str:
    """Build stable identity for a complete ordered input manifest."""

    payload = {
        "as_of": _normalize_timestamp(as_of).isoformat(),
        "pair": pair.model_dump(mode="json"),
        "policy_version": policy_version,
        "source": _normalize_text(source),
        "windows": [window.model_dump(mode="json") for window in windows],
    }
    return _checksum(payload)


class MarketContextInputManifest(BaseModel):
    """Complete and reproducible multi-timeframe input selected for a context run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-input-manifest-v1"] = "market-context-input-manifest-v1"
    manifest_id: str = Field(pattern=r"^market-context-input-[a-f0-9]{16}$")
    policy_version: Literal["market-context-alignment-policy-v1"] = _POLICY_VERSION
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    as_of: datetime
    windows: tuple[MarketContextWindowReference, ...] = Field(min_length=3)
    input_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    created_at: datetime

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("as_of", "created_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        policy = default_market_context_alignment_policy()
        if _floor_to_boundary(self.as_of, policy.anchor_timeframe) != self.as_of:
            raise ValueError("manifest as-of time must be an anchor timeframe boundary")
        if self.created_at < self.as_of:
            raise ValueError("manifest creation cannot precede its as-of time")

        expected_order = tuple(
            sorted(
                self.windows,
                key=lambda item: (
                    _TIMEFRAME_ORDER.get(item.timeframe, len(_TIMEFRAME_ORDER)),
                    item.window_start,
                    item.version,
                ),
            )
        )
        if self.windows != expected_order:
            raise ValueError(
                "manifest windows must use deterministic timeframe and event-time order"
            )

        identities: set[tuple[str, int]] = set()
        grouped: dict[Timeframe, list[MarketContextWindowReference]] = {
            timeframe: [] for timeframe in policy.timeframes
        }
        for window in self.windows:
            if window.source != self.source or window.pair != self.pair:
                raise ValueError("manifest windows must belong to one exact market stream")
            if window.timeframe not in grouped:
                raise ValueError("manifest includes a timeframe outside its alignment policy")
            if window.window_end > self.as_of:
                raise ValueError("manifest cannot consume a future event-time window")
            identity = (window.window_id, window.version)
            if identity in identities:
                raise ValueError("manifest contains a duplicate window version")
            identities.add(identity)
            grouped[window.timeframe].append(window)

        for timeframe, references in grouped.items():
            if not references:
                raise ValueError(f"manifest is missing required {timeframe.value} windows")
            expected_latest_end = _floor_to_boundary(self.as_of, timeframe)
            if references[-1].window_end != expected_latest_end:
                raise ValueError(
                    f"latest {timeframe.value} window does not match the as-of boundary"
                )
            if any(
                current.window_end != following.window_start
                for current, following in pairwise(references)
            ):
                raise ValueError(f"manifest has a gap in {timeframe.value} window history")

        expected_checksum = build_market_context_input_checksum(
            policy_version=self.policy_version,
            source=self.source,
            pair=self.pair,
            as_of=self.as_of,
            windows=self.windows,
        )
        if self.input_checksum != expected_checksum:
            raise ValueError("market-context input checksum is inconsistent")
        expected_id = f"market-context-input-{expected_checksum[:16]}"
        if self.manifest_id != expected_id:
            raise ValueError("market-context manifest ID is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        windows: tuple[MarketContextWindowReference, ...],
        created_at: datetime,
    ) -> Self:
        ordered = tuple(
            sorted(
                windows,
                key=lambda item: (
                    _TIMEFRAME_ORDER.get(item.timeframe, len(_TIMEFRAME_ORDER)),
                    item.window_start,
                    item.version,
                ),
            )
        )
        checksum = build_market_context_input_checksum(
            policy_version=_POLICY_VERSION,
            source=source,
            pair=pair,
            as_of=as_of,
            windows=ordered,
        )
        return cls(
            manifest_id=f"market-context-input-{checksum[:16]}",
            source=source,
            pair=pair,
            as_of=as_of,
            windows=ordered,
            input_checksum=checksum,
            created_at=created_at,
        )


class MarketContextFeatureRequirement(BaseModel):
    """One versioned, deterministic input requirement for a feature set."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    timeframe: Timeframe
    lookback_windows: int = Field(ge=1, le=10_000)
    calculation_version: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}-v[1-9][0-9]*$")
    requires_finalized_windows: Literal[True] = True

    @model_validator(mode="after")
    def validate_requirement(self) -> Self:
        if self.timeframe not in _TIMEFRAME_ORDER:
            raise ValueError("feature timeframe is outside the v1 market-context policy")
        return self


class MarketContextFeatureSetDefinition(BaseModel):
    """Versioned contract for an ordered collection of deterministic features."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-feature-set-v1"] = "market-context-feature-set-v1"
    feature_set_version: str = Field(pattern=r"^market-context-features-v[1-9][0-9]*$")
    policy_version: Literal["market-context-alignment-policy-v1"] = _POLICY_VERSION
    requirements: tuple[MarketContextFeatureRequirement, ...] = Field(min_length=1)
    deterministic: Literal[True] = True
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        keys = tuple(requirement.feature_key for requirement in self.requirements)
        if keys != tuple(sorted(keys)):
            raise ValueError("feature requirements must be ordered by feature key")
        if len(keys) != len(set(keys)):
            raise ValueError("feature requirement keys must be unique")
        expected = self.calculate_checksum(
            feature_set_version=self.feature_set_version,
            requirements=self.requirements,
        )
        if self.definition_checksum != expected:
            raise ValueError("feature-set definition checksum is inconsistent")
        return self

    @staticmethod
    def calculate_checksum(
        *,
        feature_set_version: str,
        requirements: tuple[MarketContextFeatureRequirement, ...],
    ) -> str:
        return _checksum(
            {
                "feature_set_version": feature_set_version,
                "policy_version": _POLICY_VERSION,
                "requirements": [item.model_dump(mode="json") for item in requirements],
            }
        )

    @classmethod
    def build(
        cls,
        *,
        feature_set_version: str,
        requirements: tuple[MarketContextFeatureRequirement, ...],
    ) -> Self:
        ordered = tuple(sorted(requirements, key=lambda item: item.feature_key))
        return cls(
            feature_set_version=feature_set_version,
            requirements=ordered,
            definition_checksum=cls.calculate_checksum(
                feature_set_version=feature_set_version,
                requirements=ordered,
            ),
        )


class MarketContextEvidence(BaseModel):
    """A feature value and exact window lineage supporting an assessment."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature_key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,63}$")
    timeframe: Timeframe
    value: Decimal
    calculation_version: str = Field(pattern=r"^[a-z][a-z0-9_-]{2,63}-v[1-9][0-9]*$")
    window_reference_checksums: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.timeframe not in _TIMEFRAME_ORDER:
            raise ValueError("evidence timeframe is outside the v1 market-context policy")
        return self

    @field_validator("window_reference_checksums")
    @classmethod
    def validate_reference_checksums(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(
            len(item) != 64 or any(character not in "0123456789abcdef" for character in item)
            for item in value
        ):
            raise ValueError("evidence window reference checksum is invalid")
        if len(value) != len(set(value)):
            raise ValueError("evidence cannot reference the same window twice")
        return value


def build_market_regime_assessment_id(
    *,
    source: str,
    pair: TradingPair,
    as_of: datetime,
    input_checksum: str,
    feature_set_version: str,
    algorithm_version: str,
) -> str:
    identity = {
        "algorithm_version": algorithm_version,
        "as_of": _normalize_timestamp(as_of).isoformat(),
        "feature_set_version": feature_set_version,
        "input_checksum": input_checksum,
        "pair": pair.model_dump(mode="json"),
        "source": _normalize_text(source),
    }
    return f"market-regime-{_checksum(identity)[:16]}"


class MarketRegimeAssessment(BaseModel):
    """Versioned market-context output; calculation is implemented in P3-05."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-regime-assessment-v1"] = "market-regime-assessment-v1"
    assessment_id: str = Field(pattern=r"^market-regime-[a-f0-9]{16}$")
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    as_of: datetime
    input_manifest_id: str = Field(pattern=r"^market-context-input-[a-f0-9]{16}$")
    input_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_set_version: str = Field(pattern=r"^market-context-features-v[1-9][0-9]*$")
    feature_set_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    algorithm_version: str = Field(pattern=r"^market-regime-v[1-9][0-9]*$")
    status: MarketContextAssessmentStatus
    trend: MarketTrendRegime
    volatility: MarketVolatilityRegime
    confidence: Decimal = Field(ge=0, le=1)
    evidence: tuple[MarketContextEvidence, ...] = ()
    issue_codes: tuple[str, ...] = ()
    assessed_at: datetime
    expires_at: datetime

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("as_of", "assessed_at", "expires_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("issue_codes")
    @classmethod
    def validate_issue_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(not item or item.strip() != item for item in value):
            raise ValueError("assessment issue codes must be normalized non-empty text")
        if value != tuple(sorted(value)):
            raise ValueError("assessment issue codes must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("assessment issue codes must be unique")
        return value

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        expected_id = build_market_regime_assessment_id(
            source=self.source,
            pair=self.pair,
            as_of=self.as_of,
            input_checksum=self.input_checksum,
            feature_set_version=self.feature_set_version,
            algorithm_version=self.algorithm_version,
        )
        if self.assessment_id != expected_id:
            raise ValueError("market-regime assessment ID is inconsistent")
        if self.input_manifest_id != f"market-context-input-{self.input_checksum[:16]}":
            raise ValueError("assessment input manifest identity is inconsistent")
        if self.assessed_at < self.as_of:
            raise ValueError("assessment time cannot precede its event-time boundary")

        evidence_keys = tuple(item.feature_key for item in self.evidence)
        if evidence_keys != tuple(sorted(evidence_keys)):
            raise ValueError("assessment evidence must use deterministic feature-key order")
        if len(evidence_keys) != len(set(evidence_keys)):
            raise ValueError("assessment evidence feature keys must be unique")

        if self.status is MarketContextAssessmentStatus.READY:
            if self.trend is MarketTrendRegime.UNDETERMINED:
                raise ValueError("ready assessment requires a determinate trend regime")
            if self.volatility is MarketVolatilityRegime.UNDETERMINED:
                raise ValueError("ready assessment requires a determinate volatility regime")
            if self.confidence <= 0 or not self.evidence or self.issue_codes:
                raise ValueError("ready assessment requires confidence and evidence without issues")
            if self.expires_at <= self.assessed_at:
                raise ValueError("ready assessment must expire after assessment time")
        else:
            if (
                self.trend is not MarketTrendRegime.UNDETERMINED
                or self.volatility is not MarketVolatilityRegime.UNDETERMINED
                or self.confidence != 0
                or self.evidence
                or not self.issue_codes
            ):
                raise ValueError("non-ready assessment cannot expose a partial regime")
            if self.expires_at != self.assessed_at:
                raise ValueError("non-ready assessment must be immediately expired")
        return self
