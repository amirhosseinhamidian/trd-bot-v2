import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence.contracts import (
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
)
from trd_bot.decision_intelligence.evaluation import StrategyEvaluationRecord
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies import SignalDirection, StrategySignal

SCORE_QUANTUM = Decimal("0.000001")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision candidate timestamp must include timezone information")
    return value.astimezone(UTC)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(SCORE_QUANTUM, rounding=ROUND_HALF_UP)


class DecisionCandidateAction(StrEnum):
    """Directional action represented by an offline decision candidate."""

    LONG = "long"
    SHORT = "short"


class DecisionCandidateScoreComponentName(StrEnum):
    """Explainable inputs to the frozen candidate ranking score."""

    CONTEXT_CONFIDENCE = "context_confidence"
    SIGNAL_STRENGTH = "signal_strength"


class DecisionCandidatePolicyV1(BaseModel):
    """Frozen construction and ranking policy for Phase 5 candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-candidate-policy-v1"] = "decision-candidate-policy-v1"
    policy_version: Literal["decision-candidate-v1"] = "decision-candidate-v1"
    validity_candles: Literal[4] = 4
    reward_risk_ratio: Decimal = Field(default=Decimal("2.000000"), gt=0)
    signal_strength_weight: Decimal = Field(default=Decimal("0.600000"), ge=0, le=1)
    context_confidence_weight: Decimal = Field(default=Decimal("0.400000"), ge=0, le=1)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        if self.reward_risk_ratio != Decimal("2.000000"):
            raise ValueError("decision candidate reward/risk ratio is not version one")
        if self.signal_strength_weight != Decimal("0.600000"):
            raise ValueError("decision candidate signal weight is not version one")
        if self.context_confidence_weight != Decimal("0.400000"):
            raise ValueError("decision candidate context weight is not version one")
        if self.signal_strength_weight + self.context_confidence_weight != Decimal("1"):
            raise ValueError("decision candidate ranking weights must sum to one")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision candidate policy checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "context_confidence_weight": str(self.context_confidence_weight),
            "policy_version": self.policy_version,
            "reward_risk_ratio": str(self.reward_risk_ratio),
            "schema_version": self.schema_version,
            "signal_strength_weight": str(self.signal_strength_weight),
            "validity_candles": self.validity_candles,
        }


def decision_candidate_policy_v1() -> DecisionCandidatePolicyV1:
    """Return a validated copy of the canonical candidate policy."""

    unvalidated = DecisionCandidatePolicyV1.model_construct(definition_checksum="0" * 64)
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return DecisionCandidatePolicyV1.model_validate(payload)


class DecisionCandidateTradePlan(BaseModel):
    """Price-only plan derived from the exact source candle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_price: Decimal = Field(gt=0)
    invalidation_price: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
    reward_risk_ratio: Decimal = Field(gt=0)


