from datetime import UTC, datetime, timedelta

import pytest

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.import_history import (
    InMemoryMarketDataImportRepository,
    MarketDataImportRecord,
    MarketDataImportStatus,
)

START = datetime(2026, 8, 31, 10, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")


def build_record(
    import_id: str,
    *,
    status: MarketDataImportStatus = MarketDataImportStatus.SUCCEEDED,
    created_at: datetime = START,
) -> MarketDataImportRecord:
    succeeded = status is MarketDataImportStatus.SUCCEEDED
    return MarketDataImportRecord(
        import_id=import_id,
        connection_id="market-data-connection-1",
        provider_id="binance-public",
        dataset_name="BTC history",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        requested_start_time=START - timedelta(hours=2),
        requested_end_time=START,
        created_at=created_at,
        completed_at=created_at + timedelta(seconds=1),
        status=status,
        candle_count=2 if succeeded else 0,
        dataset_id="dataset-1234567890abcdef" if succeeded else None,
        error_code=None if succeeded else "provider_request_failed",
        error_message=None if succeeded else "temporary provider failure",
    )


def test_import_record_enforces_outcome_consistency() -> None:
    with pytest.raises(ValueError, match="successful import must reference a dataset"):
        MarketDataImportRecord(
            import_id="market-data-import-bad",
            connection_id="market-data-connection-1",
            provider_id="binance-public",
            dataset_name="BTC history",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            requested_start_time=START - timedelta(hours=2),
            requested_end_time=START,
            created_at=START,
            completed_at=START,
            status=MarketDataImportStatus.SUCCEEDED,
            candle_count=2,
        )


def test_in_memory_history_filters_and_orders_newest_first() -> None:
    repository = InMemoryMarketDataImportRepository()
    repository.save(build_record("market-data-import-1"))
    repository.save(
        build_record(
            "market-data-import-2",
            status=MarketDataImportStatus.FAILED,
            created_at=START + timedelta(minutes=1),
        )
    )

    assert repository.count(connection_id="market-data-connection-1") == 2
    assert repository.count(status=MarketDataImportStatus.FAILED) == 1
    assert [record.import_id for record in repository.list_page(limit=10, offset=0)] == [
        "market-data-import-2",
        "market-data-import-1",
    ]
