from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    MarketContextFeatureSnapshotRow,
    MarketContextInputManifestRow,
    MarketContextInputWindowRow,
    MarketRegimeAssessmentRow,
    SqlAlchemyMarketContextStore,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAssessmentStatus,
    MarketContextEvidence,
    MarketContextFeatureRequirement,
    MarketContextFeatureSetDefinition,
    MarketContextFeatureSnapshot,
    MarketContextInputManifest,
    MarketContextWindowReference,
    MarketRegimeAssessment,
    MarketTrendRegime,
    MarketVolatilityRegime,
    build_market_regime_assessment_id,
)
from trd_bot.market_data import MarketDataEvent, MarketDataWatermark, MarketDataWindowSnapshot

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 16, 12, tzinfo=UTC)
CALCULATED_AT = datetime(2026, 10, 16, 12, 5, tzinfo=UTC)


def finalized_input(
    timeframe: Timeframe,
    window_start: datetime,
) -> tuple[MarketDataWindowSnapshot, MarketContextWindowReference]:
    candle = OHLCVCandle(
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        open_time=window_start,
        close_time=window_start + timeframe.duration,
        received_at=window_start + timeframe.duration + timedelta(seconds=10),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1250"),
    )
    event = MarketDataEvent.from_candle(candle)
    provisional = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=candle.received_at,
    )
    watermark = MarketDataWatermark.build(
        source=SOURCE,
        pair=PAIR,
        timeframe=timeframe,
        high_water_event_time=candle.close_time,
        allowed_lateness_seconds=0,
        calculated_at=candle.received_at,
    )
    finalized = provisional.finalize(
        watermark,
        finalized_at=candle.received_at + timedelta(seconds=1),
    )
    return finalized, MarketContextWindowReference.from_snapshot(finalized)


def context_records() -> tuple[
    tuple[MarketDataWindowSnapshot, ...],
    MarketContextInputManifest,
    MarketContextFeatureSnapshot,
    MarketRegimeAssessment,
]:
    inputs = (
        finalized_input(Timeframe.HOUR_1, datetime(2026, 10, 16, 11, tzinfo=UTC)),
        finalized_input(Timeframe.HOURS_4, datetime(2026, 10, 16, 8, tzinfo=UTC)),
        finalized_input(Timeframe.DAY_1, datetime(2026, 10, 15, tzinfo=UTC)),
    )
    windows = tuple(item[0] for item in inputs)
    manifest = MarketContextInputManifest.build(
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        windows=tuple(item[1] for item in inputs),
        created_at=CALCULATED_AT,
    )
    definition = MarketContextFeatureSetDefinition.build(
        feature_set_version="market-context-features-v1",
        requirements=(
            MarketContextFeatureRequirement(
                feature_key="trend_slope_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=1,
                calculation_version="trend-slope-v1",
            ),
        ),
    )
    evidence = MarketContextEvidence(
        feature_key="trend_slope_1h",
        timeframe=Timeframe.HOUR_1,
        value=Decimal("0.013"),
        calculation_version="trend-slope-v1",
        window_reference_checksums=(manifest.windows[0].reference_checksum,),
    )
    feature_snapshot = MarketContextFeatureSnapshot.build(
        manifest=manifest,
        feature_set=definition,
        features=(evidence,),
        calculated_at=CALCULATED_AT,
    )
    assessed_at = CALCULATED_AT + timedelta(seconds=1)
    assessment = MarketRegimeAssessment(
        assessment_id=build_market_regime_assessment_id(
            source=SOURCE,
            pair=PAIR,
            as_of=AS_OF,
            input_checksum=manifest.input_checksum,
            feature_set_version=definition.feature_set_version,
            algorithm_version="market-regime-v1",
        ),
        source=SOURCE,
        pair=PAIR,
        as_of=AS_OF,
        input_manifest_id=manifest.manifest_id,
        input_checksum=manifest.input_checksum,
        feature_set_version=definition.feature_set_version,
        feature_set_checksum=definition.definition_checksum,
        feature_snapshot_id=feature_snapshot.snapshot_id,
        feature_snapshot_checksum=feature_snapshot.snapshot_checksum,
        algorithm_version="market-regime-v1",
        status=MarketContextAssessmentStatus.READY,
        trend=MarketTrendRegime.TRENDING_UP,
        volatility=MarketVolatilityRegime.NORMAL,
        confidence=Decimal("0.82"),
        evidence=feature_snapshot.features,
        assessed_at=assessed_at,
        expires_at=assessed_at + timedelta(hours=1),
    )
    return windows, manifest, feature_snapshot, assessment


