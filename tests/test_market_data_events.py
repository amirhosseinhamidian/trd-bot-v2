from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    MarketDataArrivalClass,
    MarketDataEvent,
    MarketDataEventDisposition,
    MarketDataEventReason,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
    decide_market_data_event,
)

PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


def create_candle(
    hour: int = 10,
    *,
    close_price: str = "105",
    is_closed: bool = True,
    received_hour: int = 20,
) -> OHLCVCandle:
    return OHLCVCandle(
        source="nobitex-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        open_time=datetime(2026, 10, 9, hour, tzinfo=UTC),
        close_time=datetime(2026, 10, 9, hour + 1, tzinfo=UTC),
        received_at=datetime(2026, 10, 9, received_hour, tzinfo=UTC),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal(close_price),
        volume=Decimal("1250.5"),
        is_closed=is_closed,
    )


def create_watermark(
    *,
    high_water_hour: int = 12,
    allowed_lateness_seconds: int = 0,
) -> MarketDataWatermark:
    return MarketDataWatermark.build(
        source="nobitex-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        high_water_event_time=datetime(2026, 10, 9, high_water_hour, tzinfo=UTC),
        allowed_lateness_seconds=allowed_lateness_seconds,
        calculated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )


def test_event_identity_ignores_transport_receipt_time() -> None:
    first = MarketDataEvent.from_candle(create_candle(received_hour=20))
    redelivered = MarketDataEvent.from_candle(create_candle(received_hour=21))

    assert first.event_id == redelivered.event_id
    assert first.idempotency_key == redelivered.idempotency_key
    assert first.payload_checksum == redelivered.payload_checksum
    assert first.observed_at != redelivered.observed_at


def test_corrected_payload_keeps_window_identity_but_changes_event_identity() -> None:
    original = MarketDataEvent.from_candle(create_candle(close_price="105"))
    correction = MarketDataEvent.from_candle(create_candle(close_price="106"))

    assert original.window_id == correction.window_id
    assert original.event_id != correction.event_id
    assert original.payload_checksum != correction.payload_checksum


def test_event_rejects_envelope_metadata_that_disagrees_with_payload() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    payload = event.model_dump()
    payload["source"] = "kraken-public"

    with pytest.raises(ValidationError, match="event source does not match"):
        MarketDataEvent.model_validate(payload)


def test_watermark_classifies_boundary_as_late_and_never_moves_backwards() -> None:
    watermark = create_watermark(high_water_hour=12, allowed_lateness_seconds=3600)
    boundary_event = MarketDataEvent.from_candle(create_candle(hour=10))
    on_time_event = MarketDataEvent.from_candle(create_candle(hour=12))

    assert watermark.watermark_time == datetime(2026, 10, 9, 11, tzinfo=UTC)
    assert watermark.classify(boundary_event) is MarketDataArrivalClass.LATE
    assert watermark.classify(on_time_event) is MarketDataArrivalClass.ON_TIME

    unchanged = watermark.advance(
        boundary_event,
        calculated_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
    )
    advanced = watermark.advance(
        on_time_event,
        calculated_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
    )

    assert unchanged.high_water_event_time == watermark.high_water_event_time
    assert advanced.high_water_event_time == on_time_event.event_time
    assert advanced.watermark_time == datetime(2026, 10, 9, 12, tzinfo=UTC)


def test_watermark_rejects_event_from_another_stream() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    watermark = MarketDataWatermark.build(
        source="kraken-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        high_water_event_time=datetime(2026, 10, 9, 12, tzinfo=UTC),
        allowed_lateness_seconds=0,
        calculated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="watermark stream"):
        watermark.classify(event)


def test_watermark_rejects_a_backwards_calculation_time() -> None:
    watermark = create_watermark()
    event = MarketDataEvent.from_candle(create_candle(hour=12))

    with pytest.raises(ValueError, match="calculation time cannot move backwards"):
        watermark.advance(
            event,
            calculated_at=datetime(2026, 10, 9, 19, tzinfo=UTC),
        )


