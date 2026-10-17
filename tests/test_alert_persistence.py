from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from trd_bot.alerts import (
    AlertDraft,
    AlertEvaluationRecord,
    AlertRuleDefinition,
    AlertRuleState,
    AlertSeverity,
    AlertSuppressionReason,
    MarketContextAlertCondition,
    MarketContextAlertSourceReference,
)
from trd_bot.db import (
    AlertEvaluationRow,
    AlertRow,
    AlertRuleDefinitionRow,
    DatabaseBase,
    MarketRegimeAssessmentRow,
    SqlAlchemyAlertStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvidence,
    MarketContextProductView,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
AS_OF = datetime(2026, 10, 17, 12, tzinfo=UTC)
EVALUATED_AT = AS_OF + timedelta(minutes=20)


def ready_assessment() -> MarketRegimeAssessment:
    input_checksum = "a" * 64
    return MarketRegimeAssessment(
        assessment_id=build_market_regime_assessment_id(
            source="kraken-public",
            pair=PAIR,
            as_of=AS_OF,
            input_checksum=input_checksum,
            feature_set_version="market-context-features-v1",
            algorithm_version="market-regime-v1",
        ),
        source="kraken-public",
        pair=PAIR,
        as_of=AS_OF,
        input_manifest_id=f"market-context-input-{input_checksum[:16]}",
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        feature_set_checksum="b" * 64,
        feature_snapshot_id="market-context-features-dddddddddddddddd",
        feature_snapshot_checksum="d" * 64,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.HIGH,
        confidence=Decimal("0.82"),
        evidence=(
            MarketContextEvidence(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                value=Decimal("0.013"),
                calculation_version="trend-slope-v1",
                window_reference_checksums=("e" * 64,),
            ),
        ),
        assessed_at=AS_OF + timedelta(minutes=1),
        expires_at=AS_OF + timedelta(hours=1, minutes=1),
    )


def alert_rule(*, version: int = 1) -> AlertRuleDefinition:
    return AlertRuleDefinition.build(
        rule_key="high-volatility-uptrend",
        rule_version=version,
        name="High-volatility uptrend",
        description="Notify when an uptrend has high volatility and enough confidence.",
        state=AlertRuleState.ENABLED,
        severity=AlertSeverity.WARNING,
        condition=MarketContextAlertCondition(
            trends=(MarketTrendRegime.TRENDING_UP,),
            volatilities=(MarketVolatilityRegime.HIGH,),
            minimum_confidence=Decimal("0.75"),
        ),
        expires_after_seconds=1800,
        deduplication_window_seconds=3600,
        cooldown_seconds=7200,
        created_at=AS_OF + timedelta(minutes=2),
    )


def source_reference(
    assessment: MarketRegimeAssessment,
    *,
    evaluated_at: datetime = EVALUATED_AT,
) -> MarketContextAlertSourceReference:
    return MarketContextAlertSourceReference.from_market_context_view(
        MarketContextProductView.from_assessment(
            assessment,
            evaluated_at=evaluated_at,
        )
    )


def alert_draft(
    rule: AlertRuleDefinition,
    source: MarketContextAlertSourceReference,
) -> AlertDraft:
    return AlertDraft.build(
        rule=rule,
        source=source,
        title="Volatility regime changed",
        message="BTC/USDT is trending up with high volatility.",
        created_at=source.evaluated_at,
    )


def seed_assessment(session: Session, assessment: MarketRegimeAssessment) -> None:
    session.add(
        MarketRegimeAssessmentRow(
            assessment_id=assessment.assessment_id,
            schema_version=assessment.schema_version,
            manifest_id=assessment.input_manifest_id,
            feature_snapshot_id=assessment.feature_snapshot_id,
            source=assessment.source,
            base_asset=assessment.pair.base_asset,
            quote_asset=assessment.pair.quote_asset,
            market_type=assessment.pair.market_type.value,
            as_of=assessment.as_of,
            input_checksum=assessment.input_checksum,
            feature_set_version=assessment.feature_set_version,
            feature_set_checksum=assessment.feature_set_checksum,
            feature_snapshot_checksum=assessment.feature_snapshot_checksum,
            algorithm_version=assessment.algorithm_version,
            status=assessment.status.value,
            trend=assessment.trend.value,
            volatility=assessment.volatility.value,
            confidence=assessment.confidence,
            evidence_count=len(assessment.evidence),
            issue_count=len(assessment.issue_codes),
            payload_json=assessment.model_dump_json(),
            assessed_at=assessment.assessed_at,
            expires_at=assessment.expires_at,
        )
    )


def test_rule_versions_are_idempotent_and_cannot_skip_persisted_lineage() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    first = alert_rule()
    second = alert_rule(version=2)
    skipped = alert_rule(version=3)

    try:
        with factory.begin() as session:
            store = SqlAlchemyAlertStore(session)
            assert store.stage_rule_definition(first) == (first, True)
            assert store.stage_rule_definition(first) == (first, False)
            with pytest.raises(ValueError, match="immediate predecessor"):
                store.stage_rule_definition(skipped)
            assert store.stage_rule_definition(second) == (second, True)

        with factory() as session:
            store = SqlAlchemyAlertStore(session)
            assert store.get_rule_definition(first.rule_id, 1) == first
            assert store.get_latest_rule_definition(first.rule_id) == second
            assert session.scalar(select(func.count()).select_from(AlertRuleDefinitionRow)) == 2
    finally:
        engine.dispose()


def test_published_evaluation_and_alert_are_durable_and_idempotent() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    assessment = ready_assessment()
    rule = alert_rule()
    source = source_reference(assessment)
    draft = alert_draft(rule, source)
    evaluation = AlertEvaluationRecord.published(draft)

    try:
        with factory.begin() as session:
            seed_assessment(session, assessment)
            store = SqlAlchemyAlertStore(session)
            store.stage_rule_definition(rule)
            assert store.stage_evaluation(evaluation, draft=draft) == (evaluation, True)
            assert store.stage_evaluation(evaluation, draft=draft) == (evaluation, False)

        with factory() as session:
            store = SqlAlchemyAlertStore(session)
            assert store.get_evaluation(evaluation.evaluation_id) == evaluation
            assert store.get_alert(draft.alert_id) == draft
            assert store.get_alert_by_deduplication_key(draft.deduplication_key) == draft
            assert session.scalar(select(func.count()).select_from(AlertEvaluationRow)) == 1
            assert session.scalar(select(func.count()).select_from(AlertRow)) == 1
    finally:
        engine.dispose()


def test_suppressed_evaluation_is_persisted_without_an_alert() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    assessment = ready_assessment()
    rule = alert_rule()
    source = source_reference(
        assessment,
        evaluated_at=assessment.expires_at + timedelta(minutes=1),
    )
    evaluation = AlertEvaluationRecord.suppressed(
        rule=rule,
        source=source,
        reasons=(
            AlertSuppressionReason.SOURCE_EXPIRED,
            AlertSuppressionReason.SOURCE_NOT_CONSUMABLE,
        ),
    )

    try:
        with factory.begin() as session:
            seed_assessment(session, assessment)
            store = SqlAlchemyAlertStore(session)
            store.stage_rule_definition(rule)
            assert store.stage_evaluation(evaluation) == (evaluation, True)

        with factory() as session:
            store = SqlAlchemyAlertStore(session)
            assert store.get_evaluation(evaluation.evaluation_id) == evaluation
            assert session.scalar(select(func.count()).select_from(AlertRow)) == 0
    finally:
        engine.dispose()


def test_evaluation_requires_exact_persisted_source_lineage() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    assessment = ready_assessment()
    rule = alert_rule()
    source = source_reference(assessment)
    draft = alert_draft(rule, source)
    evaluation = AlertEvaluationRecord.published(draft)

    try:
        with factory.begin() as session:
            SqlAlchemyAlertStore(session).stage_rule_definition(rule)

        with factory() as session:
            with pytest.raises(ValueError, match="source assessment does not exist"):
                SqlAlchemyAlertStore(session).stage_evaluation(evaluation, draft=draft)
            assert session.get(AlertEvaluationRow, evaluation.evaluation_id) is None
            assert session.get(AlertRow, draft.alert_id) is None
    finally:
        engine.dispose()


def test_caller_transaction_rolls_back_evaluation_and_alert_together() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    assessment = ready_assessment()
    rule = alert_rule()
    source = source_reference(assessment)
    draft = alert_draft(rule, source)
    evaluation = AlertEvaluationRecord.published(draft)

    try:
        with factory.begin() as session:
            seed_assessment(session, assessment)
            SqlAlchemyAlertStore(session).stage_rule_definition(rule)

        with (
            pytest.raises(RuntimeError, match="simulated failure"),
            factory.begin() as session,
        ):
            SqlAlchemyAlertStore(session).stage_evaluation(evaluation, draft=draft)
            raise RuntimeError("simulated failure")

        with factory() as session:
            assert session.get(AlertEvaluationRow, evaluation.evaluation_id) is None
            assert session.get(AlertRow, draft.alert_id) is None
    finally:
        engine.dispose()


def test_published_evaluation_rejects_missing_or_conflicting_draft() -> None:
    rule = alert_rule()
    source = source_reference(ready_assessment())
    draft = alert_draft(rule, source)
    evaluation = AlertEvaluationRecord.published(draft)

    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory() as session:
            store = SqlAlchemyAlertStore(session)
            with pytest.raises(ValueError, match="requires its draft"):
                store.stage_evaluation(evaluation)

            conflicting = AlertDraft.build(
                rule=rule,
                source=source,
                title="Conflicting title",
                message=draft.message,
                created_at=source.evaluated_at,
            )
            with pytest.raises(ValueError, match="does not match its draft"):
                store.stage_evaluation(evaluation, draft=conflicting)
    finally:
        engine.dispose()