def test_store_round_trips_immutable_context_lineage() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest, feature_snapshot, assessment = context_records()

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for window in windows:
                window_store.stage_window_version(window)
            store = SqlAlchemyMarketContextStore(session)
            assert store.stage_input_manifest(manifest)[1] is True
            assert store.stage_feature_snapshot(feature_snapshot)[1] is True
            assert store.stage_assessment(assessment)[1] is True

        with factory() as session:
            store = SqlAlchemyMarketContextStore(session)
            assert store.get_input_manifest(manifest.manifest_id) == manifest
            assert store.get_input_manifest_by_checksum(manifest.input_checksum) == manifest
            assert store.get_feature_snapshot(feature_snapshot.snapshot_id) == feature_snapshot
            assert store.get_assessment(assessment.assessment_id) == assessment
            assert store.get_latest_assessment(source=SOURCE, pair=PAIR) == assessment
            assert store.stage_input_manifest(manifest)[1] is False
            assert store.stage_feature_snapshot(feature_snapshot)[1] is False
            assert store.stage_assessment(assessment)[1] is False

            assert (
                session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 1
            )
            assert (
                session.scalar(select(func.count()).select_from(MarketContextInputWindowRow)) == 3
            )
            assert (
                session.scalar(select(func.count()).select_from(MarketContextFeatureSnapshotRow))
                == 1
            )
            assert session.scalar(select(func.count()).select_from(MarketRegimeAssessmentRow)) == 1
    finally:
        engine.dispose()


def test_manifest_requires_every_referenced_finalized_window_to_exist() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    _, manifest, _, _ = context_records()

    try:
        with factory() as session:
            with pytest.raises(ValueError, match="window version does not exist"):
                SqlAlchemyMarketContextStore(session).stage_input_manifest(manifest)
            assert session.get(MarketContextInputManifestRow, manifest.manifest_id) is None
    finally:
        engine.dispose()


def test_feature_snapshot_requires_its_persisted_manifest() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    _, _, feature_snapshot, _ = context_records()

    try:
        with (
            factory() as session,
            pytest.raises(ValueError, match="input manifest does not exist"),
        ):
            SqlAlchemyMarketContextStore(session).stage_feature_snapshot(feature_snapshot)
    finally:
        engine.dispose()


def test_ready_assessment_requires_matching_persisted_feature_lineage() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest, _, assessment = context_records()

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for window in windows:
                window_store.stage_window_version(window)
            SqlAlchemyMarketContextStore(session).stage_input_manifest(manifest)

        with (
            factory() as session,
            pytest.raises(ValueError, match="feature snapshot does not exist"),
        ):
            SqlAlchemyMarketContextStore(session).stage_assessment(assessment)
    finally:
        engine.dispose()


def test_caller_transaction_can_roll_back_the_whole_context_bundle() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest, feature_snapshot, assessment = context_records()

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for window in windows:
                window_store.stage_window_version(window)

        with (
            pytest.raises(RuntimeError, match="simulated failure"),
            factory.begin() as session,
        ):
            store = SqlAlchemyMarketContextStore(session)
            store.stage_input_manifest(manifest)
            store.stage_feature_snapshot(feature_snapshot)
            store.stage_assessment(assessment)
            raise RuntimeError("simulated failure")

        with factory() as session:
            assert session.get(MarketContextInputManifestRow, manifest.manifest_id) is None
            assert (
                session.get(MarketContextFeatureSnapshotRow, feature_snapshot.snapshot_id) is None
            )
            assert session.get(MarketRegimeAssessmentRow, assessment.assessment_id) is None
    finally:
        engine.dispose()


def test_assessment_identity_is_immutable_after_persistence() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    windows, manifest, feature_snapshot, assessment = context_records()

    try:
        with factory.begin() as session:
            window_store = SqlAlchemyMarketDataEventStore(session)
            for window in windows:
                window_store.stage_window_version(window)
            store = SqlAlchemyMarketContextStore(session)
            store.stage_input_manifest(manifest)
            store.stage_feature_snapshot(feature_snapshot)
            store.stage_assessment(assessment)

        changed = assessment.model_copy(update={"confidence": Decimal("0.90")})
        with (
            factory() as session,
            pytest.raises(ValueError, match="ID exists with different content"),
        ):
            SqlAlchemyMarketContextStore(session).stage_assessment(changed)
    finally:
        engine.dispose()
