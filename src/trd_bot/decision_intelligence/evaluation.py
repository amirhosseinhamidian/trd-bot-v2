import hashlib
import json
from decimal import Decimal
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence.contracts import (
    DecisionDatasetReference,
    DecisionDisposition,
    DecisionEvaluationIntent,
    DecisionPolicyState,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
    DecisionStrategyReference,
)
from trd_bot.market_context import (
    MarketContextUnavailableReason,
    MarketTrendRegime,
    MarketVolatilityRegime,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies import (
    SignalDirection,
    StrategyLifecycleStatus,
    StrategyParameterKind,
    StrategyRegistry,
    StrategySignal,
)


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


class StrategyContextCompatibilityRule(BaseModel):
    """One deterministic admission rule for an exact strategy version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=50)
    allowed_trends: tuple[MarketTrendRegime, ...] = Field(min_length=1)
    allowed_volatilities: tuple[MarketVolatilityRegime, ...] = Field(min_length=1)
    minimum_confidence: Decimal = Field(ge=0, le=1)

    @field_validator("allowed_trends")
    @classmethod
    def validate_trends(
        cls,
        value: tuple[MarketTrendRegime, ...],
    ) -> tuple[MarketTrendRegime, ...]:
        order = {item: index for index, item in enumerate(MarketTrendRegime)}
        if value != tuple(sorted(value, key=order.__getitem__)):
            raise ValueError("strategy context trends must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("strategy context trends must be unique")
        return value

    @field_validator("allowed_volatilities")
    @classmethod
    def validate_volatilities(
        cls,
        value: tuple[MarketVolatilityRegime, ...],
    ) -> tuple[MarketVolatilityRegime, ...]:
        order = {item: index for index, item in enumerate(MarketVolatilityRegime)}
        if value != tuple(sorted(value, key=order.__getitem__)):
            raise ValueError("strategy context volatilities must use deterministic order")
        if len(value) != len(set(value)):
            raise ValueError("strategy context volatilities must be unique")
        return value


class StrategyContextCompatibilityPolicyV1(BaseModel):
    """Frozen v1 Strategy/Regime compatibility matrix."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["strategy-context-compatibility-policy-v1"] = (
        "strategy-context-compatibility-policy-v1"
    )
    policy_version: Literal["strategy-context-compatibility-v1"] = (
        "strategy-context-compatibility-v1"
    )
    rules: tuple[StrategyContextCompatibilityRule, ...] = Field(min_length=1)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        identities = tuple((item.strategy_name, item.strategy_version) for item in self.rules)
        if identities != tuple(sorted(identities)):
            raise ValueError("strategy context rules must use deterministic order")
        if len(identities) != len(set(identities)):
            raise ValueError("strategy context rules must be unique")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("strategy context policy checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "rules": [item.model_dump(mode="json") for item in self.rules],
            "schema_version": self.schema_version,
        }

    def get_rule(
        self,
        *,
        strategy_name: str,
        strategy_version: str,
    ) -> StrategyContextCompatibilityRule | None:
        return next(
            (
                item
                for item in self.rules
                if item.strategy_name == strategy_name and item.strategy_version == strategy_version
            ),
            None,
        )


def strategy_context_compatibility_policy_v1() -> StrategyContextCompatibilityPolicyV1:
    """Return a new validated copy of the canonical compatibility policy."""

    all_volatility = (
        MarketVolatilityRegime.LOW,
        MarketVolatilityRegime.NORMAL,
        MarketVolatilityRegime.HIGH,
    )
    trend_following = (
        MarketTrendRegime.TRENDING_UP,
        MarketTrendRegime.TRENDING_DOWN,
    )
    rules = (
        StrategyContextCompatibilityRule(
            strategy_name="ema-crossover",
            strategy_version="1.0.0",
            allowed_trends=trend_following,
            allowed_volatilities=all_volatility,
            minimum_confidence=Decimal("0.60"),
        ),
        StrategyContextCompatibilityRule(
            strategy_name="rsi-threshold",
            strategy_version="1.0.0",
            allowed_trends=(MarketTrendRegime.RANGING,),
            allowed_volatilities=(
                MarketVolatilityRegime.LOW,
                MarketVolatilityRegime.NORMAL,
            ),
            minimum_confidence=Decimal("0.60"),
        ),
        StrategyContextCompatibilityRule(
            strategy_name="sma-crossover",
            strategy_version="1.0.0",
            allowed_trends=trend_following,
            allowed_volatilities=all_volatility,
            minimum_confidence=Decimal("0.60"),
        ),
    )
    unvalidated = StrategyContextCompatibilityPolicyV1.model_construct(
        rules=rules,
        definition_checksum="0" * 64,
    )
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return StrategyContextCompatibilityPolicyV1.model_validate(payload)


