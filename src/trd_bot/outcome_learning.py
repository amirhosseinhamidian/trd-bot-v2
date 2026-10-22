import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.decision_intelligence import DecisionStage
from trd_bot.research.position_monitoring import CandidateExitReason

OUTCOME_LEARNING_POLICY_VERSION = "outcome-learning-review-policy-v1"
OUTCOME_LEARNING_SCHEMA_VERSION = "outcome-learning-review-v1"
_RATE_QUANTUM = Decimal("0.00000001")


class OutcomeLearningReadiness(StrEnum):
    INSUFFICIENT_DATA = "insufficient_data"
    OBSERVATIONAL = "observational"
    REVIEW_READY = "review_ready"


class OutcomeLearningSignalSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"


class OutcomeLearningSignalCode(StrEnum):
    ALERT_SAMPLE_INSUFFICIENT = "alert_sample_insufficient"
    CANDIDATE_SAMPLE_INSUFFICIENT = "candidate_sample_insufficient"
    DECISION_SAMPLE_INSUFFICIENT = "decision_sample_insufficient"
    POSITION_SAMPLE_INSUFFICIENT = "position_sample_insufficient"
    ALERT_FALSE_POSITIVE_ELEVATED = "alert_false_positive_elevated"
    ALERT_DRIFT_ELEVATED = "alert_drift_elevated"
    CANDIDATE_NO_POSITION_ELEVATED = "candidate_no_position_elevated"
    DECISION_NON_ACCEPTANCE_ELEVATED = "decision_non_acceptance_elevated"
    SIMULATED_LOSS_RATE_ELEVATED = "simulated_loss_rate_elevated"
    SIMULATED_NET_PNL_NEGATIVE = "simulated_net_pnl_negative"
    EVIDENCE_READY = "evidence_ready"


class OutcomeLearningReviewPolicy(BaseModel):
    """Versioned thresholds for human review, never automatic tuning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["outcome-learning-review-policy-v1"] = (
        "outcome-learning-review-policy-v1"
    )
    minimum_alert_outcomes: int = Field(ge=1)
    minimum_candidate_journals: int = Field(ge=1)
    minimum_decision_evaluations: int = Field(ge=1)
    minimum_stage_outcomes: int = Field(ge=1)
    minimum_closed_positions: int = Field(ge=1)
    false_positive_warning_rate: Decimal = Field(ge=0, le=1)
    drift_warning_rate: Decimal = Field(ge=0, le=1)
    no_position_warning_rate: Decimal = Field(ge=0, le=1)
    decision_non_acceptance_warning_rate: Decimal = Field(ge=0, le=1)
    simulated_loss_warning_rate: Decimal = Field(ge=0, le=1)
    automatic_policy_updates_allowed: Literal[False] = False
    production_ml_training_allowed: Literal[False] = False

    @property
    def definition_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


class DecisionStageReview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: DecisionStage
    accepted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    deferred: int = Field(ge=0)
    unavailable: int = Field(ge=0)

    @property
    def total(self) -> int:
        return self.accepted + self.rejected + self.deferred + self.unavailable

    @property
    def non_acceptance_rate(self) -> Decimal:
        if self.total == 0:
            return Decimal(0)
        return _rate(self.rejected + self.deferred + self.unavailable, self.total)


class ExitReasonReview(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: CandidateExitReason
    count: int = Field(ge=0)


class OutcomeLearningSnapshot(BaseModel):
    """Aggregate-only evidence; no account, credential, or order data is accepted."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alert_outcomes: int = Field(ge=0)
    alert_awaiting_outcome: int = Field(ge=0)
    alert_confirmed: int = Field(ge=0)
    alert_neutral: int = Field(ge=0)
    alert_false_positive: int = Field(ge=0)
    alert_drifted: int = Field(ge=0)
    average_alert_directional_return: Decimal
    candidate_journals: int = Field(ge=0)
    candidate_no_position: int = Field(ge=0)
    candidate_closed: int = Field(ge=0)
    exit_reasons: tuple[ExitReasonReview, ...]
    decision_evaluations: int = Field(ge=0)
    decision_stages: tuple[DecisionStageReview, ...]
    simulated_portfolios: int = Field(ge=0)
    paper_portfolios: int = Field(ge=0)
    shadow_portfolios: int = Field(ge=0)
    closed_positions: int = Field(ge=0)
    profitable_positions: int = Field(ge=0)
    losing_positions: int = Field(ge=0)
    breakeven_positions: int = Field(ge=0)
    net_realized_pnl: Decimal

    @model_validator(mode="after")
    def validate_aggregate_consistency(self) -> Self:
        if self.alert_outcomes != (
            self.alert_confirmed + self.alert_neutral + self.alert_false_positive
        ):
            raise ValueError("alert outcome aggregate is inconsistent")
        if self.alert_drifted > self.alert_outcomes:
            raise ValueError("alert drift count exceeds completed outcomes")
        if self.candidate_journals != self.candidate_no_position + self.candidate_closed:
            raise ValueError("candidate journal aggregate is inconsistent")
        if sum(item.count for item in self.exit_reasons) != self.candidate_closed:
            raise ValueError("candidate exit-reason aggregate is inconsistent")
        expected_reasons = tuple(CandidateExitReason)
        if tuple(item.reason for item in self.exit_reasons) != expected_reasons:
            raise ValueError("candidate exit reasons must be complete and canonical")
        expected_stages = tuple(DecisionStage)
        if tuple(item.stage for item in self.decision_stages) != expected_stages:
            raise ValueError("decision stages must be complete and canonical")
        if any(item.total > self.decision_evaluations for item in self.decision_stages):
            raise ValueError("decision stage outcomes exceed evaluation count")
        if self.simulated_portfolios != self.paper_portfolios + self.shadow_portfolios:
            raise ValueError("simulated portfolio aggregate is inconsistent")
        if self.closed_positions != (
            self.profitable_positions + self.losing_positions + self.breakeven_positions
        ):
            raise ValueError("simulated position aggregate is inconsistent")
        return self

    @property
    def alert_false_positive_rate(self) -> Decimal:
        return _rate(self.alert_false_positive, self.alert_outcomes)

    @property
    def alert_drift_rate(self) -> Decimal:
        return _rate(self.alert_drifted, self.alert_outcomes)

    @property
    def candidate_no_position_rate(self) -> Decimal:
        return _rate(self.candidate_no_position, self.candidate_journals)

    @property
    def simulated_loss_rate(self) -> Decimal:
        return _rate(self.losing_positions, self.closed_positions)


