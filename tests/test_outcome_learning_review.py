import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError
from scripts.review_v0_3_outcomes import validate_review_database_url

from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.outcome_learning import SqlAlchemyOutcomeLearningReviewReader
from trd_bot.decision_intelligence import DecisionStage
from trd_bot.outcome_learning import (
    DecisionStageReview,
    ExitReasonReview,
    OutcomeLearningReadiness,
    OutcomeLearningSignalCode,
    OutcomeLearningSignalSeverity,
    OutcomeLearningSnapshot,
    build_outcome_learning_review,
    default_outcome_learning_policy,
    parse_outcome_learning_review,
    serialize_outcome_learning_review,
)
from trd_bot.research.position_monitoring import CandidateExitReason

_NOW = datetime(2026, 10, 21, 12, tzinfo=UTC)
_COMMIT_SHA = "a" * 40


def _exit_reasons(*, target: int = 0, portfolio_risk: int = 0) -> tuple[ExitReasonReview, ...]:
    counts = {
        CandidateExitReason.TARGET: target,
        CandidateExitReason.PORTFOLIO_RISK: portfolio_risk,
    }
    return tuple(
        ExitReasonReview(reason=reason, count=counts.get(reason, 0))
        for reason in CandidateExitReason
    )


def _decision_stages(
    *,
    accepted: int = 0,
    rejected: int = 0,
    deferred: int = 0,
    unavailable: int = 0,
) -> tuple[DecisionStageReview, ...]:
    return tuple(
        DecisionStageReview(
            stage=stage,
            accepted=accepted,
            rejected=rejected,
            deferred=deferred,
            unavailable=unavailable,
        )
        for stage in DecisionStage
    )


def _empty_snapshot() -> OutcomeLearningSnapshot:
    return OutcomeLearningSnapshot(
        alert_outcomes=0,
        alert_awaiting_outcome=0,
        alert_confirmed=0,
        alert_neutral=0,
        alert_false_positive=0,
        alert_drifted=0,
        average_alert_directional_return=Decimal(0),
        candidate_journals=0,
        candidate_no_position=0,
        candidate_closed=0,
        exit_reasons=_exit_reasons(),
        decision_evaluations=0,
        decision_stages=_decision_stages(),
        simulated_portfolios=0,
        paper_portfolios=0,
        shadow_portfolios=0,
        closed_positions=0,
        profitable_positions=0,
        losing_positions=0,
        breakeven_positions=0,
        net_realized_pnl=Decimal(0),
    )


def _warning_snapshot() -> OutcomeLearningSnapshot:
    return OutcomeLearningSnapshot(
        alert_outcomes=40,
        alert_awaiting_outcome=2,
        alert_confirmed=20,
        alert_neutral=5,
        alert_false_positive=15,
        alert_drifted=13,
        average_alert_directional_return=Decimal("-0.0125"),
        candidate_journals=40,
        candidate_no_position=30,
        candidate_closed=10,
        exit_reasons=_exit_reasons(target=4, portfolio_risk=6),
        decision_evaluations=40,
        decision_stages=_decision_stages(accepted=20, rejected=20),
        simulated_portfolios=4,
        paper_portfolios=2,
        shadow_portfolios=2,
        closed_positions=40,
        profitable_positions=15,
        losing_positions=25,
        breakeven_positions=0,
        net_realized_pnl=Decimal("-100.25"),
    )


def test_default_outcome_learning_policy_is_frozen_and_safe() -> None:
    policy = default_outcome_learning_policy()

    assert policy.minimum_alert_outcomes == 30
    assert policy.minimum_candidate_journals == 30
    assert policy.minimum_decision_evaluations == 30
    assert policy.minimum_stage_outcomes == 30
    assert policy.minimum_closed_positions == 30
    assert policy.false_positive_warning_rate == Decimal("0.30")
    assert policy.drift_warning_rate == Decimal("0.30")
    assert policy.no_position_warning_rate == Decimal("0.70")
    assert policy.decision_non_acceptance_warning_rate == Decimal("0.50")
    assert policy.simulated_loss_warning_rate == Decimal("0.50")
    assert policy.automatic_policy_updates_allowed is False
    assert policy.production_ml_training_allowed is False
    assert policy.definition_checksum == (
        "01a16992e6096a96ab9a2ae5fab0b7df8789cc5ecdb53365a8b1721428c9fd4c"
    )


