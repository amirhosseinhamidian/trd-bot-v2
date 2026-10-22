from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.db import DatabaseBase, SqlAlchemyMarketDataEventStore
from trd_bot.db.session import create_database_engine, create_session_factory
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataEvent,
    MarketDataInboxReceipt,
    MarketDataOutboxMessage,
    MarketDataRawObservation,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    VersionedMarketDataWatermark,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
WINDOW_START = datetime(2026, 10, 14, 8, tzinfo=UTC)
WINDOW_END = datetime(2026, 10, 14, 9, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 10, 14, 9, 0, 5, tzinfo=UTC)
STORED_AT = datetime(2026, 10, 14, 9, 0, 6, tzinfo=UTC)


def create_candle() -> OHLCVCandle:
    return OHLCVCandle(
        source="kraken-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=WINDOW_START,
        close_time=WINDOW_END,
        received_at=OBSERVED_AT,
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1250.5"),
        is_closed=True,
    )


def create_raw_observation() -> MarketDataRawObservation:
    return MarketDataRawObservation.build(
        source="kraken-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        window_start=WINDOW_START,
        window_end=WINDOW_END,
        observed_at=OBSERVED_AT,
        payload={
            "open": "100",
            "high": "110",
            "low": "95",
            "close": "105",
            "volume": "1250.5",
        },
        created_at=STORED_AT,
    )


def create_watermark() -> MarketDataWatermark:
    return MarketDataWatermark.build(
        source="kraken-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        high_water_event_time=datetime(2026, 10, 14, 10, tzinfo=UTC),
        allowed_lateness_seconds=0,
        calculated_at=datetime(2026, 10, 14, 10, 0, 1, tzinfo=UTC),
    )


def test_raw_observation_identity_is_content_and_delivery_bound() -> None:
    observation = create_raw_observation()
    redelivery = MarketDataRawObservation.build(
        source=observation.source,
        pair=observation.pair,
        timeframe=observation.timeframe,
        window_start=observation.window_start,
        window_end=observation.window_end,
        observed_at=datetime(2026, 10, 14, 9, 0, 10, tzinfo=UTC),
        payload=observation.payload,
        created_at=datetime(2026, 10, 14, 9, 0, 11, tzinfo=UTC),
    )

    assert observation.payload_checksum == redelivery.payload_checksum
    assert observation.observation_id != redelivery.observation_id

    invalid_payload = observation.model_dump()
    invalid_payload["payload"] = {"close": "999"}
    with pytest.raises(ValidationError, match="payload checksum is inconsistent"):
        MarketDataRawObservation.model_validate(invalid_payload)


def test_inbox_and_outbox_contracts_preserve_deduplication_identity() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    receipt = MarketDataInboxReceipt.from_event(event)
    redelivery = receipt.record_redelivery(observed_at=datetime(2026, 10, 14, 9, 1, tzinfo=UTC))
    message = MarketDataOutboxMessage.from_event(
        event,
        topic="market-data.windowing",
        created_at=STORED_AT,
    )

    assert receipt.idempotency_key == event.idempotency_key
    assert redelivery.delivery_count == 2
    assert redelivery.first_seen_at == receipt.first_seen_at
    assert message.event_id == event.event_id
    assert message.payload_version == event.schema_version
    assert message.payload["idempotency_key"] == event.idempotency_key


def test_event_store_round_trips_all_p2_01_records() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    raw = create_raw_observation()
    event = MarketDataEvent.from_candle(create_candle())
    inbox = MarketDataInboxReceipt.from_event(event)
    outbox = MarketDataOutboxMessage.from_event(
        event,
        topic="market-data.windowing",
        created_at=STORED_AT,
    )
    provisional = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=STORED_AT,
    )
    watermark = create_watermark()
    finalized = provisional.finalize(
        watermark,
        finalized_at=datetime(2026, 10, 14, 10, 0, 2, tzinfo=UTC),
    )
    stored_watermark = VersionedMarketDataWatermark.build(
        watermark=watermark,
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=datetime(2026, 10, 14, 10, 0, 2, tzinfo=UTC),
    )

    try:
        with factory.begin() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            assert store.stage_raw_observation(raw)[1] is True
            assert (
                store.stage_event(
                    event,
                    raw_observation_id=raw.observation_id,
                    persisted_at=STORED_AT,
                )[1]
                is True
            )
            assert store.stage_inbox_receipt(inbox)[1] is True
            assert store.stage_outbox_message(outbox)[1] is True
            assert store.stage_window_version(provisional)[1] is True
            assert store.stage_window_version(finalized)[1] is True
            assert store.stage_watermark(stored_watermark)[1] is True

        with factory() as session:
            store = SqlAlchemyMarketDataEventStore(session)
            assert store.get_raw_observation(raw.observation_id) == raw
            persisted_event = store.get_event(event.event_id)
            assert persisted_event is not None
            assert persisted_event.event == event
            assert persisted_event.raw_observation_id == raw.observation_id
            assert store.get_event_by_idempotency_key(event.idempotency_key) == persisted_event
            assert store.get_inbox_receipt(inbox.idempotency_key) == inbox
            assert store.get_outbox_message(outbox.outbox_id) == outbox
            assert store.get_window_version(provisional.window_id, 1) == provisional
            assert store.get_latest_window(provisional.window_id) == finalized
            assert store.get_watermark(stored_watermark.watermark_id) == stored_watermark
            assert (
                store.get_latest_watermark(
                    source="kraken-public",
                    pair=PAIR,
                    timeframe=Timeframe.HOUR_1,
                )
                == stored_watermark
            )

            assert store.stage_raw_observation(raw)[1] is False
            assert (
                store.stage_event(
                    event,
                    raw_observation_id=raw.observation_id,
                    persisted_at=STORED_AT,
                )[1]
                is False
            )
            assert store.stage_inbox_receipt(inbox)[1] is False
            assert store.stage_outbox_message(outbox)[1] is False
            assert store.stage_window_version(finalized)[1] is False
            assert store.stage_watermark(stored_watermark)[1] is False
    finally:
        engine.dispose()


def test_watermark_storage_identity_is_version_and_policy_bound() -> None:
    watermark = create_watermark()
    first = VersionedMarketDataWatermark.build(
        watermark=watermark,
        version=1,
        policy_version="market-data-service-level-policy-v1",
        stored_at=datetime(2026, 10, 14, 10, 0, 2, tzinfo=UTC),
    )
    second = VersionedMarketDataWatermark.build(
        watermark=watermark,
        version=2,
        policy_version="market-data-service-level-policy-v1",
        stored_at=datetime(2026, 10, 14, 10, 0, 3, tzinfo=UTC),
    )

    assert first.watermark_id != second.watermark_id
