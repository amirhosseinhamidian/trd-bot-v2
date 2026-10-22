import hashlib
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextProductView,
    MarketContextUnavailableReason,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies.metadata import (
    StrategyLifecycleStatus,
    StrategyMetadata,
    StrategyParameterKind,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision timestamp must include timezone information")
    return value.astimezone(UTC)


def _normalize_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("decision text cannot be empty")
    return normalized


def _canonical_decimal(value: object) -> str:
    if isinstance(value, bool):
        raise ValueError("decision decimal parameter cannot be boolean")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("decision decimal parameter is invalid") from error
    if not parsed.is_finite():
        raise ValueError("decision decimal parameter must be finite")
    if parsed == 0:
        return "0"
    return format(parsed.normalize(), "f")


class DecisionMode(StrEnum):
    """Execution modes admitted by the offline decision-support boundary."""

    RESEARCH = "research"
    SHADOW = "shadow"
    PAPER = "paper"


class DecisionStage(StrEnum):
    """Ordered decision stages planned for the Phase 5 pipeline."""

    STRATEGY_EVALUATION = "strategy_evaluation"
    CANDIDATE_RANKING = "candidate_ranking"
    RISK_GATE = "risk_gate"
    PORTFOLIO_SIMULATION = "portfolio_simulation"


class DecisionDisposition(StrEnum):
    """Stable meaning of one completed decision stage."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    UNAVAILABLE = "unavailable"


class DecisionReasonCode(StrEnum):
    """Version-one fail-closed reasons shared by decision stages."""

    POLICY_DISABLED = "policy_disabled"
    MODE_NOT_ALLOWED = "mode_not_allowed"
    MARKET_CONTEXT_NOT_CONSUMABLE = "market_context_not_consumable"
    MARKET_CONTEXT_EXPIRED = "market_context_expired"
    MARKET_CONTEXT_BOUNDARY_MISMATCH = "market_context_boundary_mismatch"
    MARKET_CONTEXT_NOT_READY = "market_context_not_ready"
    DATASET_PAIR_MISMATCH = "dataset_pair_mismatch"
    DATASET_SOURCE_MISMATCH = "dataset_source_mismatch"
    DATASET_LOOKAHEAD = "dataset_lookahead"
    STRATEGY_NOT_ACTIVE = "strategy_not_active"
    STRATEGY_CONTEXT_INCOMPATIBLE = "strategy_context_incompatible"
    SIGNAL_NEUTRAL = "signal_neutral"
    CANDIDATE_NOT_SELECTABLE = "candidate_not_selectable"
    RISK_POLICY_REJECTED = "risk_policy_rejected"
    PORTFOLIO_POLICY_REJECTED = "portfolio_policy_rejected"
    PORTFOLIO_UNAVAILABLE = "portfolio_unavailable"
    UNCERTAINTY_ABOVE_LIMIT = "uncertainty_above_limit"


class DecisionPolicyState(StrEnum):
    """Whether one immutable decision policy version may be evaluated."""

    ENABLED = "enabled"
    DISABLED = "disabled"


class DecisionStrategyParameterValue(BaseModel):
    """Canonical scalar parameter pinned into a strategy reference."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=100)
    kind: StrategyParameterKind
    value: str = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_canonical_value(self) -> Self:
        if self.kind is StrategyParameterKind.INTEGER:
            try:
                canonical = str(int(self.value))
            except ValueError as error:
                raise ValueError("decision integer parameter is invalid") from error
            if self.value != canonical:
                raise ValueError("decision integer parameter must use canonical notation")
        elif self.value != _canonical_decimal(self.value):
            raise ValueError("decision decimal parameter must use canonical notation")
        return self

    @classmethod
    def from_value(
        cls,
        *,
        name: str,
        kind: StrategyParameterKind,
        value: object,
    ) -> Self:
        if kind is StrategyParameterKind.INTEGER:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("decision integer parameter must be an integer")
            canonical = str(value)
        else:
            canonical = _canonical_decimal(value)
        return cls(name=name, kind=kind, value=canonical)


class DecisionDatasetReference(BaseModel):
    """Tamper-evident pointer to one immutable strategy input dataset."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-dataset-reference-v1"] = "decision-dataset-reference-v1"
    reference_id: str = Field(pattern=r"^decision-dataset-[a-f0-9]{16}$")
    dataset_id: str = Field(min_length=1, max_length=100)
    dataset_schema_version: int = Field(ge=1)
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe
    start_time: datetime
    end_time: datetime
    created_at: datetime
    candle_count: int = Field(gt=0)
    dataset_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("start_time", "end_time", "created_at")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @staticmethod
    def _checksum_payload(
        *,
        dataset_id: str,
        dataset_schema_version: int,
        source: str,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        created_at: datetime,
        candle_count: int,
        dataset_checksum: str,
    ) -> dict[str, object]:
        return {
            "candle_count": candle_count,
            "created_at": _normalize_timestamp(created_at).isoformat(),
            "dataset_checksum": dataset_checksum,
            "dataset_id": dataset_id,
            "dataset_schema_version": dataset_schema_version,
            "end_time": _normalize_timestamp(end_time).isoformat(),
            "pair": pair.model_dump(mode="json"),
            "schema_version": "decision-dataset-reference-v1",
            "source": _normalize_text(source),
            "start_time": _normalize_timestamp(start_time).isoformat(),
            "timeframe": timeframe.value,
        }

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        if self.end_time <= self.start_time:
            raise ValueError("decision dataset end time must be after start time")
        expected_checksum = _checksum(
            self._checksum_payload(
                dataset_id=self.dataset_id,
                dataset_schema_version=self.dataset_schema_version,
                source=self.source,
                pair=self.pair,
                timeframe=self.timeframe,
                start_time=self.start_time,
                end_time=self.end_time,
                created_at=self.created_at,
                candle_count=self.candle_count,
                dataset_checksum=self.dataset_checksum,
            )
        )
        if self.reference_checksum != expected_checksum:
            raise ValueError("decision dataset reference checksum is inconsistent")
        if self.reference_id != f"decision-dataset-{expected_checksum[:16]}":
            raise ValueError("decision dataset reference ID is inconsistent")
        return self

    @classmethod
    def from_dataset(cls, dataset: DatasetSnapshot) -> Self:
        payload = cls._checksum_payload(
            dataset_id=dataset.dataset_id,
            dataset_schema_version=dataset.schema_version,
            source=dataset.source,
            pair=dataset.pair,
            timeframe=dataset.timeframe,
            start_time=dataset.start_time,
            end_time=dataset.end_time,
            created_at=dataset.created_at,
            candle_count=dataset.candle_count,
            dataset_checksum=dataset.checksum,
        )
        checksum = _checksum(payload)
        return cls(
            reference_id=f"decision-dataset-{checksum[:16]}",
            dataset_id=dataset.dataset_id,
            dataset_schema_version=dataset.schema_version,
            source=dataset.source,
            pair=dataset.pair,
            timeframe=dataset.timeframe,
            start_time=dataset.start_time,
            end_time=dataset.end_time,
            created_at=dataset.created_at,
            candle_count=dataset.candle_count,
            dataset_checksum=dataset.checksum,
            reference_checksum=checksum,
        )


class DecisionStrategyReference(BaseModel):
    """Exact executable strategy identity and canonical parameter values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-strategy-reference-v1"] = "decision-strategy-reference-v1"
    reference_id: str = Field(pattern=r"^decision-strategy-[a-f0-9]{16}$")
    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    behavior_fingerprint: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    lifecycle_status: StrategyLifecycleStatus
    parameters: tuple[DecisionStrategyParameterValue, ...]
    reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("strategy_name", "strategy_version")
    @classmethod
    def normalize_strategy_text(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("parameters")
    @classmethod
    def validate_parameters(
        cls,
        value: tuple[DecisionStrategyParameterValue, ...],
    ) -> tuple[DecisionStrategyParameterValue, ...]:
        if tuple(item.name for item in value) != tuple(sorted(item.name for item in value)):
            raise ValueError("decision strategy parameters must use deterministic order")
        if len(value) != len({item.name for item in value}):
            raise ValueError("decision strategy parameters must be unique")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        strategy_name: str,
        strategy_version: str,
        behavior_fingerprint: str,
        lifecycle_status: StrategyLifecycleStatus,
        parameters: tuple[DecisionStrategyParameterValue, ...],
    ) -> dict[str, object]:
        return {
            "behavior_fingerprint": behavior_fingerprint,
            "lifecycle_status": lifecycle_status.value,
            "parameters": [item.model_dump(mode="json") for item in parameters],
            "schema_version": "decision-strategy-reference-v1",
            "strategy_name": _normalize_text(strategy_name),
            "strategy_version": _normalize_text(strategy_version),
        }

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        expected_checksum = _checksum(
            self._checksum_payload(
                strategy_name=self.strategy_name,
                strategy_version=self.strategy_version,
                behavior_fingerprint=self.behavior_fingerprint,
                lifecycle_status=self.lifecycle_status,
                parameters=self.parameters,
            )
        )
        if self.reference_checksum != expected_checksum:
            raise ValueError("decision strategy reference checksum is inconsistent")
        if self.reference_id != f"decision-strategy-{expected_checksum[:16]}":
            raise ValueError("decision strategy reference ID is inconsistent")
        return self

    @classmethod
    def from_metadata(
        cls,
        metadata: StrategyMetadata,
        *,
        parameters: Mapping[str, object],
    ) -> Self:
        definitions = {item.name: item for item in metadata.parameters}
        if set(parameters) != set(definitions):
            missing = sorted(set(definitions) - set(parameters))
            unexpected = sorted(set(parameters) - set(definitions))
            detail = missing[0] if missing else unexpected[0]
            raise ValueError(f"decision strategy parameter set is incomplete: {detail}")
        values = tuple(
            DecisionStrategyParameterValue.from_value(
                name=name,
                kind=definitions[name].kind,
                value=parameters[name],
            )
            for name in sorted(definitions)
        )
        payload = cls._checksum_payload(
            strategy_name=metadata.name,
            strategy_version=metadata.version,
            behavior_fingerprint=metadata.behavior_fingerprint,
            lifecycle_status=metadata.lifecycle_status,
            parameters=values,
        )
        checksum = _checksum(payload)
        return cls(
            reference_id=f"decision-strategy-{checksum[:16]}",
            strategy_name=metadata.name,
            strategy_version=metadata.version,
            behavior_fingerprint=metadata.behavior_fingerprint,
            lifecycle_status=metadata.lifecycle_status,
            parameters=values,
            reference_checksum=checksum,
        )


def build_decision_source_assessment_checksum(assessment: MarketRegimeAssessment) -> str:
    """Checksum the complete immutable assessment admitted to a decision intent."""

    return _checksum(assessment.model_dump(mode="json"))


class MarketContextDecisionReference(BaseModel):
    """Tamper-evident context view captured at decision request time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-decision-reference-v1"] = (
        "market-context-decision-reference-v1"
    )
    reference_id: str = Field(pattern=r"^decision-context-[a-f0-9]{16}$")
    assessment_id: str = Field(pattern=r"^market-regime-[a-f0-9]{16}$")
    assessment_schema_version: Literal["market-regime-assessment-v1"] = (
        "market-regime-assessment-v1"
    )
    assessment_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    as_of: datetime
    assessed_at: datetime
    expires_at: datetime
    evaluated_at: datetime
    expected_as_of: datetime
    assessment_status: MarketContextAssessmentStatus
    trend: MarketTrendRegime
    volatility: MarketVolatilityRegime
    confidence: Decimal = Field(ge=0, le=1)
    consumable: bool
    unavailable_reasons: tuple[MarketContextUnavailableReason, ...]
    reference_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("source")
    @classmethod
    def normalize_source(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("as_of", "assessed_at", "expires_at", "evaluated_at", "expected_as_of")
    @classmethod
    def normalize_timestamps(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("unavailable_reasons")
    @classmethod
    def validate_unavailable_reasons(
        cls,
        value: tuple[MarketContextUnavailableReason, ...],
    ) -> tuple[MarketContextUnavailableReason, ...]:
        expected = tuple(sorted(value, key=lambda item: item.value))
        if value != expected:
            raise ValueError("decision context unavailable reasons must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("decision context unavailable reasons must be unique")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        assessment_id: str,
        assessment_checksum: str,
        source: str,
        pair: TradingPair,
        as_of: datetime,
        assessed_at: datetime,
        expires_at: datetime,
        evaluated_at: datetime,
        expected_as_of: datetime,
        assessment_status: MarketContextAssessmentStatus,
        trend: MarketTrendRegime,
        volatility: MarketVolatilityRegime,
        confidence: Decimal,
        consumable: bool,
        unavailable_reasons: tuple[MarketContextUnavailableReason, ...],
    ) -> dict[str, object]:
        return {
            "as_of": _normalize_timestamp(as_of).isoformat(),
            "assessed_at": _normalize_timestamp(assessed_at).isoformat(),
            "assessment_checksum": assessment_checksum,
            "assessment_id": assessment_id,
            "assessment_schema_version": "market-regime-assessment-v1",
            "assessment_status": assessment_status.value,
            "confidence": str(confidence),
            "consumable": consumable,
            "evaluated_at": _normalize_timestamp(evaluated_at).isoformat(),
            "expected_as_of": _normalize_timestamp(expected_as_of).isoformat(),
            "expires_at": _normalize_timestamp(expires_at).isoformat(),
            "pair": pair.model_dump(mode="json"),
            "schema_version": "market-context-decision-reference-v1",
            "source": _normalize_text(source),
            "trend": trend.value,
            "unavailable_reasons": [item.value for item in unavailable_reasons],
            "volatility": volatility.value,
        }

    @model_validator(mode="after")
    def validate_reference(self) -> Self:
        expected_reasons: set[MarketContextUnavailableReason] = set()
        if self.assessment_status is not MarketContextAssessmentStatus.READY:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_NOT_READY)
        if self.expires_at <= self.evaluated_at:
            expected_reasons.add(MarketContextUnavailableReason.ASSESSMENT_EXPIRED)
        if self.as_of != self.expected_as_of:
            expected_reasons.add(MarketContextUnavailableReason.BOUNDARY_MISMATCH)
        ordered_reasons = tuple(sorted(expected_reasons, key=lambda item: item.value))
        if self.unavailable_reasons != ordered_reasons:
            raise ValueError("decision context consumption reasons are inconsistent")
        if self.consumable != (not ordered_reasons):
            raise ValueError("decision context consumption decision is inconsistent")

        expected_checksum = _checksum(
            self._checksum_payload(
                assessment_id=self.assessment_id,
                assessment_checksum=self.assessment_checksum,
                source=self.source,
                pair=self.pair,
                as_of=self.as_of,
                assessed_at=self.assessed_at,
                expires_at=self.expires_at,
                evaluated_at=self.evaluated_at,
                expected_as_of=self.expected_as_of,
                assessment_status=self.assessment_status,
                trend=self.trend,
                volatility=self.volatility,
                confidence=self.confidence,
                consumable=self.consumable,
                unavailable_reasons=self.unavailable_reasons,
            )
        )
        if self.reference_checksum != expected_checksum:
            raise ValueError("decision context reference checksum is inconsistent")
        if self.reference_id != f"decision-context-{expected_checksum[:16]}":
            raise ValueError("decision context reference ID is inconsistent")
        return self

    @classmethod
    def from_product_view(cls, view: MarketContextProductView) -> Self:
        assessment = view.assessment
        assessment_checksum = build_decision_source_assessment_checksum(assessment)
        payload = cls._checksum_payload(
            assessment_id=assessment.assessment_id,
            assessment_checksum=assessment_checksum,
            source=assessment.source,
            pair=assessment.pair,
            as_of=assessment.as_of,
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
            evaluated_at=view.evaluated_at,
            expected_as_of=view.expected_as_of,
            assessment_status=assessment.status,
            trend=assessment.trend,
            volatility=assessment.volatility,
            confidence=assessment.confidence,
            consumable=view.consumable,
            unavailable_reasons=view.unavailable_reasons,
        )
        checksum = _checksum(payload)
        return cls(
            reference_id=f"decision-context-{checksum[:16]}",
            assessment_id=assessment.assessment_id,
            assessment_checksum=assessment_checksum,
            source=assessment.source,
            pair=assessment.pair,
            as_of=assessment.as_of,
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
            evaluated_at=view.evaluated_at,
            expected_as_of=view.expected_as_of,
            assessment_status=assessment.status,
            trend=assessment.trend,
            volatility=assessment.volatility,
            confidence=assessment.confidence,
            consumable=view.consumable,
            unavailable_reasons=view.unavailable_reasons,
            reference_checksum=checksum,
        )


def build_decision_policy_id(*, policy_key: str) -> str:
    """Build the stable identity shared by immutable versions of one policy."""

    normalized = _normalize_text(policy_key)
    return f"decision-policy-{_checksum({'policy_key': normalized})[:16]}"


class DecisionPolicyDefinition(BaseModel):
    """Versioned safety and admission boundary for decision evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-policy-definition-v1"] = "decision-policy-definition-v1"
    policy_id: str = Field(pattern=r"^decision-policy-[a-f0-9]{16}$")
    policy_key: str = Field(min_length=1, max_length=100)
    policy_version: int = Field(ge=1)
    supersedes_version: int | None = Field(default=None, ge=1)
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    state: DecisionPolicyState
    allowed_modes: tuple[DecisionMode, ...] = Field(min_length=1)
    require_consumable_market_context: Literal[True] = True
    require_active_strategy: Literal[True] = True
    same_pair_only: Literal[True] = True
    same_source_only: Literal[True] = True
    reject_dataset_lookahead: Literal[True] = True
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    created_at: datetime
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("policy_key", "name", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _normalize_text(value)

    @field_validator("created_at")
    @classmethod
    def normalize_created_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("allowed_modes")
    @classmethod
    def validate_allowed_modes(
        cls,
        value: tuple[DecisionMode, ...],
    ) -> tuple[DecisionMode, ...]:
        order = {mode: index for index, mode in enumerate(DecisionMode)}
        expected = tuple(sorted(value, key=order.__getitem__))
        if value != expected:
            raise ValueError("decision policy modes must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("decision policy modes must be unique")
        return value

    @staticmethod
    def _checksum_payload(
        *,
        policy_id: str,
        policy_key: str,
        policy_version: int,
        supersedes_version: int | None,
        name: str,
        description: str,
        state: DecisionPolicyState,
        allowed_modes: tuple[DecisionMode, ...],
        created_at: datetime,
    ) -> dict[str, object]:
        return {
            "allowed_modes": [mode.value for mode in allowed_modes],
            "created_at": _normalize_timestamp(created_at).isoformat(),
            "description": _normalize_text(description),
            "external_order_submission_allowed": False,
            "name": _normalize_text(name),
            "offline_only": True,
            "policy_id": policy_id,
            "policy_key": _normalize_text(policy_key),
            "policy_version": policy_version,
            "reject_dataset_lookahead": True,
            "require_active_strategy": True,
            "require_consumable_market_context": True,
            "same_pair_only": True,
            "same_source_only": True,
            "schema_version": "decision-policy-definition-v1",
            "state": state.value,
            "supersedes_version": supersedes_version,
        }

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        expected_supersedes = None if self.policy_version == 1 else self.policy_version - 1
        if self.supersedes_version != expected_supersedes:
            raise ValueError("decision policy must reference its immediate predecessor")
        if self.policy_id != build_decision_policy_id(policy_key=self.policy_key):
            raise ValueError("decision policy ID is inconsistent")
        expected_checksum = _checksum(
            self._checksum_payload(
                policy_id=self.policy_id,
                policy_key=self.policy_key,
                policy_version=self.policy_version,
                supersedes_version=self.supersedes_version,
                name=self.name,
                description=self.description,
                state=self.state,
                allowed_modes=self.allowed_modes,
                created_at=self.created_at,
            )
        )
        if self.definition_checksum != expected_checksum:
            raise ValueError("decision policy checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        policy_key: str,
        policy_version: int,
        name: str,
        description: str,
        state: DecisionPolicyState,
        allowed_modes: tuple[DecisionMode, ...],
        created_at: datetime,
    ) -> Self:
        normalized_key = _normalize_text(policy_key)
        policy_id = build_decision_policy_id(policy_key=normalized_key)
        supersedes_version = None if policy_version == 1 else policy_version - 1
        order = {mode: index for index, mode in enumerate(DecisionMode)}
        ordered_modes = tuple(sorted(allowed_modes, key=order.__getitem__))
        payload = cls._checksum_payload(
            policy_id=policy_id,
            policy_key=normalized_key,
            policy_version=policy_version,
            supersedes_version=supersedes_version,
            name=name,
            description=description,
            state=state,
            allowed_modes=ordered_modes,
            created_at=created_at,
        )
        return cls(
            policy_id=policy_id,
            policy_key=normalized_key,
            policy_version=policy_version,
            supersedes_version=supersedes_version,
            name=name,
            description=description,
            state=state,
            allowed_modes=ordered_modes,
            created_at=created_at,
            definition_checksum=_checksum(payload),
        )


class DecisionPolicyReference(BaseModel):
    """Immutable policy identity captured by one decision intent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-policy-reference-v1"] = "decision-policy-reference-v1"
    policy_id: str = Field(pattern=r"^decision-policy-[a-f0-9]{16}$")
    policy_version: int = Field(ge=1)
    state: DecisionPolicyState
    allowed_modes: tuple[DecisionMode, ...] = Field(min_length=1)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @classmethod
    def from_definition(cls, definition: DecisionPolicyDefinition) -> Self:
        return cls(
            policy_id=definition.policy_id,
            policy_version=definition.policy_version,
            state=definition.state,
            allowed_modes=definition.allowed_modes,
            definition_checksum=definition.definition_checksum,
        )


def _decision_evaluation_identity(
    *,
    mode: DecisionMode,
    dataset: DecisionDatasetReference,
    strategy: DecisionStrategyReference,
    market_context: MarketContextDecisionReference,
    policy: DecisionPolicyReference,
) -> dict[str, object]:
    return {
        "dataset_reference_checksum": dataset.reference_checksum,
        "market_context_reference_checksum": market_context.reference_checksum,
        "mode": mode.value,
        "policy_definition_checksum": policy.definition_checksum,
        "policy_id": policy.policy_id,
        "policy_version": policy.policy_version,
        "strategy_reference_checksum": strategy.reference_checksum,
    }


def build_decision_evaluation_id(
    *,
    mode: DecisionMode,
    dataset: DecisionDatasetReference,
    strategy: DecisionStrategyReference,
    market_context: MarketContextDecisionReference,
    policy: DecisionPolicyReference,
) -> str:
    """Build one deterministic identity for an exact decision input set."""

    identity = _decision_evaluation_identity(
        mode=mode,
        dataset=dataset,
        strategy=strategy,
        market_context=market_context,
        policy=policy,
    )
    return f"decision-evaluation-{_checksum(identity)[:16]}"


def build_decision_evaluation_idempotency_key(intent: "DecisionEvaluationIntent") -> str:
    """Build the durable queue key for one logical decision evaluation."""

    identity = _decision_evaluation_identity(
        mode=intent.mode,
        dataset=intent.dataset,
        strategy=intent.strategy,
        market_context=intent.market_context,
        policy=intent.policy,
    )
    return f"decision-evaluation:{_checksum(identity)}"


class DecisionEvaluationIntent(BaseModel):
    """Immutable and offline-only intent that starts the Phase 5 pipeline."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-evaluation-intent-v1"] = "decision-evaluation-intent-v1"
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    stage: Literal[DecisionStage.STRATEGY_EVALUATION] = DecisionStage.STRATEGY_EVALUATION
    mode: DecisionMode
    dataset: DecisionDatasetReference
    strategy: DecisionStrategyReference
    market_context: MarketContextDecisionReference
    policy: DecisionPolicyReference
    requested_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    intent_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("requested_at")
    @classmethod
    def normalize_requested_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @staticmethod
    def _checksum_payload(
        *,
        evaluation_id: str,
        mode: DecisionMode,
        dataset: DecisionDatasetReference,
        strategy: DecisionStrategyReference,
        market_context: MarketContextDecisionReference,
        policy: DecisionPolicyReference,
        requested_at: datetime,
    ) -> dict[str, object]:
        return {
            "dataset": dataset.model_dump(mode="json"),
            "evaluation_id": evaluation_id,
            "external_order_submission_allowed": False,
            "market_context": market_context.model_dump(mode="json"),
            "mode": mode.value,
            "offline_only": True,
            "policy": policy.model_dump(mode="json"),
            "requested_at": _normalize_timestamp(requested_at).isoformat(),
            "schema_version": "decision-evaluation-intent-v1",
            "stage": DecisionStage.STRATEGY_EVALUATION.value,
            "strategy": strategy.model_dump(mode="json"),
        }

    @model_validator(mode="after")
    def validate_intent(self) -> Self:
        if self.requested_at != self.market_context.evaluated_at:
            raise ValueError("decision context must be captured at request time")
        if self.mode not in self.policy.allowed_modes:
            raise ValueError(DecisionReasonCode.MODE_NOT_ALLOWED.value)
        if self.dataset.pair != self.market_context.pair:
            raise ValueError(DecisionReasonCode.DATASET_PAIR_MISMATCH.value)
        if self.dataset.source != self.market_context.source:
            raise ValueError(DecisionReasonCode.DATASET_SOURCE_MISMATCH.value)
        if self.dataset.end_time > self.market_context.as_of:
            raise ValueError(DecisionReasonCode.DATASET_LOOKAHEAD.value)

        expected_id = build_decision_evaluation_id(
            mode=self.mode,
            dataset=self.dataset,
            strategy=self.strategy,
            market_context=self.market_context,
            policy=self.policy,
        )
        if self.evaluation_id != expected_id:
            raise ValueError("decision evaluation ID is inconsistent")
        expected_checksum = _checksum(
            self._checksum_payload(
                evaluation_id=self.evaluation_id,
                mode=self.mode,
                dataset=self.dataset,
                strategy=self.strategy,
                market_context=self.market_context,
                policy=self.policy,
                requested_at=self.requested_at,
            )
        )
        if self.intent_checksum != expected_checksum:
            raise ValueError("decision intent checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        mode: DecisionMode,
        dataset: DatasetSnapshot,
        strategy: StrategyMetadata,
        strategy_parameters: Mapping[str, object],
        market_context: MarketContextProductView,
        policy: DecisionPolicyDefinition,
        requested_at: datetime,
    ) -> Self:
        requested = _normalize_timestamp(requested_at)
        dataset_reference = DecisionDatasetReference.from_dataset(dataset)
        strategy_reference = DecisionStrategyReference.from_metadata(
            strategy,
            parameters=strategy_parameters,
        )
        context_reference = MarketContextDecisionReference.from_product_view(market_context)
        policy_reference = DecisionPolicyReference.from_definition(policy)
        evaluation_id = build_decision_evaluation_id(
            mode=mode,
            dataset=dataset_reference,
            strategy=strategy_reference,
            market_context=context_reference,
            policy=policy_reference,
        )
        payload = cls._checksum_payload(
            evaluation_id=evaluation_id,
            mode=mode,
            dataset=dataset_reference,
            strategy=strategy_reference,
            market_context=context_reference,
            policy=policy_reference,
            requested_at=requested,
        )
        return cls(
            evaluation_id=evaluation_id,
            mode=mode,
            dataset=dataset_reference,
            strategy=strategy_reference,
            market_context=context_reference,
            policy=policy_reference,
            requested_at=requested,
            intent_checksum=_checksum(payload),
        )


class DecisionStageOutcome(BaseModel):
    """Tamper-evident semantic outcome for one stage of an evaluation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-stage-outcome-v1"] = "decision-stage-outcome-v1"
    outcome_id: str = Field(pattern=r"^decision-outcome-[a-f0-9]{16}$")
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    stage: DecisionStage
    disposition: DecisionDisposition
    reason_codes: tuple[DecisionReasonCode, ...] = ()
    evaluated_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    outcome_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @field_validator("reason_codes")
    @classmethod
    def validate_reason_codes(
        cls,
        value: tuple[DecisionReasonCode, ...],
    ) -> tuple[DecisionReasonCode, ...]:
        expected = tuple(sorted(value, key=lambda item: item.value))
        if value != expected:
            raise ValueError("decision reason codes must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("decision reason codes must be unique")
        return value

    @staticmethod
    def _identity(*, evaluation_id: str, stage: DecisionStage) -> dict[str, object]:
        return {"evaluation_id": evaluation_id, "stage": stage.value}

    @staticmethod
    def _checksum_payload(
        *,
        outcome_id: str,
        evaluation_id: str,
        stage: DecisionStage,
        disposition: DecisionDisposition,
        reason_codes: tuple[DecisionReasonCode, ...],
        evaluated_at: datetime,
    ) -> dict[str, object]:
        return {
            "disposition": disposition.value,
            "evaluated_at": _normalize_timestamp(evaluated_at).isoformat(),
            "evaluation_id": evaluation_id,
            "external_order_submission_allowed": False,
            "offline_only": True,
            "outcome_id": outcome_id,
            "reason_codes": [reason.value for reason in reason_codes],
            "schema_version": "decision-stage-outcome-v1",
            "stage": stage.value,
        }

    @model_validator(mode="after")
    def validate_outcome(self) -> Self:
        if self.disposition is DecisionDisposition.ACCEPTED:
            if self.reason_codes:
                raise ValueError("accepted decision outcome cannot contain reason codes")
        elif not self.reason_codes:
            raise ValueError("non-accepted decision outcome requires at least one reason code")

        identity = self._identity(
            evaluation_id=self.evaluation_id,
            stage=self.stage,
        )
        expected_id = f"decision-outcome-{_checksum(identity)[:16]}"
        if self.outcome_id != expected_id:
            raise ValueError("decision outcome ID is inconsistent")
        expected_checksum = _checksum(
            self._checksum_payload(
                outcome_id=self.outcome_id,
                evaluation_id=self.evaluation_id,
                stage=self.stage,
                disposition=self.disposition,
                reason_codes=self.reason_codes,
                evaluated_at=self.evaluated_at,
            )
        )
        if self.outcome_checksum != expected_checksum:
            raise ValueError("decision outcome checksum is inconsistent")
        return self

    @classmethod
    def build(
        cls,
        *,
        evaluation_id: str,
        stage: DecisionStage,
        disposition: DecisionDisposition,
        reason_codes: tuple[DecisionReasonCode, ...],
        evaluated_at: datetime,
    ) -> Self:
        ordered_reasons = tuple(sorted(reason_codes, key=lambda item: item.value))
        identity = cls._identity(
            evaluation_id=evaluation_id,
            stage=stage,
        )
        outcome_id = f"decision-outcome-{_checksum(identity)[:16]}"
        payload = cls._checksum_payload(
            outcome_id=outcome_id,
            evaluation_id=evaluation_id,
            stage=stage,
            disposition=disposition,
            reason_codes=ordered_reasons,
            evaluated_at=evaluated_at,
        )
        return cls(
            outcome_id=outcome_id,
            evaluation_id=evaluation_id,
            stage=stage,
            disposition=disposition,
            reason_codes=ordered_reasons,
            evaluated_at=evaluated_at,
            outcome_checksum=_checksum(payload),
        )