def test_new_window_is_accepted_with_version_one() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    decision = decide_market_data_event(
        event,
        watermark=create_watermark(allowed_lateness_seconds=7200),
        existing_window=None,
        decided_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    assert decision.arrival is MarketDataArrivalClass.ON_TIME
    assert decision.disposition is MarketDataEventDisposition.ACCEPTED
    assert decision.reason is MarketDataEventReason.NEW_WINDOW
    assert decision.proposed_window_version == 1
    assert decision.requires_replay is False


def test_late_new_window_requires_explicit_replay() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    decision = decide_market_data_event(
        event,
        watermark=create_watermark(),
        existing_window=None,
        decided_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    assert decision.arrival is MarketDataArrivalClass.LATE
    assert decision.disposition is MarketDataEventDisposition.REVISION_REQUIRED
    assert decision.reason is MarketDataEventReason.LATE_ARRIVAL
    assert decision.proposed_window_version == 1
    assert decision.requires_replay is True


def test_duplicate_payload_does_not_create_another_window_version() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    existing = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    decision = decide_market_data_event(
        event,
        watermark=create_watermark(),
        existing_window=existing,
        decided_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    assert decision.disposition is MarketDataEventDisposition.DUPLICATE
    assert decision.reason is MarketDataEventReason.DUPLICATE_PAYLOAD
    assert decision.existing_window_version == 1
    assert decision.proposed_window_version is None


def test_correction_updates_only_a_provisional_window() -> None:
    original = MarketDataEvent.from_candle(create_candle(close_price="105"))
    correction = MarketDataEvent.from_candle(create_candle(close_price="106"))
    existing = MarketDataWindowSnapshot.from_event(
        original,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    decision = decide_market_data_event(
        correction,
        watermark=create_watermark(allowed_lateness_seconds=7200),
        existing_window=existing,
        decided_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
    )

    assert decision.disposition is MarketDataEventDisposition.ACCEPTED
    assert decision.reason is MarketDataEventReason.PROVISIONAL_UPDATE
    assert decision.existing_window_version == 1
    assert decision.proposed_window_version == 2


def test_finalization_creates_a_new_immutable_version() -> None:
    event = MarketDataEvent.from_candle(create_candle())
    provisional = MarketDataWindowSnapshot.from_event(
        event,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    finalized = provisional.finalize(
        create_watermark(),
        finalized_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
    )

    assert provisional.state is MarketDataWindowState.PROVISIONAL
    assert provisional.version == 1
    assert provisional.finalized_at is None
    assert finalized.state is MarketDataWindowState.FINALIZED
    assert finalized.version == 2
    assert finalized.finalized_at == datetime(2026, 10, 9, 21, tzinfo=UTC)


def test_open_or_not_yet_watermarked_window_cannot_finalize() -> None:
    open_event = MarketDataEvent.from_candle(create_candle(is_closed=False))
    open_window = MarketDataWindowSnapshot.from_event(
        open_event,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="open candle"):
        open_window.finalize(
            create_watermark(),
            finalized_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
        )

    closed_event = MarketDataEvent.from_candle(create_candle())
    closed_window = MarketDataWindowSnapshot.from_event(
        closed_event,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )
    early_watermark = MarketDataWatermark.build(
        source="nobitex-public",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        high_water_event_time=datetime(2026, 10, 9, 10, 30, tzinfo=UTC),
        allowed_lateness_seconds=0,
        calculated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )

    with pytest.raises(ValueError, match="has not passed"):
        closed_window.finalize(
            early_watermark,
            finalized_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
        )


def test_correction_after_finalization_requires_explicit_replay() -> None:
    original = MarketDataEvent.from_candle(create_candle(close_price="105"))
    correction = MarketDataEvent.from_candle(create_candle(close_price="106"))
    provisional = MarketDataWindowSnapshot.from_event(
        original,
        version=1,
        created_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
    )
    finalized = provisional.finalize(
        create_watermark(),
        finalized_at=datetime(2026, 10, 9, 21, tzinfo=UTC),
    )

    decision = decide_market_data_event(
        correction,
        watermark=create_watermark(),
        existing_window=finalized,
        decided_at=datetime(2026, 10, 9, 22, tzinfo=UTC),
    )

    assert decision.disposition is MarketDataEventDisposition.REVISION_REQUIRED
    assert decision.reason is MarketDataEventReason.FINALIZED_WINDOW_CONFLICT
    assert decision.existing_window_version == 2
    assert decision.proposed_window_version == 3
    assert decision.requires_replay is True
    assert finalized.payload_checksum == original.payload_checksum
