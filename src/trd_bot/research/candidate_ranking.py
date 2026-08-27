from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from trd_bot.research.candidates import (
    ResearchCandidate,
    normalize_candidate_timestamp,
)

SCORE_QUANTUM = Decimal("0.000001")


class CandidateRankingComponentName(StrEnum):
    """Explainable components used by the deterministic candidate ranker."""

    CONFIDENCE = "confidence"
    SIGNAL_STRENGTH = "signal_strength"
    FRESHNESS = "freshness"


class CandidateRankingPolicy(BaseModel):
    """Weights used to rank selectable research candidates."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    confidence_weight: Decimal = Field(
        default=Decimal("0.45"),
        ge=0,
        le=1,
    )
    signal_strength_weight: Decimal = Field(
        default=Decimal("0.35"),
        ge=0,
        le=1,
    )
    freshness_weight: Decimal = Field(
        default=Decimal("0.20"),
        ge=0,
        le=1,
    )

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> Self:
        total = self.confidence_weight + self.signal_strength_weight + self.freshness_weight

        if total != Decimal("1"):
            raise ValueError("candidate ranking weights must sum to one")

        return self


class CandidateRankingComponent(BaseModel):
    """One normalized and weighted contribution to a candidate score."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    name: CandidateRankingComponentName
    raw_value: Decimal = Field(ge=0, le=1)
    weight: Decimal = Field(ge=0, le=1)
    weighted_value: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def weighted_value_must_match(self) -> Self:
        expected = _quantize_score(self.raw_value * self.weight)

        if self.weighted_value != expected:
            raise ValueError("candidate ranking weighted value does not match")

        return self


class CandidateRankingEntry(BaseModel):
    """One ranked candidate with its complete score explanation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    rank: int = Field(ge=1)
    candidate: ResearchCandidate
    total_score: Decimal = Field(ge=0, le=1)
    components: tuple[CandidateRankingComponent, ...]

    @model_validator(mode="after")
    def components_must_match_total(self) -> Self:
        component_names = [component.name for component in self.components]

        if len(component_names) != len(set(component_names)):
            raise ValueError("candidate ranking component names must be unique")

        expected_names = set(CandidateRankingComponentName)
        if set(component_names) != expected_names:
            raise ValueError("candidate ranking entry requires every score component")

        expected_total = _quantize_score(
            sum(
                (component.weighted_value for component in self.components),
                start=Decimal("0"),
            )
        )

        if self.total_score != expected_total:
            raise ValueError("candidate ranking total does not match its components")

        return self


class CandidateRankingResult(BaseModel):
    """Deterministic ranked view over one candidate set at one point in time."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    ranked_at: datetime
    policy: CandidateRankingPolicy
    total_candidates: int = Field(ge=0)
    eligible_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    entries: tuple[CandidateRankingEntry, ...]

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        normalized_time = normalize_candidate_timestamp(self.ranked_at)

        if normalized_time != self.ranked_at:
            raise ValueError("candidate ranking time must be normalized to UTC")

        if self.eligible_count + self.excluded_count != self.total_candidates:
            raise ValueError("candidate ranking counts do not reconcile")

        if len(self.entries) != self.eligible_count:
            raise ValueError("candidate ranking entries do not match eligible count")

        expected_ranks = tuple(range(1, len(self.entries) + 1))
        actual_ranks = tuple(entry.rank for entry in self.entries)
        if actual_ranks != expected_ranks:
            raise ValueError("candidate ranking ranks must be contiguous")

        scores = tuple(entry.total_score for entry in self.entries)
        if scores != tuple(sorted(scores, reverse=True)):
            raise ValueError("candidate ranking entries must be score ordered")

        return self


@dataclass(frozen=True)
class _ScoredCandidate:
    candidate: ResearchCandidate
    total_score: Decimal
    components: tuple[CandidateRankingComponent, ...]


