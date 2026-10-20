import hashlib
import json
from datetime import UTC, datetime
from decimal import ROUND_DOWN, Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence.candidates import (
    DecisionCandidate,
    DecisionCandidateRankingEntry,
    DecisionCandidateRankingRecord,
)
from trd_bot.decision_intelligence.contracts import (
    DecisionDisposition,
    DecisionReasonCode,
    DecisionStage,
    DecisionStageOutcome,
)

AMOUNT_QUANTUM = Decimal("0.00000001")
RATIO_QUANTUM = Decimal("0.000001")


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("decision risk timestamp must include timezone information")
    return value.astimezone(UTC)


def _quantize_amount(value: Decimal) -> Decimal:
    return value.quantize(AMOUNT_QUANTUM, rounding=ROUND_DOWN)


def _quantize_ratio(value: Decimal) -> Decimal:
    return value.quantize(RATIO_QUANTUM, rounding=ROUND_DOWN)


class DecisionRiskDecision(StrEnum):
    """Fail-closed result of evaluating one ranked offline candidate."""

    APPROVED = "approved"
    REJECTED = "rejected"


class DecisionRiskCheckName(StrEnum):
    """Stable ordered checks applied by the version-one risk policy."""

    CANDIDATE_FRESH = "candidate_fresh"
    RANKING_SCORE = "ranking_score"
    REWARD_RISK = "reward_risk"
    RISK_BUDGET = "risk_budget"
    NOTIONAL_CAP = "notional_cap"


class DecisionRiskPolicyV1(BaseModel):
    """Frozen conservative limits for offline position sizing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-risk-policy-v1"] = "decision-risk-policy-v1"
    policy_version: Literal["decision-risk-v1"] = "decision-risk-v1"
    reference_equity: Decimal = Field(default=Decimal("10000.00000000"), gt=0)
    max_risk_fraction: Decimal = Field(default=Decimal("0.010000"), gt=0, le=1)
    max_notional_fraction: Decimal = Field(default=Decimal("0.100000"), gt=0, le=1)
    minimum_ranking_score: Decimal = Field(default=Decimal("0.300000"), ge=0, le=1)
    minimum_reward_risk_ratio: Decimal = Field(default=Decimal("1.500000"), gt=0)
    quantity_quantum: Decimal = Field(default=AMOUNT_QUANTUM, gt=0)
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_policy(self) -> Self:
        expected = {
            "reference_equity": Decimal("10000.00000000"),
            "max_risk_fraction": Decimal("0.010000"),
            "max_notional_fraction": Decimal("0.100000"),
            "minimum_ranking_score": Decimal("0.300000"),
            "minimum_reward_risk_ratio": Decimal("1.500000"),
            "quantity_quantum": AMOUNT_QUANTUM,
        }
        for name, value in expected.items():
            if getattr(self, name) != value:
                raise ValueError(f"decision risk {name} is not version one")
        if self.max_risk_fraction > self.max_notional_fraction:
            raise ValueError("decision risk fraction cannot exceed notional fraction")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision risk policy checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "max_notional_fraction": str(self.max_notional_fraction),
            "max_risk_fraction": str(self.max_risk_fraction),
            "minimum_ranking_score": str(self.minimum_ranking_score),
            "minimum_reward_risk_ratio": str(self.minimum_reward_risk_ratio),
            "policy_version": self.policy_version,
            "quantity_quantum": str(self.quantity_quantum),
            "reference_equity": str(self.reference_equity),
            "schema_version": self.schema_version,
        }


def decision_risk_policy_v1() -> DecisionRiskPolicyV1:
    """Return a validated copy of the canonical risk policy."""

    unvalidated = DecisionRiskPolicyV1.model_construct(definition_checksum="0" * 64)
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return DecisionRiskPolicyV1.model_validate(payload)


class DecisionRiskCheck(BaseModel):
    """One explainable policy check and its observed value."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: DecisionRiskCheckName
    passed: bool
    actual_value: str = Field(min_length=1, max_length=100)
    limit_value: str = Field(min_length=1, max_length=100)
    explanation: str = Field(min_length=1, max_length=500)


