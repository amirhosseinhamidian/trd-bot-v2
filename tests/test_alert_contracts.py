from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.alerts import (
    AlertDraft,
    AlertRuleDefinition,
    AlertRuleState,
    AlertSeverity,
    AlertSuppressionReason,
    MarketContextAlertCondition,
    MarketContextAlertSourceReference,
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


def ready_assessment(*, expires_at: datetime | None = None) -> MarketRegimeAssessment:
    input_checksum = "a" * 64
    assessment_id = build_market_regime_assessment_id(
        source="kraken-public",
        pair=PAIR,
        as_of=AS_OF,
        input_checksum=input_checksum,
        feature_set_version="market-context-features-v1",
        algorithm_version="market-regime-v1",
    )
    return MarketRegimeAssessment(
        assessment_id=assessment_id,
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
        expires_at=expires_at or AS_OF + timedelta(hours=1, minutes=1),
    )


def source_reference(
    *,
    evaluated_at: datetime = AS_OF + timedelta(minutes=20),
    expires_at: datetime | None = None,
) -> MarketContextAlertSourceReference:
    view = MarketContextProductView.from_assessment(
        ready_assessment(expires_at=expires_at),
        evaluated_at=evaluated_at,
    )
    return MarketContextAlertSourceReference.from_market_context_view(view)


def condition(*, minimum_confidence: str = "0.75") -> MarketContextAlertCondition:
    return MarketContextAlertCondition(
        trends=(MarketTrendRegime.TRENDING_UP,),
        volatilities=(MarketVolatilityRegime.HIGH,),
        minimum_confidence=Decimal(minimum_confidence),
    )


def rule(
    *,
    version: int = 1,
    state: AlertRuleState = AlertRuleState.ENABLED,
    minimum_confidence: str = "0.75",
) -> AlertRuleDefinition:
    return AlertRuleDefinition.build(
        rule_key="high-volatility-uptrend",
        rule_version=version,
        name="High-volatility uptrend",
        description="Notify when an uptrend has high volatility and enough confidence.",
        state=state,
        severity=AlertSeverity.WARNING,
        condition=condition(minimum_confidence=minimum_confidence),
        expires_after_seconds=1800,
        deduplication_window_seconds=3600,
        cooldown_seconds=7200,
        created_at=AS_OF + timedelta(minutes=2),
    )


def test_alert_rule_is_versioned_deterministic_and_immutable() -> None:
    first = rule()
    repeated = rule()
    second = rule(version=2, minimum_confidence="0.80")

    assert first == repeated
    assert first.rule_id == second.rule_id
    assert first.rule_version == 1
    assert first.supersedes_version is None
    assert second.rule_version == 2
    assert second.supersedes_version == 1
    assert first.definition_checksum != second.definition_checksum

    with pytest.raises(ValidationError, match="frozen"):
        first.severity = AlertSeverity.CRITICAL


def test_alert_rule_rejects_skipped_version_lineage_and_checksum_tampering() -> None:
    definition = rule(version=2)

    payload = definition.model_dump()
    payload["supersedes_version"] = None
    with pytest.raises(ValidationError, match="immediate predecessor"):
        AlertRuleDefinition.model_validate(payload)

    payload = definition.model_dump()
    payload["severity"] = AlertSeverity.CRITICAL
    with pytest.raises(ValidationError, match="checksum is inconsistent"):
        AlertRuleDefinition.model_validate(payload)


def test_market_context_condition_is_typed_ordered_and_determinate() -> None:
    with pytest.raises(ValidationError, match="deterministic order"):
        MarketContextAlertCondition(
            trends=(MarketTrendRegime.TRENDING_UP, MarketTrendRegime.RANGING),
            volatilities=(MarketVolatilityRegime.HIGH,),
            minimum_confidence=Decimal("0.75"),
        )

    with pytest.raises(ValidationError, match="undetermined trend"):
        MarketContextAlertCondition(
            trends=(MarketTrendRegime.UNDETERMINED,),
            volatilities=(MarketVolatilityRegime.HIGH,),
            minimum_confidence=Decimal("0.75"),
        )


def test_market_context_source_reference_preserves_consumption_and_lineage() -> None:
    source = source_reference()

    assert source.consumable is True
    assert source.unavailable_reasons == ()
    assert source.source_event_id.startswith("market-regime-")

    payload = source.model_dump()
    payload["confidence"] = Decimal("0.91")
    with pytest.raises(ValidationError, match="reference checksum is inconsistent"):
        MarketContextAlertSourceReference.model_validate(payload)


def test_alert_draft_is_deterministic_and_bounded_by_source_expiry() -> None:
    definition = rule()
    source = source_reference(expires_at=AS_OF + timedelta(minutes=30))
    created_at = AS_OF + timedelta(minutes=20)

    draft = AlertDraft.build(
        rule=definition,
        source=source,
        title="Volatility regime changed",
        message="BTC/USDT is trending up with high volatility.",
        created_at=created_at,
    )
    repeated = AlertDraft.build(
        rule=definition,
        source=source,
        title="Volatility regime changed",
        message="BTC/USDT is trending up with high volatility.",
        created_at=created_at,
    )

    assert draft.alert_id == repeated.alert_id
    assert draft.deduplication_key == repeated.deduplication_key
    assert draft.expires_at == source.expires_at
    assert draft.rule.definition_checksum == definition.definition_checksum
    assert draft.source.reference_checksum == source.reference_checksum
    assert AlertDraft.model_validate_json(draft.model_dump_json()) == draft

    payload = draft.model_dump()
    payload["message"] = "Tampered alert content."
    with pytest.raises(ValidationError, match="draft checksum is inconsistent"):
        AlertDraft.model_validate(payload)


def test_disabled_rule_cannot_create_a_publishable_alert() -> None:
    with pytest.raises(ValueError, match=AlertSuppressionReason.RULE_DISABLED.value):
        AlertDraft.build(
            rule=rule(state=AlertRuleState.DISABLED),
            source=source_reference(),
            title="Disabled",
            message="This alert must not be published.",
            created_at=AS_OF + timedelta(minutes=20),
        )


def test_stale_context_cannot_create_a_publishable_alert() -> None:
    stale_source = source_reference(
        evaluated_at=AS_OF + timedelta(hours=1, minutes=2),
        expires_at=AS_OF + timedelta(hours=1, minutes=1),
    )

    assert stale_source.consumable is False
    with pytest.raises(
        ValueError,
        match=AlertSuppressionReason.SOURCE_NOT_CONSUMABLE.value,
    ):
        AlertDraft.build(
            rule=rule(),
            source=stale_source,
            title="Stale",
            message="This alert must not be published.",
            created_at=AS_OF + timedelta(hours=1, minutes=2),
        )


def test_non_matching_condition_cannot_create_a_publishable_alert() -> None:
    with pytest.raises(
        ValueError,
        match=AlertSuppressionReason.CONDITION_NOT_MATCHED.value,
    ):
        AlertDraft.build(
            rule=rule(minimum_confidence="0.90"),
            source=source_reference(),
            title="Low confidence",
            message="This alert must not be published.",
            created_at=AS_OF + timedelta(minutes=20),
        )


def test_alert_contracts_forbid_unknown_fields() -> None:
    payload = rule().model_dump()
    payload["exchange_api_key"] = "forbidden"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        AlertRuleDefinition.model_validate(payload)