class CandidateRanker:
    """Rank still-selectable candidates without side effects or hidden state."""

    def __init__(
        self,
        *,
        policy: CandidateRankingPolicy | None = None,
    ) -> None:
        self._policy = policy or CandidateRankingPolicy()

    @property
    def policy(self) -> CandidateRankingPolicy:
        return self._policy

    def rank(
        self,
        *,
        candidates: Sequence[ResearchCandidate],
        at: datetime,
    ) -> CandidateRankingResult:
        ranked_at = normalize_candidate_timestamp(at)

        eligible = tuple(
            candidate for candidate in candidates if candidate.is_selectable(at=ranked_at)
        )

        scored = tuple(
            self._score(
                candidate=candidate,
                at=ranked_at,
            )
            for candidate in eligible
        )

        ordered = tuple(
            sorted(
                scored,
                key=lambda item: (
                    -item.total_score,
                    item.candidate.candidate_id,
                ),
            )
        )

        entries = tuple(
            CandidateRankingEntry(
                rank=index,
                candidate=item.candidate,
                total_score=item.total_score,
                components=item.components,
            )
            for index, item in enumerate(
                ordered,
                start=1,
            )
        )

        return CandidateRankingResult(
            ranked_at=ranked_at,
            policy=self._policy,
            total_candidates=len(candidates),
            eligible_count=len(entries),
            excluded_count=len(candidates) - len(entries),
            entries=entries,
        )

    def _score(
        self,
        *,
        candidate: ResearchCandidate,
        at: datetime,
    ) -> _ScoredCandidate:
        confidence = _quantize_score(candidate.confidence)
        signal_strength = _quantize_score(abs(candidate.signal_score))
        freshness = _freshness_score(
            candidate=candidate,
            at=at,
        )

        components = (
            _build_component(
                name=CandidateRankingComponentName.CONFIDENCE,
                raw_value=confidence,
                weight=self._policy.confidence_weight,
            ),
            _build_component(
                name=CandidateRankingComponentName.SIGNAL_STRENGTH,
                raw_value=signal_strength,
                weight=self._policy.signal_strength_weight,
            ),
            _build_component(
                name=CandidateRankingComponentName.FRESHNESS,
                raw_value=freshness,
                weight=self._policy.freshness_weight,
            ),
        )

        total_score = _quantize_score(
            sum(
                (component.weighted_value for component in components),
                start=Decimal("0"),
            )
        )

        return _ScoredCandidate(
            candidate=candidate,
            total_score=total_score,
            components=components,
        )


def _build_component(
    *,
    name: CandidateRankingComponentName,
    raw_value: Decimal,
    weight: Decimal,
) -> CandidateRankingComponent:
    normalized_raw = _quantize_score(raw_value)
    normalized_weight = _quantize_score(weight)

    return CandidateRankingComponent(
        name=name,
        raw_value=normalized_raw,
        weight=normalized_weight,
        weighted_value=_quantize_score(
            normalized_raw * normalized_weight,
        ),
    )


def _freshness_score(
    *,
    candidate: ResearchCandidate,
    at: datetime,
) -> Decimal:
    total_lifetime = candidate.valid_until - candidate.created_at
    remaining_lifetime = candidate.valid_until - at

    total_microseconds = _timedelta_microseconds(total_lifetime)
    remaining_microseconds = _timedelta_microseconds(remaining_lifetime)

    if total_microseconds <= 0:
        raise ValueError("candidate lifetime must be positive")

    if remaining_microseconds <= 0:
        return Decimal("0")

    return _quantize_score(Decimal(remaining_microseconds) / Decimal(total_microseconds))


def _timedelta_microseconds(value: timedelta) -> int:
    return value.days * 86_400 * 1_000_000 + value.seconds * 1_000_000 + value.microseconds


def _quantize_score(value: Decimal) -> Decimal:
    return value.quantize(
        SCORE_QUANTUM,
        rounding=ROUND_HALF_UP,
    )