class DecisionPositionSizing(BaseModel):
    """Offline-only quantity bounded by risk and notional budgets."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-position-sizing-v1"] = "decision-position-sizing-v1"
    candidate_id: str = Field(pattern=r"^decision-candidate-[a-f0-9]{16}$")
    quote_asset: str = Field(min_length=1, max_length=30)
    reference_equity: Decimal = Field(gt=0)
    risk_budget: Decimal = Field(gt=0)
    notional_cap: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    invalidation_price: Decimal = Field(gt=0)
    unit_price_risk: Decimal = Field(gt=0)
    target_price: Decimal = Field(gt=0)
    reward_risk_ratio: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)
    notional: Decimal = Field(gt=0)
    maximum_loss: Decimal = Field(gt=0)
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    sizing_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_sizing(self) -> Self:
        if self.unit_price_risk != abs(self.entry_price - self.invalidation_price):
            raise ValueError("decision position unit risk is inconsistent")
        expected_ratio = _quantize_ratio(
            abs(self.target_price - self.entry_price) / self.unit_price_risk
        )
        if self.reward_risk_ratio != expected_ratio:
            raise ValueError("decision position reward/risk ratio is inconsistent")
        if self.quantity != _quantize_amount(self.quantity):
            raise ValueError("decision position quantity is not quantized")
        if self.notional != _quantize_amount(self.quantity * self.entry_price):
            raise ValueError("decision position notional is inconsistent")
        if self.maximum_loss != _quantize_amount(self.quantity * self.unit_price_risk):
            raise ValueError("decision position maximum loss is inconsistent")
        if self.notional > self.notional_cap:
            raise ValueError("decision position exceeds its notional cap")
        if self.maximum_loss > self.risk_budget:
            raise ValueError("decision position exceeds its risk budget")
        if self.sizing_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision position sizing checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "entry_price": str(self.entry_price),
            "external_order_submission_allowed": False,
            "invalidation_price": str(self.invalidation_price),
            "maximum_loss": str(self.maximum_loss),
            "notional": str(self.notional),
            "notional_cap": str(self.notional_cap),
            "offline_only": True,
            "quantity": str(self.quantity),
            "quote_asset": self.quote_asset,
            "reference_equity": str(self.reference_equity),
            "reward_risk_ratio": str(self.reward_risk_ratio),
            "risk_budget": str(self.risk_budget),
            "schema_version": self.schema_version,
            "target_price": str(self.target_price),
            "unit_price_risk": str(self.unit_price_risk),
        }

    @classmethod
    def build(
        cls,
        *,
        candidate: DecisionCandidate,
        policy: DecisionRiskPolicyV1,
    ) -> Self | None:
        trade_plan = candidate.trade_plan
        unit_risk = abs(trade_plan.entry_price - trade_plan.invalidation_price)
        if unit_risk <= 0:
            return None
        risk_budget = _quantize_amount(policy.reference_equity * policy.max_risk_fraction)
        notional_cap = _quantize_amount(policy.reference_equity * policy.max_notional_fraction)
        risk_limited = risk_budget / unit_risk
        notional_limited = notional_cap / trade_plan.entry_price
        quantity = min(risk_limited, notional_limited).quantize(
            policy.quantity_quantum,
            rounding=ROUND_DOWN,
        )
        if quantity <= 0:
            return None
        reward_risk = _quantize_ratio(
            abs(trade_plan.target_price - trade_plan.entry_price) / unit_risk
        )
        unvalidated = cls.model_construct(
            candidate_id=candidate.candidate_id,
            quote_asset=candidate.pair.quote_asset,
            reference_equity=policy.reference_equity,
            risk_budget=risk_budget,
            notional_cap=notional_cap,
            entry_price=trade_plan.entry_price,
            invalidation_price=trade_plan.invalidation_price,
            unit_price_risk=unit_risk,
            target_price=trade_plan.target_price,
            reward_risk_ratio=reward_risk,
            quantity=quantity,
            notional=_quantize_amount(quantity * trade_plan.entry_price),
            maximum_loss=_quantize_amount(quantity * unit_risk),
            sizing_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["sizing_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class DecisionRiskAssessment(BaseModel):
    """Auditable risk decision for the top deterministic candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-risk-assessment-v1"] = "decision-risk-assessment-v1"
    assessment_id: str = Field(pattern=r"^decision-risk-[a-f0-9]{16}$")
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    candidate_id: str = Field(pattern=r"^decision-candidate-[a-f0-9]{16}$")
    candidate_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    rank: int = Field(ge=1)
    ranking_score: Decimal = Field(ge=0, le=1)
    decision: DecisionRiskDecision
    checks: tuple[DecisionRiskCheck, ...]
    position_sizing: DecisionPositionSizing | None = None
    evaluated_at: datetime
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    assessment_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        if tuple(item.name for item in self.checks) != tuple(DecisionRiskCheckName):
            raise ValueError("decision risk checks must be complete and ordered")
        expected_decision = (
            DecisionRiskDecision.APPROVED
            if all(item.passed for item in self.checks)
            else DecisionRiskDecision.REJECTED
        )
        if self.decision is not expected_decision:
            raise ValueError("decision risk decision does not match its checks")
        if (self.position_sizing is not None) != (self.decision is DecisionRiskDecision.APPROVED):
            raise ValueError("only approved risk assessment may expose position sizing")
        if (
            self.position_sizing is not None
            and self.position_sizing.candidate_id != self.candidate_id
        ):
            raise ValueError("decision risk sizing belongs to another candidate")
        expected_id = f"decision-risk-{_checksum(self._identity_payload())[:16]}"
        if self.assessment_id != expected_id:
            raise ValueError("decision risk assessment ID is inconsistent")
        if self.assessment_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision risk assessment checksum is inconsistent")
        return self

    def _identity_payload(self) -> dict[str, object]:
        return {
            "candidate_id": self.candidate_id,
            "evaluation_id": self.evaluation_id,
            "policy_checksum": self.policy_checksum,
        }

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "candidate_checksum": self.candidate_checksum,
            "candidate_id": self.candidate_id,
            "checks": [item.model_dump(mode="json") for item in self.checks],
            "decision": self.decision.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "offline_only": True,
            "policy_checksum": self.policy_checksum,
            "position_sizing": (
                None
                if self.position_sizing is None
                else self.position_sizing.model_dump(mode="json")
            ),
            "rank": self.rank,
            "ranking_score": str(self.ranking_score),
            "schema_version": self.schema_version,
        }

    @classmethod
    def build(
        cls,
        *,
        entry: DecisionCandidateRankingEntry,
        policy: DecisionRiskPolicyV1,
        evaluated_at: datetime,
    ) -> Self:
        candidate = entry.candidate
        evaluated = _normalize_timestamp(evaluated_at)
        provisional_sizing = DecisionPositionSizing.build(candidate=candidate, policy=policy)
        reward_risk = (
            Decimal("0") if provisional_sizing is None else provisional_sizing.reward_risk_ratio
        )
        checks = (
            DecisionRiskCheck(
                name=DecisionRiskCheckName.CANDIDATE_FRESH,
                passed=candidate.constructed_at <= evaluated < candidate.valid_until,
                actual_value=evaluated.isoformat(),
                limit_value=f"<{candidate.valid_until.isoformat()}",
                explanation="Candidate must remain inside its immutable validity interval.",
            ),
            DecisionRiskCheck(
                name=DecisionRiskCheckName.RANKING_SCORE,
                passed=entry.total_score >= policy.minimum_ranking_score,
                actual_value=str(entry.total_score),
                limit_value=str(policy.minimum_ranking_score),
                explanation="Deterministic ranking score must meet the policy floor.",
            ),
            DecisionRiskCheck(
                name=DecisionRiskCheckName.REWARD_RISK,
                passed=reward_risk >= policy.minimum_reward_risk_ratio,
                actual_value=str(reward_risk),
                limit_value=str(policy.minimum_reward_risk_ratio),
                explanation="Candidate reward/risk must meet the conservative minimum.",
            ),
            DecisionRiskCheck(
                name=DecisionRiskCheckName.RISK_BUDGET,
                passed=(
                    provisional_sizing is not None
                    and provisional_sizing.maximum_loss <= provisional_sizing.risk_budget
                ),
                actual_value=(
                    "0" if provisional_sizing is None else str(provisional_sizing.maximum_loss)
                ),
                limit_value=(
                    "0" if provisional_sizing is None else str(provisional_sizing.risk_budget)
                ),
                explanation="Maximum simulated loss must stay inside the reference risk budget.",
            ),
            DecisionRiskCheck(
                name=DecisionRiskCheckName.NOTIONAL_CAP,
                passed=(
                    provisional_sizing is not None
                    and provisional_sizing.notional <= provisional_sizing.notional_cap
                ),
                actual_value=(
                    "0" if provisional_sizing is None else str(provisional_sizing.notional)
                ),
                limit_value=(
                    "0" if provisional_sizing is None else str(provisional_sizing.notional_cap)
                ),
                explanation="Simulated notional must stay inside the reference exposure cap.",
            ),
        )
        approved = all(item.passed for item in checks)
        identity = {
            "candidate_id": candidate.candidate_id,
            "evaluation_id": candidate.evaluation_id,
            "policy_checksum": policy.definition_checksum,
        }
        assessment_id = f"decision-risk-{_checksum(identity)[:16]}"
        unvalidated = cls.model_construct(
            assessment_id=assessment_id,
            evaluation_id=candidate.evaluation_id,
            candidate_id=candidate.candidate_id,
            candidate_checksum=candidate.candidate_checksum,
            rank=entry.rank,
            ranking_score=entry.total_score,
            decision=(DecisionRiskDecision.APPROVED if approved else DecisionRiskDecision.REJECTED),
            checks=checks,
            position_sizing=provisional_sizing if approved else None,
            evaluated_at=evaluated,
            policy_checksum=policy.definition_checksum,
            assessment_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["assessment_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class DecisionRiskGateRecord(BaseModel):
    """Immutable risk gate outcome and optional approved position sizing."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["decision-risk-gate-record-v1"] = "decision-risk-gate-record-v1"
    evaluation_id: str = Field(pattern=r"^decision-evaluation-[a-f0-9]{16}$")
    outcome: DecisionStageOutcome
    candidate_ranking_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: Literal["decision-risk-v1"]
    policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    assessment: DecisionRiskAssessment
    approved_candidate_id: str | None = Field(
        default=None,
        pattern=r"^decision-candidate-[a-f0-9]{16}$",
    )
    evaluated_at: datetime
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    record_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("evaluated_at")
    @classmethod
    def normalize_evaluated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.outcome.evaluation_id != self.evaluation_id:
            raise ValueError("decision risk outcome belongs to another evaluation")
        if self.outcome.stage is not DecisionStage.RISK_GATE:
            raise ValueError("decision risk outcome has an invalid stage")
        if self.outcome.evaluated_at != self.evaluated_at:
            raise ValueError("decision risk outcome time is inconsistent")
        if self.assessment.evaluation_id != self.evaluation_id:
            raise ValueError("decision risk assessment belongs to another evaluation")
        if self.assessment.policy_checksum != self.policy_checksum:
            raise ValueError("decision risk policy lineage is inconsistent")
        approved = self.assessment.decision is DecisionRiskDecision.APPROVED
        expected_disposition = (
            DecisionDisposition.ACCEPTED if approved else DecisionDisposition.REJECTED
        )
        expected_reasons = () if approved else (DecisionReasonCode.RISK_POLICY_REJECTED,)
        if (
            self.outcome.disposition is not expected_disposition
            or self.outcome.reason_codes != expected_reasons
        ):
            raise ValueError("decision risk stage outcome is inconsistent")
        expected_candidate = self.assessment.candidate_id if approved else None
        if self.approved_candidate_id != expected_candidate:
            raise ValueError("decision risk approved candidate is inconsistent")
        if self.record_checksum != _checksum(self._checksum_payload()):
            raise ValueError("decision risk gate record checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return {
            "approved_candidate_id": self.approved_candidate_id,
            "assessment": self.assessment.model_dump(mode="json"),
            "candidate_ranking_checksum": self.candidate_ranking_checksum,
            "evaluated_at": self.evaluated_at.isoformat(),
            "evaluation_id": self.evaluation_id,
            "external_order_submission_allowed": False,
            "offline_only": True,
            "outcome": self.outcome.model_dump(mode="json"),
            "policy_checksum": self.policy_checksum,
            "policy_version": self.policy_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def build(
        cls,
        *,
        ranking: DecisionCandidateRankingRecord,
        policy: DecisionRiskPolicyV1,
        evaluated_at: datetime,
    ) -> Self:
        evaluated = _normalize_timestamp(evaluated_at)
        if ranking.outcome.disposition is not DecisionDisposition.ACCEPTED:
            raise DecisionRiskIntegrityError("risk gate requires accepted candidate ranking")
        if not ranking.entries or ranking.top_candidate_id is None:
            raise DecisionRiskIntegrityError("accepted candidate ranking has no top candidate")
        top_entry = ranking.entries[0]
        if top_entry.candidate.candidate_id != ranking.top_candidate_id:
            raise DecisionRiskIntegrityError("risk gate top candidate lineage is inconsistent")
        assessment = DecisionRiskAssessment.build(
            entry=top_entry,
            policy=policy,
            evaluated_at=evaluated,
        )
        approved = assessment.decision is DecisionRiskDecision.APPROVED
        outcome = DecisionStageOutcome.build(
            evaluation_id=ranking.evaluation_id,
            stage=DecisionStage.RISK_GATE,
            disposition=(
                DecisionDisposition.ACCEPTED if approved else DecisionDisposition.REJECTED
            ),
            reason_codes=() if approved else (DecisionReasonCode.RISK_POLICY_REJECTED,),
            evaluated_at=evaluated,
        )
        unvalidated = cls.model_construct(
            evaluation_id=ranking.evaluation_id,
            outcome=outcome,
            candidate_ranking_checksum=ranking.record_checksum,
            policy_version=policy.policy_version,
            policy_checksum=policy.definition_checksum,
            assessment=assessment,
            approved_candidate_id=(assessment.candidate_id if approved else None),
            evaluated_at=evaluated,
            record_checksum="0" * 64,
        )
        payload = unvalidated.model_dump()
        payload["record_checksum"] = _checksum(unvalidated._checksum_payload())
        return cls.model_validate(payload)


class DecisionRiskIntegrityError(ValueError):
    """Persisted ranking or risk evidence no longer matches pinned lineage."""


def evaluate_decision_risk(
    *,
    ranking: DecisionCandidateRankingRecord,
    policy: DecisionRiskPolicyV1 | None = None,
) -> DecisionRiskGateRecord:
    """Apply deterministic offline risk checks to the top ranked candidate."""

    resolved_policy = policy or decision_risk_policy_v1()
    return DecisionRiskGateRecord.build(
        ranking=ranking,
        policy=resolved_policy,
        evaluated_at=ranking.ranked_at,
    )