class OutcomeLearningSignal(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: OutcomeLearningSignalCode
    severity: OutcomeLearningSignalSeverity
    subject: str = Field(min_length=1, max_length=100)
    sample_count: int = Field(ge=0)
    observed_value: Decimal | None = None
    threshold: Decimal | None = None
    recommendation: str = Field(min_length=1, max_length=300)


class OutcomeLearningReview(BaseModel):
    """Commit-bound, aggregate, advisory review of offline outcome evidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["outcome-learning-review-v1"] = "outcome-learning-review-v1"
    environment_label: str = Field(min_length=1, max_length=64)
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    generated_at: datetime
    policy: OutcomeLearningReviewPolicy
    snapshot: OutcomeLearningSnapshot
    readiness: OutcomeLearningReadiness
    sample_gaps: tuple[str, ...]
    signals: tuple[OutcomeLearningSignal, ...]
    human_review_required: bool
    offline_only: Literal[True] = True
    external_order_submission_allowed: Literal[False] = False
    automatic_policy_updates_applied: Literal[False] = False
    production_ml_training_performed: Literal[False] = False

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("outcome learning review timestamp must include timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_derived_review(self) -> Self:
        readiness, gaps, signals = derive_outcome_learning_review(self.policy, self.snapshot)
        if self.readiness is not readiness or self.sample_gaps != gaps or self.signals != signals:
            raise ValueError("outcome learning review derivatives are inconsistent")
        expected_human_review = any(
            signal.severity is OutcomeLearningSignalSeverity.WARNING for signal in signals
        )
        if self.human_review_required is not expected_human_review:
            raise ValueError("outcome learning human-review flag is inconsistent")
        return self

    @property
    def report_checksum(self) -> str:
        return _checksum(self.model_dump(mode="json"))


def default_outcome_learning_policy() -> OutcomeLearningReviewPolicy:
    return OutcomeLearningReviewPolicy(
        minimum_alert_outcomes=30,
        minimum_candidate_journals=30,
        minimum_decision_evaluations=30,
        minimum_stage_outcomes=30,
        minimum_closed_positions=30,
        false_positive_warning_rate=Decimal("0.30"),
        drift_warning_rate=Decimal("0.30"),
        no_position_warning_rate=Decimal("0.70"),
        decision_non_acceptance_warning_rate=Decimal("0.50"),
        simulated_loss_warning_rate=Decimal("0.50"),
    )


def derive_outcome_learning_review(
    policy: OutcomeLearningReviewPolicy,
    snapshot: OutcomeLearningSnapshot,
) -> tuple[
    OutcomeLearningReadiness,
    tuple[str, ...],
    tuple[OutcomeLearningSignal, ...],
]:
    gaps: list[str] = []
    signals: list[OutcomeLearningSignal] = []
    sample_requirements = (
        (
            "alert_outcomes",
            snapshot.alert_outcomes,
            policy.minimum_alert_outcomes,
            OutcomeLearningSignalCode.ALERT_SAMPLE_INSUFFICIENT,
        ),
        (
            "candidate_journals",
            snapshot.candidate_journals,
            policy.minimum_candidate_journals,
            OutcomeLearningSignalCode.CANDIDATE_SAMPLE_INSUFFICIENT,
        ),
        (
            "decision_evaluations",
            snapshot.decision_evaluations,
            policy.minimum_decision_evaluations,
            OutcomeLearningSignalCode.DECISION_SAMPLE_INSUFFICIENT,
        ),
        (
            "closed_positions",
            snapshot.closed_positions,
            policy.minimum_closed_positions,
            OutcomeLearningSignalCode.POSITION_SAMPLE_INSUFFICIENT,
        ),
    )
    for subject, observed, minimum, code in sample_requirements:
        if observed < minimum:
            gaps.append(subject)
            signals.append(
                OutcomeLearningSignal(
                    code=code,
                    severity=OutcomeLearningSignalSeverity.INFO,
                    subject=subject,
                    sample_count=observed,
                    observed_value=Decimal(observed),
                    threshold=Decimal(minimum),
                    recommendation=(
                        "Collect more immutable offline outcomes before changing policy."
                    ),
                )
            )

    if snapshot.alert_outcomes >= policy.minimum_alert_outcomes:
        _append_rate_warning(
            signals,
            code=OutcomeLearningSignalCode.ALERT_FALSE_POSITIVE_ELEVATED,
            subject="alert_false_positive_rate",
            sample_count=snapshot.alert_outcomes,
            observed=snapshot.alert_false_positive_rate,
            threshold=policy.false_positive_warning_rate,
            recommendation="Review alert rules and evidence; do not auto-disable or retune them.",
        )
        _append_rate_warning(
            signals,
            code=OutcomeLearningSignalCode.ALERT_DRIFT_ELEVATED,
            subject="alert_drift_rate",
            sample_count=snapshot.alert_outcomes,
            observed=snapshot.alert_drift_rate,
            threshold=policy.drift_warning_rate,
            recommendation="Review regime assumptions and context freshness evidence.",
        )
    if snapshot.candidate_journals >= policy.minimum_candidate_journals:
        _append_rate_warning(
            signals,
            code=OutcomeLearningSignalCode.CANDIDATE_NO_POSITION_ELEVATED,
            subject="candidate_no_position_rate",
            sample_count=snapshot.candidate_journals,
            observed=snapshot.candidate_no_position_rate,
            threshold=policy.no_position_warning_rate,
            recommendation="Review ranking, risk, and fill reasons before changing thresholds.",
        )
    for stage in snapshot.decision_stages:
        if stage.total >= policy.minimum_stage_outcomes:
            _append_rate_warning(
                signals,
                code=OutcomeLearningSignalCode.DECISION_NON_ACCEPTANCE_ELEVATED,
                subject=stage.stage.value,
                sample_count=stage.total,
                observed=stage.non_acceptance_rate,
                threshold=policy.decision_non_acceptance_warning_rate,
                recommendation="Review stage reason codes and lineage; keep policy changes manual.",
            )
    if snapshot.closed_positions >= policy.minimum_closed_positions:
        _append_rate_warning(
            signals,
            code=OutcomeLearningSignalCode.SIMULATED_LOSS_RATE_ELEVATED,
            subject="simulated_loss_rate",
            sample_count=snapshot.closed_positions,
            observed=snapshot.simulated_loss_rate,
            threshold=policy.simulated_loss_warning_rate,
            recommendation="Review simulated exits, fees, and regime splits before reuse.",
        )
        if snapshot.net_realized_pnl < 0:
            signals.append(
                OutcomeLearningSignal(
                    code=OutcomeLearningSignalCode.SIMULATED_NET_PNL_NEGATIVE,
                    severity=OutcomeLearningSignalSeverity.WARNING,
                    subject="net_realized_pnl",
                    sample_count=snapshot.closed_positions,
                    observed_value=snapshot.net_realized_pnl,
                    threshold=Decimal(0),
                    recommendation=(
                        "Keep the reviewed policy out of promotion until manually assessed."
                    ),
                )
            )

    core_samples = (
        snapshot.alert_outcomes,
        snapshot.candidate_journals,
        snapshot.decision_evaluations,
        snapshot.closed_positions,
    )
    if not gaps:
        readiness = OutcomeLearningReadiness.REVIEW_READY
        signals.append(
            OutcomeLearningSignal(
                code=OutcomeLearningSignalCode.EVIDENCE_READY,
                severity=OutcomeLearningSignalSeverity.INFO,
                subject="cross_domain_review",
                sample_count=sum(core_samples),
                recommendation="Evidence is sufficient for human review, not automatic learning.",
            )
        )
    elif any(core_samples):
        readiness = OutcomeLearningReadiness.OBSERVATIONAL
    else:
        readiness = OutcomeLearningReadiness.INSUFFICIENT_DATA
    return readiness, tuple(gaps), tuple(signals)


def build_outcome_learning_review(
    *,
    environment_label: str,
    commit_sha: str,
    generated_at: datetime,
    snapshot: OutcomeLearningSnapshot,
    policy: OutcomeLearningReviewPolicy | None = None,
) -> OutcomeLearningReview:
    active_policy = policy or default_outcome_learning_policy()
    readiness, gaps, signals = derive_outcome_learning_review(active_policy, snapshot)
    return OutcomeLearningReview(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=generated_at,
        policy=active_policy,
        snapshot=snapshot,
        readiness=readiness,
        sample_gaps=gaps,
        signals=signals,
        human_review_required=any(
            signal.severity is OutcomeLearningSignalSeverity.WARNING for signal in signals
        ),
    )


def outcome_learning_review_to_dict(review: OutcomeLearningReview) -> dict[str, object]:
    payload = review.model_dump(mode="json")
    payload["policy_checksum"] = review.policy.definition_checksum
    payload["report_checksum"] = review.report_checksum
    return payload


def serialize_outcome_learning_review(review: OutcomeLearningReview) -> str:
    return json.dumps(
        outcome_learning_review_to_dict(review),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_outcome_learning_review(value: str | bytes) -> OutcomeLearningReview:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("outcome learning review is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("outcome learning review must be a JSON object")
    payload = dict(raw)
    policy_checksum = payload.pop("policy_checksum", None)
    report_checksum = payload.pop("report_checksum", None)
    review = OutcomeLearningReview.model_validate(payload)
    if policy_checksum is not None and policy_checksum != review.policy.definition_checksum:
        raise ValueError("outcome learning policy checksum is inconsistent")
    if report_checksum is not None and report_checksum != review.report_checksum:
        raise ValueError("outcome learning report checksum is inconsistent")
    return review


def _append_rate_warning(
    signals: list[OutcomeLearningSignal],
    *,
    code: OutcomeLearningSignalCode,
    subject: str,
    sample_count: int,
    observed: Decimal,
    threshold: Decimal,
    recommendation: str,
) -> None:
    if observed >= threshold:
        signals.append(
            OutcomeLearningSignal(
                code=code,
                severity=OutcomeLearningSignalSeverity.WARNING,
                subject=subject,
                sample_count=sample_count,
                observed_value=observed,
                threshold=threshold,
                recommendation=recommendation,
            )
        )


def _rate(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal(0)
    return (Decimal(numerator) / Decimal(denominator)).quantize(_RATE_QUANTUM)


def _checksum(value: object) -> str:
    serialized = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
