from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from trd_bot.db import (
    DatabaseBase,
    MarketContextInputManifestRow,
    SqlAlchemyMarketContextAssembler,
    SqlAlchemyMarketDataEventStore,
    create_database_engine,
    create_session_factory,
)
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context import (
    MarketContextAlignmentIssueCode,
    MarketContextAlignmentResult,
    MarketContextAlignmentStatus,
    MarketContextFeatureRequirement,
    MarketContextFeatureSetDefinition,
    align_market_context_windows,
    required_market_context_window_counts,
)
from trd_bot.market_data import MarketDataEvent, MarketDataWindowSnapshot, MarketDataWindowState

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
SOURCE = "kraken-public"
AS_OF = datetime(2026, 10, 16, 12, tzinfo=UTC)
ALIGNED_AT = AS_OF + timedelta(minutes=5)


def feature_set() -> MarketContextFeatureSetDefinition:
    return MarketContextFeatureSetDefinition.build(
        feature_set_version="market-context-features-v1",
        requirements=(
            MarketContextFeatureRequirement(
                feature_key="momentum_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=2,
                calculation_version="momentum-v1",
            ),
            MarketContextFeatureRequirement(
                feature_key="trend_1h",
                timeframe=Timeframe.HOUR_1,
                lookback_windows=3,
                calculation_version="trend-v1",
            ),
            MarketContextFeatureRequirement(
                feature_key="trend_4h",
                timeframe=Timeframe.HOURS_4,
                lookback_windows=2,
                calculation_version="trend-v1",
            ),
            MarketContextFeatureRequirement(
                feature_key="volatility_1d",
                timeframe=Timeframe.DAY_1,
                lookback_windows=1,
                calculation_version="volatility-v1",
            ),
        ),
    )


def window(
    timeframe: Timeframe,
    window_start: datetime,
    *,
    version: int = 2,
    close_price: str = "105",
    source: str = SOURCE,
    pair: TradingPair = PAIR,
    finalized: bool = True,
) -> MarketDataWindowSnapshot:
    close_time = window_start + timeframe.duration
    candle = OHLCVCandle(
        source=source,
        pair=pair,
        timeframe=timeframe,
        open_time=window_start,
        close_time=close_time,
        received_at=close_time + timedelta(minutes=1),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal(close_price),
        volume=Decimal("1250"),
    )
    event = MarketDataEvent.from_candle(candle)
    state = MarketDataWindowState.FINALIZED if finalized else MarketDataWindowState.PROVISIONAL
    return MarketDataWindowSnapshot(
        window_id=event.window_id,
        version=version,
        state=state,
        source=source,
        pair=pair,
        timeframe=timeframe,
        window_start=window_start,
        window_end=close_time,
        event_id=event.event_id,
        payload_checksum=event.payload_checksum,
        candle=candle,
        created_at=close_time + timedelta(minutes=1),
        finalized_at=close_time + timedelta(minutes=2) if finalized else None,
    )


def complete_windows() -> tuple[MarketDataWindowSnapshot, ...]:
    return (
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 9, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 10, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 11, tzinfo=UTC)),
        window(Timeframe.HOURS_4, datetime(2026, 10, 16, 4, tzinfo=UTC)),
        window(Timeframe.HOURS_4, datetime(2026, 10, 16, 8, tzinfo=UTC)),
        window(Timeframe.DAY_1, datetime(2026, 10, 15, tzinfo=UTC)),
    )


def align(
    windows: tuple[MarketDataWindowSnapshot, ...],
    *,
    as_of: datetime = AS_OF,
) -> MarketContextAlignmentResult:
    return align_market_context_windows(
        source=SOURCE,
        pair=PAIR,
        as_of=as_of,
        windows=windows,
        feature_set=feature_set(),
        aligned_at=ALIGNED_AT,
    )


def test_required_counts_use_largest_lookback_and_cover_every_timeframe() -> None:
    assert required_market_context_window_counts(feature_set()) == {
        Timeframe.HOUR_1: 3,
        Timeframe.HOURS_4: 2,
        Timeframe.DAY_1: 1,
    }


def test_ready_alignment_builds_ordered_manifest_from_latest_finalized_versions() -> None:
    original = complete_windows()
    revised_latest = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 11, tzinfo=UTC),
        version=3,
        close_price="107",
    )
    result = align((*reversed(original), revised_latest))

    assert result.status is MarketContextAlignmentStatus.READY
    assert result.issue_codes == ()
    assert result.manifest is not None
    assert tuple(item.timeframe for item in result.manifest.windows) == (
        Timeframe.HOUR_1,
        Timeframe.HOUR_1,
        Timeframe.HOUR_1,
        Timeframe.HOURS_4,
        Timeframe.HOURS_4,
        Timeframe.DAY_1,
    )
    assert result.manifest.windows[2].version == 3
    assert result.manifest.windows[2].payload_checksum == revised_latest.payload_checksum
    assert all(
        coverage.status is MarketContextAlignmentStatus.READY for coverage in result.coverages
    )