def test_empty_evidence_is_explicitly_insufficient_and_round_trips() -> None:
    review = build_outcome_learning_review(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_empty_snapshot(),
    )

    assert review.readiness is OutcomeLearningReadiness.INSUFFICIENT_DATA
    assert review.sample_gaps == (
        "alert_outcomes",
        "candidate_journals",
        "decision_evaluations",
        "closed_positions",
    )
    assert all(signal.severity is OutcomeLearningSignalSeverity.INFO for signal in review.signals)
    assert review.human_review_required is False
    assert review.offline_only is True
    assert review.external_order_submission_allowed is False
    assert review.automatic_policy_updates_applied is False
    assert review.production_ml_training_performed is False
    assert parse_outcome_learning_review(serialize_outcome_learning_review(review)) == review


def test_sufficient_adverse_evidence_requires_human_review_only() -> None:
    review = build_outcome_learning_review(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_warning_snapshot(),
    )

    assert review.readiness is OutcomeLearningReadiness.REVIEW_READY
    assert review.sample_gaps == ()
    assert review.human_review_required is True
    codes = {signal.code for signal in review.signals}
    assert {
        OutcomeLearningSignalCode.ALERT_FALSE_POSITIVE_ELEVATED,
        OutcomeLearningSignalCode.ALERT_DRIFT_ELEVATED,
        OutcomeLearningSignalCode.CANDIDATE_NO_POSITION_ELEVATED,
        OutcomeLearningSignalCode.DECISION_NON_ACCEPTANCE_ELEVATED,
        OutcomeLearningSignalCode.SIMULATED_LOSS_RATE_ELEVATED,
        OutcomeLearningSignalCode.SIMULATED_NET_PNL_NEGATIVE,
        OutcomeLearningSignalCode.EVIDENCE_READY,
    } <= codes
    assert review.automatic_policy_updates_applied is False
    assert review.production_ml_training_performed is False


def test_serialized_review_rejects_derived_and_checksum_tampering() -> None:
    review = build_outcome_learning_review(
        environment_label="unit-test",
        commit_sha=_COMMIT_SHA,
        generated_at=_NOW,
        snapshot=_warning_snapshot(),
    )
    payload = json.loads(serialize_outcome_learning_review(review))

    payload["signals"] = []
    with pytest.raises(ValidationError, match="derivatives are inconsistent"):
        parse_outcome_learning_review(json.dumps(payload))

    payload = json.loads(serialize_outcome_learning_review(review))
    payload["report_checksum"] = "0" * 64
    with pytest.raises(ValueError, match="report checksum is inconsistent"):
        parse_outcome_learning_review(json.dumps(payload))


def test_snapshot_rejects_inconsistent_aggregates() -> None:
    payload = _warning_snapshot().model_dump()
    payload["alert_false_positive"] = 16

    with pytest.raises(ValidationError, match="alert outcome aggregate is inconsistent"):
        OutcomeLearningSnapshot.model_validate(payload)


def test_snapshot_rejects_non_finite_decimal_aggregates() -> None:
    payload = _empty_snapshot().model_dump()
    payload["net_realized_pnl"] = Decimal("NaN")

    with pytest.raises(ValidationError, match="finite number"):
        OutcomeLearningSnapshot.model_validate(payload)


def test_sqlalchemy_reader_handles_empty_database_without_row_payloads() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            review = SqlAlchemyOutcomeLearningReviewReader(session).read(
                environment_label="sqlite-query-test",
                commit_sha=_COMMIT_SHA,
                generated_at=_NOW,
            )
    finally:
        engine.dispose()

    assert review.snapshot == _empty_snapshot()
    assert review.readiness is OutcomeLearningReadiness.INSUFFICIENT_DATA


@pytest.mark.parametrize("database_url", ["", "  ", "sqlite:///local.sqlite3"])
def test_release_review_rejects_missing_or_non_postgresql_database(database_url: str) -> None:
    with pytest.raises(ValueError, match=r"database URL|requires PostgreSQL"):
        validate_review_database_url(database_url)


def test_release_review_accepts_postgresql_database() -> None:
    database_url = "postgresql+psycopg://postgres:postgres@localhost:5432/trd_bot_test"

    assert validate_review_database_url(database_url) == database_url