class DecisionCandidate(BaseModel):
    """Immutable candidate constructed from one accepted strategy signal."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-candidate-v1"] = "decision-candidate-v1"
    candidate_id: str = Field(pattern=r"^decision-candidate-[a-f0-9]{16}$")
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    signal_id: str = Field(pattern=r"^signal-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1, max_length=100)
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    action: DecisionCandidateAction
    signal_score: Decimal = Field(ge=-1, le=1)
    context_confidence: Decimal = Field(ge=0, le=1)
    observed_at: datetime
    constructed_at: datetime
    valid_until: datetime
    trade_plan: DecisionCandidateTradePlan
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    candidate_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("observed_at", "constructed_at", "valid_until")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_candidate(self) -> Self:
        if self.observed_at > self.constructed_at:
            raise ValueError("decision candidate cannot observe a future signal")
        if self.valid_until <= self.constructed_at:
            raise ValueError("decision candidate validity must extend beyond construction")
        if self.action is DecisionCandidateAction.LONG:
            if self.signal_score <= 0:
                raise ValueError("long decision candidate requires a positive signal")
            if self.trade_plan.invalidation_price >= self.trade_plan.entry_price:
                raise ValueError("long decision candidate invalidation must be below entry")
            if self.trade_plan.target_price <= self.trade_plan.entry_price:
                raise ValueError("long decision candidate target must be above entry")
        else:
            if self.signal_score >= 0:
                raise ValueError("short decision candidate requires a negative signal")
            if self.trade_plan.invalidation_price <= self.trade_plan.entry_price:
                raise ValueError("short decision candidate invalidation must be above entry")
            if self.trade_plan.target_price >= self.trade_plan.entry_price:
                raise ValueError("short decision candidate target must be below entry")
        expected_id = f"decision-candidate-{_checksum(self._identity_payload())[:16]}"
        if self.candidate_id != expected_id:
            raise ValueError("decision candidate ID is inconsistent")
        if self.candidate_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision candidate checksum is inconsistent")
        return self

    def _identity_payload(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "policy_checksum": self.policy_checksum,
            "signal_id": self.signal_id,
        }

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "action": self.action.value,
            "candidate_id": self.candidate_id,
            "constructed_at": self.constructed_at.isoformat(),
            "context_confidence": str(self.context_confidence),
            "dataset_id": self.dataset_id,
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "observed_at": self.observed_at.isoformat(),
            "offline_only": True,
            "pair": self.pair.model_dump(mode="json"),
            "policy_checksum": self.policy_checksum,
            "schema_version": self.schema_version,
            "signal_id": self.signal_id,
            "signal_score": str(self.signal_score),
            "strategy_name": self.strategy_name,
            "strategy_version": self.strategy_version,
            "timeframe": self.timeframe.value,
            "trade_plan": self.trade_plan.model_dump(mode="json"),
            "valid_until": self.valid_until.isoformat(),
        }

    @classmethod
    def build(
        cls,
        *,
        intent: DecisionEvaluationIntent,
        signal: StrategySignal,
        entry_price: Decimal,
        invalidation_price: Decimal,
        target_price: Decimal,
        policy: DecisionCandidatePolicyV1,
    ) -> Self:
        action = {
            SignalDirection.LONG: DecisionCandidateAction.LONG,
            SignalDirection.SHORT: DecisionCandidateAction.SHORT,
        }.get(signal.direction)
        if action is None:
            raise ValueError("neutral signal cannot create a decision candidate")
        identity = {
            "evaluation_id": intent.evaluation_id,
            "policy_checksum": policy.definition_checksum,
            "signal_id": signal.signal_id,
        }
        candidate_id = f"decision-candidate-{_checksum(identity)[:16]}"
        trade_plan = DecisionCandidateTradePlan(
            entry_price=entry_price,
            invalidation_price=invalidation_price,
            target_price=target_price,
            reward_risk_ratio=policy.reward_risk_ratio,
        )
        unvalidated = cls.model_construct(
            candidate_id=candidate_id,
            evaluation_id=intent.evaluation_id,
            signal_id=signal.signal_id,
            dataset_id=signal.dataset_id,
            strategy_name=signal.strategy_name,
            strategy_version=signal.strategy_version,
            pair=signal.pair,
            timeframe=signal.timeframe,
            action=action,
            signal_score=signal.score,
            context_confidence=intent.market_context.confidence,
            observed_at=signal.candle_close_time,
            constructed_at=intent.requested_at,
            valid_until=(intent.requested_at + signal.timeframe.duration * policy.validity_candles),
            trade_plan=trade_plan,
            policy_checksum=policy.definition_checksum,
            candidate_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["candidate_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class DecisionCandidateScoreComponent(BaseModel):
    """One normalized and weighted contribution to candidate ranking."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: DecisionCandidateScoreComponentName
    raw_value: Decimal = Field(ge=0, le=1)
    weight: Decimal = Field(ge=0, le=1)
    weighted_value: Decimal = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_component(self) -> Self:
        if self.weighted_value != _quantize(self.raw_value * self.weight):
            raise ValueError("decision candidate weighted score is inconsistent")
        return self