class StrategyEvaluationRecord(BaseModel):
    """Immutable signals and semantic outcome produced for one exact intent."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["strategy-evaluation-record-v1"] = "strategy-evaluation-record-v1"
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    outcome: DecisionStageOutcome
    compatibility_policy_version: Literal["strategy-context-compatibility-v1"]
    compatibility_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    signals: tuple[StrategySignal, ...]
    signal_count: int = Field(ge=0)
    latest_signal_id: str | None = Field(
        default=None,
        pattern=r"^signal-[a-f0-9]{16}$",
    )
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome.evaluation_id != self.evaluation_id:
            raise ValueError("strategy evaluation outcome belongs to another intent")
        if self.outcome.stage is not DecisionStage.STRATEGY_EVALUATION:
            raise ValueError("strategy evaluation outcome has an invalid stage")
        ordered = tuple(
            sorted(self.signals, key=lambda item: (item.candle_close_time, item.signal_id))
        )
        if self.signals != ordered:
            raise ValueError("strategy evaluation signals must use deterministic order")
        if len(self.signals) != len({item.signal_id for item in self.signals}):
            raise ValueError("strategy evaluation signals must be unique")
        if self.signal_count != len(self.signals):
            raise ValueError("strategy evaluation signal count is inconsistent")
        expected_latest = self.signals[-1].signal_id if self.signals else None
        if self.latest_signal_id != expected_latest:
            raise ValueError("strategy evaluation latest signal is inconsistent")
        if self.outcome.disposition is DecisionDisposition.ACCEPTED and not self.signals:
            raise ValueError("accepted strategy evaluation requires at least one signal")
        if self.outcome.disposition is not DecisionDisposition.ACCEPTED and self.signals:
            raise ValueError("non-accepted strategy evaluation cannot expose signals")
        if self.record_checksum != _checksum(self._checksum_payload()):
            raise ValueError("strategy evaluation record checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "compatibility_policy_checksum": self.compatibility_policy_checksum,
            "compatibility_policy_version": self.compatibility_policy_version,
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "latest_signal_id": self.latest_signal_id,
            "offline_only": True,
            "outcome": self.outcome.model_dump(mode="json"),
            "schema_version": self.schema_version,
            "signal_count": self.signal_count,
            "signals": [item.model_dump(mode="json") for item in self.signals],
        }

    @classmethod
    def build(
        cls,
        *,
        outcome: DecisionStageOutcome,
        compatibility_policy: StrategyContextCompatibilityPolicyV1,
        signals: tuple[StrategySignal, ...],
    ) -> Self:
        ordered = tuple(sorted(signals, key=lambda item: (item.candle_close_time, item.signal_id)))
        unvalidated = cls.model_construct(
            evaluation_id=outcome.evaluation_id,
            outcome=outcome,
            compatibility_policy_version=compatibility_policy.policy_version,
            compatibility_policy_checksum=compatibility_policy.definition_checksum,
            signals=ordered,
            signal_count=len(ordered),
            latest_signal_id=ordered[-1].signal_id if ordered else None,
            record_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["record_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class StrategyEvaluationIntegrityError(ValueError):
    """Pinned input no longer matches executable local strategy state."""


def evaluate_strategy_intent(
    *,
    intent: DecisionEvaluationIntent,
    dataset: DatasetSnapshot,
    registry: StrategyRegistry,
    compatibility_policy: StrategyContextCompatibilityPolicyV1 | None = None,
) -> StrategyEvaluationRecord:
    """Evaluate one persisted intent without clock, network, or account side effects."""

    policy = compatibility_policy or strategy_context_compatibility_policy_v1()
    if DecisionDatasetReference.from_dataset(dataset) != intent.dataset:
        raise StrategyEvaluationIntegrityError(
            "strategy evaluation dataset does not match the pinned reference"
        )

    unavailable_reasons = _unavailable_reasons(intent)
    if unavailable_reasons:
        return _build_record(
            intent=intent,
            policy=policy,
            disposition=DecisionDisposition.UNAVAILABLE,
            reason_codes=unavailable_reasons,
        )

    rule = policy.get_rule(
        strategy_name=intent.strategy.strategy_name,
        strategy_version=intent.strategy.strategy_version,
    )
    rejected_reasons: set[DecisionReasonCode] = set()
    if rule is None:
        rejected_reasons.add(DecisionReasonCode.STRATEGY_CONTEXT_INCOMPATIBLE)
    else:
        context = intent.market_context
        if (
            context.trend not in rule.allowed_trends
            or context.volatility not in rule.allowed_volatilities
        ):
            rejected_reasons.add(DecisionReasonCode.STRATEGY_CONTEXT_INCOMPATIBLE)
        if context.confidence < rule.minimum_confidence:
            rejected_reasons.add(DecisionReasonCode.UNCERTAINTY_ABOVE_LIMIT)
    if rejected_reasons:
        return _build_record(
            intent=intent,
            policy=policy,
            disposition=DecisionDisposition.REJECTED,
            reason_codes=tuple(rejected_reasons),
        )

    _validate_registry_reference(intent=intent, registry=registry)
    strategy = registry.create(
        name=intent.strategy.strategy_name,
        version=intent.strategy.strategy_version,
        parameters=_strategy_parameters(intent.strategy),
    )
    signals = tuple(
        sorted(
            strategy.generate(dataset),
            key=lambda item: (item.candle_close_time, item.signal_id),
        )
    )
    _validate_signals(intent=intent, signals=signals)
    if not signals:
        return _build_record(
            intent=intent,
            policy=policy,
            disposition=DecisionDisposition.DEFERRED,
            reason_codes=(DecisionReasonCode.SIGNAL_NEUTRAL,),
        )
    return _build_record(
        intent=intent,
        policy=policy,
        disposition=DecisionDisposition.ACCEPTED,
        signals=signals,
    )


def _unavailable_reasons(
    intent: DecisionEvaluationIntent,
) -> tuple[DecisionReasonCode, ...]:
    reasons: set[DecisionReasonCode] = set()
    if intent.policy.state is DecisionPolicyState.DISABLED:
        reasons.add(DecisionReasonCode.POLICY_DISABLED)
    if intent.strategy.lifecycle_status is not StrategyLifecycleStatus.ACTIVE:
        reasons.add(DecisionReasonCode.STRATEGY_NOT_ACTIVE)
    if not intent.market_context.consumable:
        reasons.add(DecisionReasonCode.MARKET_CONTEXT_NOT_CONSUMABLE)
        mapping = {
            MarketContextUnavailableReason.ASSESSMENT_EXPIRED: (
                DecisionReasonCode.MARKET_CONTEXT_EXPIRED
            ),
            MarketContextUnavailableReason.ASSESSMENT_NOT_READY: (
                DecisionReasonCode.MARKET_CONTEXT_NOT_READY
            ),
            MarketContextUnavailableReason.BOUNDARY_MISMATCH: (
                DecisionReasonCode.MARKET_CONTEXT_BOUNDARY_MISMATCH
            ),
        }
        reasons.update(mapping[item] for item in intent.market_context.unavailable_reasons)
    return tuple(sorted(reasons, key=lambda item: item.value))


def _validate_registry_reference(
    *,
    intent: DecisionEvaluationIntent,
    registry: StrategyRegistry,
) -> None:
    metadata = registry.get_metadata(
        name=intent.strategy.strategy_name,
        version=intent.strategy.strategy_version,
    )
    if metadata is None:
        raise StrategyEvaluationIntegrityError(
            "strategy evaluation executable metadata is unavailable"
        )
    current = DecisionStrategyReference.from_metadata(
        metadata,
        parameters=_strategy_parameters(intent.strategy),
    )
    if current != intent.strategy:
        raise StrategyEvaluationIntegrityError(
            "strategy evaluation executable metadata does not match the pinned reference"
        )


def _strategy_parameters(
    reference: DecisionStrategyReference,
) -> dict[str, int | Decimal]:
    return {
        item.name: int(item.value)
        if item.kind is StrategyParameterKind.INTEGER
        else Decimal(item.value)
        for item in reference.parameters
    }


def _validate_signals(
    *,
    intent: DecisionEvaluationIntent,
    signals: tuple[StrategySignal, ...],
) -> None:
    seen: set[str] = set()
    for signal in signals:
        if signal.signal_id in seen:
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation produced duplicate signal IDs"
            )
        seen.add(signal.signal_id)
        if (
            signal.strategy_name != intent.strategy.strategy_name
            or signal.strategy_version != intent.strategy.strategy_version
            or signal.dataset_id != intent.dataset.dataset_id
            or signal.pair != intent.dataset.pair
            or signal.timeframe is not intent.dataset.timeframe
        ):
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation signal lineage does not match the intent"
            )
        if not (intent.dataset.start_time < signal.candle_close_time <= intent.dataset.end_time):
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation signal is outside the dataset boundary"
            )
        if signal.generated_at != signal.candle_close_time:
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation signal generation time is not reproducible"
            )
        if signal.generated_at > intent.market_context.as_of:
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation signal exceeds the market-context boundary"
            )
        if signal.direction is SignalDirection.NEUTRAL:
            raise StrategyEvaluationIntegrityError(
                "strategy evaluation must represent neutrality as an empty signal set"
            )


def _build_record(
    *,
    intent: DecisionEvaluationIntent,
    policy: StrategyContextCompatibilityPolicyV1,
    disposition: DecisionDisposition,
    reason_codes: tuple[DecisionReasonCode, ...] = (),
    signals: tuple[StrategySignal, ...] = (),
) -> StrategyEvaluationRecord:
    outcome = DecisionStageOutcome.build(
        evaluation_id=intent.evaluation_id,
        stage=DecisionStage.STRATEGY_EVALUATION,
        disposition=disposition,
        reason_codes=reason_codes,
        evaluated_at=intent.requested_at,
    )
    return StrategyEvaluationRecord.build(
        outcome=outcome,
        compatibility_policy=policy,
        signals=signals,
    )
