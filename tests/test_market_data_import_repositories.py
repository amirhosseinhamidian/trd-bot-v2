from datetime import UTC, datetime, timedelta

from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.market_data_import_repositories import SqlAlchemyMarketDataImportRepository
from trd_bot.db.models import DatasetSnapshotRow, MarketDataConnectionRow
from trd_bot.domain.market_data import Timeframe, TradingPair
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportStatus,
)

START = datetime(2026, 8, 31, 10, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CONNECTION_ID = "market-data-connection-history-repo"
DATASET_ID = "dataset-history-repo-0001"


def test_sqlalchemy_import_history_round_trips_and_filters() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory.begin() as session:
            session.add(
                MarketDataConnectionRow(
                    connection_id=CONNECTION_ID,
                    provider_id="binance-public",
                    display_name="Public history",
                    state="enabled",
                    health_status="healthy",
                    created_at=START,
                    updated_at=START,
                    last_tested_at=START,
                    last_error=None,
                )
            )
            session.add(
                DatasetSnapshotRow(
                    dataset_id=DATASET_ID,
                    created_at=START,
                    source="binance-public",
                    base_asset="BTC",
                    quote_asset="USDT",
                    market_type="spot",
                    timeframe="1h",
                    start_time=START - timedelta(hours=2),
                    end_time=START,
                    candle_count=2,
                    checksum="a" * 64,
                    payload_json='{"dataset_id":"dataset-history-repo-0001"}',
                )
            )

        with factory() as session:
            repository = SqlAlchemyMarketDataImportRepository(session)
            succeeded = MarketDataImportRecord(
                import_id="market-data-import-success",
                connection_id=CONNECTION_ID,
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
                dataset_id=DATASET_ID,
            )
            succeeded_payload = succeeded.model_dump()
            succeeded_payload.update(
                {
                    "root_import_id": succeeded.import_id,
                    "version_number": 1,
                }
            )
            succeeded = MarketDataImportRecord.model_validate(succeeded_payload)

            refresh = MarketDataImportRecord(
                import_id="market-data-import-refresh",
                connection_id=CONNECTION_ID,
                provider_id="binance-public",
                dataset_name="BTC history",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                requested_start_time=START - timedelta(hours=2),
                requested_end_time=START,
                created_at=START + timedelta(seconds=10),
                completed_at=START + timedelta(seconds=11),
                status=MarketDataImportStatus.SUCCEEDED,
                candle_count=2,
                dataset_id=DATASET_ID,
                operation=MarketDataImportOperation.REFRESH,
                source_dataset_id=DATASET_ID,
                root_import_id=succeeded.import_id,
                parent_import_id=succeeded.import_id,
                version_number=2,
                content_changed=False,
            )

            failed = MarketDataImportRecord(
                import_id="market-data-import-failed",
                connection_id=CONNECTION_ID,
                provider_id="binance-public",
                dataset_name="BTC history",
                pair=PAIR,
                timeframe=Timeframe.HOUR_1,
                requested_start_time=START - timedelta(hours=2),
                requested_end_time=START,
                created_at=START + timedelta(minutes=1),
                completed_at=START + timedelta(minutes=1, seconds=1),
                status=MarketDataImportStatus.FAILED,
                candle_count=0,
                error_code="provider_request_failed",
                error_message="temporary provider failure",
            )

            repository.save(succeeded)
            repository.save(refresh)
            repository.save(failed)

            assert repository.get(succeeded.import_id) == succeeded
            assert repository.count(connection_id=CONNECTION_ID) == 3
            assert repository.count(status=MarketDataImportStatus.FAILED) == 1
            assert repository.count(root_import_id=succeeded.import_id) == 2
            assert repository.count(dataset_id=DATASET_ID) == 2
            assert repository.get_latest_successful_version(succeeded.import_id) == refresh
            assert repository.list_page(
                connection_id=CONNECTION_ID,
                limit=10,
                offset=0,
            ) == (failed, refresh, succeeded)
    finally:
        engine.dispose()
