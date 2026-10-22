from datetime import UTC, datetime, timedelta

import pytest

from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.import_history import (
    InMemoryMarketDataImportRepository,
    MarketDataImportOperation,
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


def test_refresh_lineage_requires_complete_success_metadata() -> None:
    with pytest.raises(ValueError, match="successful refresh must record whether content changed"):
        MarketDataImportRecord(
            import_id="market-data-import-refresh",
            connection_id="market-data-connection-1",
            provider_id="binance-public",
            dataset_name="BTC history",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            requested_start_time=START - timedelta(hours=2),
            requested_end_time=START,
            created_at=START,
            completed_at=START + timedelta(seconds=1),
            status=MarketDataImportStatus.SUCCEEDED,
            candle_count=2,
            dataset_id="dataset-refresh",
            operation=MarketDataImportOperation.REFRESH,
            source_dataset_id="dataset-source",
            root_import_id="market-data-import-root",
            parent_import_id="market-data-import-root",
            version_number=2,
        )


def test_in_memory_history_tracks_latest_successful_version() -> None:
    repository = InMemoryMarketDataImportRepository()
    root_payload = build_record("market-data-import-root").model_dump()
    root_payload.update(
        {
            "root_import_id": "market-data-import-root",
            "version_number": 1,
        }
    )
    root = MarketDataImportRecord.model_validate(root_payload)

    refresh_payload = build_record(
        "market-data-import-refresh",
        created_at=START + timedelta(minutes=1),
    ).model_dump()
    refresh_payload.update(
        {
            "operation": MarketDataImportOperation.REFRESH,
            "source_dataset_id": "dataset-1234567890abcdef",
            "root_import_id": root.import_id,
            "parent_import_id": root.import_id,
            "version_number": 2,
            "content_changed": False,
        }
    )
    refresh = MarketDataImportRecord.model_validate(refresh_payload)

    repository.save(root)
    repository.save(refresh)

    assert repository.count(root_import_id=root.import_id) == 2
    assert repository.count(dataset_id="dataset-1234567890abcdef") == 2
    assert repository.get_latest_successful_version(root.import_id) == refresh


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