class DecisionCandidateRankingEntry(BaseModel):
    """One candidate with deterministic rank and complete score evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank: int = Field(ge=1)
    candidate: DecisionCandidate
    total_score: Decimal = Field(ge=0, le=1)
    components: tuple[DecisionCandidateScoreComponent, ...]

    @model_validator(mode="after")
    def validate_entry(self) -> Self:
        expected_names = tuple(DecisionCandidateScoreComponentName)
        if tuple(item.name for item in self.components) != expected_names:
            raise ValueError("decision candidate score components are incomplete or unordered")
        total = _quantize(sum((item.weighted_value for item in self.components), Decimal("0")))
        if self.total_score != total:
            raise ValueError("decision candidate total score is inconsistent")
        return self


class DecisionCandidateRankingRecord(BaseModel):
    """Immutable candidate construction and ranking evidence for one evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-candidate-ranking-record-v1"] = (
        "decision-candidate-ranking-record-v1"
    )
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    outcome: DecisionStageOutcome
    policy_version: Literal["decision-candidate-v1"]
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source_signal_count: int = Field(ge=1)
    candidate_count: int = Field(ge=0)
    excluded_signal_count: int = Field(ge=0)
    entries: tuple[DecisionCandidateRankingEntry, ...]
    top_candidate_id: str | None = Field(
        default=None,
        pattern=r"^decision-candidate-[a-f0-9]{16}$",
    )
    ranked_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("ranked_at")
    @classmethod
    def normalize_ranked_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome.evaluation_id != self.evaluation_id:
            raise ValueError("candidate ranking outcome belongs to another evaluation")
        if self.outcome.stage is not DecisionStage.CANDIDATE_RANKING:
            raise ValueError("candidate ranking outcome has an invalid stage")
        if self.outcome.evaluated_at != self.ranked_at:
            raise ValueError("candidate ranking time must match its outcome")
        if self.candidate_count + self.excluded_signal_count != self.source_signal_count:
            raise ValueError("candidate ranking counts do not reconcile")
        if len(self.entries) != self.candidate_count:
            raise ValueError("candidate ranking entries do not match candidate count")
        if tuple(item.rank for item in self.entries) != tuple(range(1, self.candidate_count + 1)):
            raise ValueError("candidate ranking ranks must be contiguous")
        expected_order = tuple(
            sorted(
                self.entries,
                key=lambda item: (-item.total_score, item.candidate.candidate_id),
            )
        )
        if self.entries != expected_order:
            raise ValueError("candidate ranking order is inconsistent")
        expected_top = self.entries[0].candidate.candidate_id if self.entries else None
        if self.top_candidate_id != expected_top:
            raise ValueError("candidate ranking top candidate is inconsistent")
        if self.entries:
            if self.outcome.disposition is not DecisionDisposition.ACCEPTED:
                raise ValueError("ranked candidates require an accepted outcome")
        elif (
            self.outcome.disposition is not DecisionDisposition.DEFERRED
            or self.outcome.reason_codes != (DecisionReasonCode.CANDIDATE_NOT_SELECTABLE,)
        ):
            raise ValueError("empty candidate ranking must be explicitly deferred")
        if any(item.candidate.evaluation_id != self.evaluation_id for item in self.entries):
            raise ValueError("candidate ranking contains another evaluation")
        if any(item.candidate.policy_checksum != self.policy_checksum for item in self.entries):
            raise ValueError("candidate ranking policy lineage is inconsistent")
        if self.record_checksum != _checksum(self._checksum_payload()):
            raise ValueError("candidate ranking record checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "candidate_count": self.candidate_count,
            "entries": [item.model_dump(mode="json") for item in self.entries],
            "evaluation_id": self.evaluation_id,
            "excluded_signal_count": self.excluded_signal_count,
            "external_order_submission_allowed": False,
            "offline_only": True,
            "outcome": self.outcome.model_dump(mode="json"),
            "policy_checksum": self.policy_checksum,
            "policy_version": self.policy_version,
            "ranked_at": self.ranked_at.isoformat(),
            "schema_version": self.schema_version,
            "source_signal_count": self.source_signal_count,
            "top_candidate_id": self.top_candidate_id,
        }

    @classmethod
    def build(
        cls,
        *,
        evaluation_id: str,
        policy: DecisionCandidatePolicyV1,
        source_signal_count: int,
        entries: tuple[DecisionCandidateRankingEntry, ...],
        ranked_at: datetime,
    ) -> Self:
        disposition = DecisionDisposition.ACCEPTED if entries else DecisionDisposition.DEFERRED
        reasons = () if entries else (DecisionReasonCode.CANDIDATE_NOT_SELECTABLE,)
        outcome = DecisionStageOutcome.build(
            evaluation_id=evaluation_id,
            stage=DecisionStage.CANDIDATE_RANKING,
            disposition=disposition,
            reason_codes=reasons,
            evaluated_at=ranked_at,
        )
        unvalidated = cls.model_construct(
            evaluation_id=evaluation_id,
            outcome=outcome,
            policy_version=policy.policy_version,
            policy_checksum=policy.definition_checksum,
            source_signal_count=source_signal_count,
            candidate_count=len(entries),
            excluded_signal_count=source_signal_count - len(entries),
            entries=entries,
            top_candidate_id=entries[0].candidate.candidate_id if entries else None,
            ranked_at=ranked_at,
            record_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["record_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class DecisionCandidateIntegrityError(ValueError):
    """Persisted candidate inputs no longer form the pinned lineage."""


def build_decision_candidate_ranking(
    *,
    intent: DecisionEvaluationIntent,
    strategy_evaluation: StrategyEvaluationRecord,
    dataset: DatasetSnapshot,
    policy: DecisionCandidatePolicyV1 | None = None,
) -> DecisionCandidateRankingRecord:
    """Construct and rank candidates without clock, network, or account state."""

    resolved_policy = policy or decision_candidate_policy_v1()
    if strategy_evaluation.evaluation_id != intent.evaluation_id:
        raise DecisionCandidateIntegrityError("strategy evaluation belongs to another intent")
    if strategy_evaluation.outcome.disposition is not DecisionDisposition.ACCEPTED:
        raise DecisionCandidateIntegrityError(
            "candidate ranking requires accepted strategy evidence"
        )
    if (
        dataset.dataset_id != intent.dataset.dataset_id
        or dataset.checksum != intent.dataset.dataset_checksum
    ):
        raise DecisionCandidateIntegrityError("candidate dataset does not match the pinned intent")

    candidates = tuple(
        candidate
        for signal in strategy_evaluation.signals
        if (
            candidate := _candidate_from_signal(
                intent=intent,
                signal=signal,
                dataset=dataset,
                policy=resolved_policy,
            )
        )
        is not None
    )
    scored = tuple(_score_candidate(candidate, resolved_policy) for candidate in candidates)
    ordered = tuple(sorted(scored, key=lambda item: (-item[0], item[1].candidate_id)))
    entries = tuple(
        DecisionCandidateRankingEntry(
            rank=index,
            candidate=candidate,
            total_score=score,
            components=components,
        )
        for index, (score, candidate, components) in enumerate(ordered, start=1)
    )
    return DecisionCandidateRankingRecord.build(
        evaluation_id=intent.evaluation_id,
        policy=resolved_policy,
        source_signal_count=strategy_evaluation.signal_count,
        entries=entries,
        ranked_at=intent.requested_at,
    )


def _candidate_from_signal(
    *,
    intent: DecisionEvaluationIntent,
    signal: StrategySignal,
    dataset: DatasetSnapshot,
    policy: DecisionCandidatePolicyV1,
) -> DecisionCandidate | None:
    if signal.dataset_id != dataset.dataset_id or signal.pair != dataset.pair:
        raise DecisionCandidateIntegrityError("candidate signal dataset lineage is inconsistent")
    if signal.timeframe is not dataset.timeframe:
        raise DecisionCandidateIntegrityError("candidate signal timeframe lineage is inconsistent")
    matches = tuple(
        candle
        for candle in dataset.candles
        if candle.open_time == signal.candle_open_time
        and candle.close_time == signal.candle_close_time
    )
    if len(matches) != 1:
        raise DecisionCandidateIntegrityError(
            "candidate signal must resolve to exactly one source candle"
        )
    candle = matches[0]
    entry = candle.close_price
    if signal.direction is SignalDirection.LONG:
        invalidation = candle.low_price
        unit_risk = entry - invalidation
        target = entry + unit_risk * policy.reward_risk_ratio
    elif signal.direction is SignalDirection.SHORT:
        invalidation = candle.high_price
        unit_risk = invalidation - entry
        target = entry - unit_risk * policy.reward_risk_ratio
    else:
        return None
    if unit_risk <= 0 or target <= 0:
        return None
    return DecisionCandidate.build(
        intent=intent,
        signal=signal,
        entry_price=entry,
        invalidation_price=invalidation,
        target_price=target,
        policy=policy,
    )


def _score_candidate(
    candidate: DecisionCandidate,
    policy: DecisionCandidatePolicyV1,
) -> tuple[
    Decimal,
    DecisionCandidate,
    tuple[DecisionCandidateScoreComponent, ...],
]:
    components = (
        _score_component(
            DecisionCandidateScoreComponentName.CONTEXT_CONFIDENCE,
            candidate.context_confidence,
            policy.context_confidence_weight,
        ),
        _score_component(
            DecisionCandidateScoreComponentName.SIGNAL_STRENGTH,
            abs(candidate.signal_score),
            policy.signal_strength_weight,
        ),
    )
    score = _quantize(sum((item.weighted_value for item in components), Decimal("0")))
    return score, candidate, components


def _score_component(
    name: DecisionCandidateScoreComponentName,
    raw_value: Decimal,
    weight: Decimal,
) -> DecisionCandidateScoreComponent:
    normalized_raw = _quantize(raw_value)
    normalized_weight = _quantize(weight)
    return DecisionCandidateScoreComponent(
        name=name,
        raw_value=normalized_raw,
        weight=normalized_weight,
        weighted_value=_quantize(normalized_raw * normalized_weight),
    )