def test_alignment_reports_stale_when_contiguous_history_ends_before_boundary() -> None:
    stale_hourly = (
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 8, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 9, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 10, tzinfo=UTC)),
    )
    higher_timeframes = complete_windows()[3:]

    result = align((*stale_hourly, *higher_timeframes))

    assert result.status is MarketContextAlignmentStatus.STALE
    assert result.manifest is None
    assert result.issue_codes == (MarketContextAlignmentIssueCode.STALE_LATEST_WINDOW,)
    hourly = result.coverages[0]
    assert hourly.status is MarketContextAlignmentStatus.STALE
    assert hourly.latest_observed_window_end == datetime(2026, 10, 16, 11, tzinfo=UTC)
    assert hourly.expected_latest_window_end == AS_OF


def test_alignment_reports_insufficient_history_and_never_builds_manifest() -> None:
    result = align(complete_windows()[1:])

    assert result.status is MarketContextAlignmentStatus.INSUFFICIENT_DATA
    assert result.manifest is None
    assert MarketContextAlignmentIssueCode.INSUFFICIENT_HISTORY in result.issue_codes
    assert result.coverages[0].available_windows == 2


def test_alignment_reports_internal_gap_as_insufficient_data() -> None:
    gapped_hourly = (
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 8, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 10, tzinfo=UTC)),
        window(Timeframe.HOUR_1, datetime(2026, 10, 16, 11, tzinfo=UTC)),
    )

    result = align((*gapped_hourly, *complete_windows()[3:]))

    assert result.status is MarketContextAlignmentStatus.INSUFFICIENT_DATA
    assert MarketContextAlignmentIssueCode.WINDOW_GAP in result.issue_codes
    assert result.coverages[0].missing_window_starts == (datetime(2026, 10, 16, 9, tzinfo=UTC),)


def test_alignment_fails_closed_for_unfinalized_or_mixed_stream_inputs() -> None:
    provisional = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 11, tzinfo=UTC),
        version=1,
        finalized=False,
    )
    with pytest.raises(ValueError, match="finalized windows only"):
        align((provisional,))

    other_pair = TradingPair(base_asset="ETH", quote_asset="USDT")
    mixed = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 11, tzinfo=UTC),
        pair=other_pair,
    )
    with pytest.raises(ValueError, match="cannot mix market streams"):
        align((mixed,))

    with pytest.raises(ValueError, match="anchor timeframe boundary"):
        align((), as_of=AS_OF + timedelta(minutes=1))


def test_sqlalchemy_assembler_stages_idempotent_ready_manifest_without_committing() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    inputs = complete_windows()
    revised_latest = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 11, tzinfo=UTC),
        version=3,
        close_price="107",
    )
    provisional_revision = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 11, tzinfo=UTC),
        version=4,
        close_price="108",
        finalized=False,
    )
    provisional_future = window(
        Timeframe.HOUR_1,
        datetime(2026, 10, 16, 12, tzinfo=UTC),
        version=1,
        finalized=False,
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            for snapshot in (
                *inputs,
                revised_latest,
                provisional_revision,
                provisional_future,
            ):
                store.stage_window_version(snapshot)

        with factory() as session:
            assembler = SqlAlchemyMarketContextAssembler(session)
            first = assembler.assemble_and_stage(
                source=SOURCE,
                pair=PAIR,
                as_of=AS_OF,
                feature_set=feature_set(),
                aligned_at=ALIGNED_AT,
            )
            second = assembler.assemble_and_stage(
                source=SOURCE,
                pair=PAIR,
                as_of=AS_OF,
                feature_set=feature_set(),
                aligned_at=ALIGNED_AT + timedelta(minutes=1),
            )
            assert first.manifest == second.manifest
            assert first.aligned_at != second.aligned_at
            assert first.manifest is not None
            assert first.manifest.windows[2].version == 3
            assert (
                session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 1
            )
            session.rollback()

        with factory() as session:
            assert (
                session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 0
            )
    finally:
        engine.dispose()


def test_sqlalchemy_assembler_does_not_stage_non_ready_alignment() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            for snapshot in complete_windows()[1:]:
                store.stage_window_version(snapshot)

        with factory.begin() as session:
            result = SqlAlchemyMarketContextAssembler(session).assemble_and_stage(
                source=SOURCE,
                pair=PAIR,
                as_of=AS_OF,
                feature_set=feature_set(),
                aligned_at=ALIGNED_AT,
            )
            assert result.status is MarketContextAlignmentStatus.INSUFFICIENT_DATA
            assert result.manifest is None
            assert (
                session.scalar(select(func.count()).select_from(MarketContextInputManifestRow)) == 0
            )
    finally:
        engine.dispose()
