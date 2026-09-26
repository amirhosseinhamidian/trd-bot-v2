from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyDatasetRepository,
    SqlAlchemyHistoricalDatasetCommitter,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.market_data_import_repositories import (
    SqlAlchemyMarketDataImportRepository,
)
from trd_bot.db.models import MarketDataConnectionRow
from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportStatus,
)
from trd_bot.research import (
    DatasetBuilder,
    DatasetProvenance,
    DatasetProvenanceKind,
    DatasetSnapshot,
    HistoricalDatasetRefreshConflictError,
)

START = datetime(2026, 9, 24, 10, tzinfo=UTC)
PAIR = TradingPair(base_asset="BTC", quote_asset="USDT")
CONNECTION_ID = "market-data-connection-atomic-commit"


@pytest.fixture
def session_factory(tmp_path: Path) -> Iterator[sessionmaker[Session]]:
    engine = create_database_engine(
        f"sqlite+pysqlite:///{tmp_path / 'historical-dataset-commits.db'}"
    )
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    with factory.begin() as session:
        session.add(
            MarketDataConnectionRow(
                connection_id=CONNECTION_ID,
                provider_id="synthetic-public",
                display_name="Atomic commit feed",
                state="enabled",
                health_status="healthy",
                created_at=START,
                updated_at=START,
                last_tested_at=START,
                last_error_code=None,
                last_error=None,
            )
        )

    try:
        yield factory
    finally:
        engine.dispose()


def build_dataset(import_id: str, *, close_price: str = "105") -> DatasetSnapshot:
    candles = tuple(
        OHLCVCandle(
            source="synthetic-public",
            pair=PAIR,
            timeframe=Timeframe.HOUR_1,
            open_time=START + timedelta(hours=index),
            close_time=START + timedelta(hours=index + 1),
            received_at=START,
            open_price=Decimal("100"),
            high_price=Decimal("110"),
            low_price=Decimal("95"),
            close_price=Decimal(close_price),
            volume=Decimal("1000"),
            is_closed=True,
        )
        for index in range(2)
    )
    return DatasetBuilder().build(
        name="Atomic BTC history",
        candles=candles,
        created_at=START,
        provenance=DatasetProvenance(
            kind=DatasetProvenanceKind.MARKET_DATA_IMPORT,
            connection_id=CONNECTION_ID,
            provider_id="synthetic-public",
            import_id=import_id,
            requested_start_time=START,
            requested_end_time=START + timedelta(hours=2),
        ),
        requested_start_time=START,
        requested_end_time=START + timedelta(hours=2),
        requested_timeframe=Timeframe.HOUR_1,
    )


def build_record(
    *,
    import_id: str,
    dataset: DatasetSnapshot,
    operation: MarketDataImportOperation = MarketDataImportOperation.IMPORT,
    source_dataset_id: str | None = None,
    root_import_id: str | None = None,
    parent_import_id: str | None = None,
    version_number: int | None = None,
    content_changed: bool | None = None,
) -> MarketDataImportRecord:
    return MarketDataImportRecord(
        import_id=import_id,
        connection_id=CONNECTION_ID,
        provider_id="synthetic-public",
        dataset_name="Atomic BTC history",
        pair=PAIR,
        timeframe=Timeframe.HOUR_1,
        requested_start_time=START,
        requested_end_time=START + timedelta(hours=2),
        created_at=START,
        completed_at=START + timedelta(seconds=1),
        status=MarketDataImportStatus.SUCCEEDED,
        candle_count=dataset.candle_count,
        dataset_id=dataset.dataset_id,
        quality_report=dataset.quality_report,
        operation=operation,
        source_dataset_id=source_dataset_id,
        root_import_id=root_import_id,
        parent_import_id=parent_import_id,
        version_number=version_number,
        content_changed=content_changed,
    )


def test_success_commit_persists_snapshot_and_history_together(
    session_factory: sessionmaker[Session],
) -> None:
    import_id = "market-data-import-atomic-root"
    dataset = build_dataset(import_id)

    with session_factory() as session:
        result = SqlAlchemyHistoricalDatasetCommitter(session).commit(
            dataset=dataset,
            record=build_record(import_id=import_id, dataset=dataset),
        )

    assert result.created_snapshot is True
    assert result.record.root_import_id == import_id
    assert result.record.version_number == 1

    with session_factory() as session:
        assert SqlAlchemyDatasetRepository(session).count() == 1
        history = SqlAlchemyMarketDataImportRepository(session)
        assert history.count() == 1
        stored = history.get(import_id)
        assert stored is not None
        assert stored.quality_report is not None
        assert stored.quality_report.score is not None
        assert stored.quality_report.score.score_percent == 100.0
        assert stored.quality_report.acceptance is not None
        assert stored.quality_report.acceptance.accepted is True


def test_history_failure_rolls_back_a_new_snapshot(
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import_id = "market-data-import-rollback"
    dataset = build_dataset(import_id)

    def fail_history_stage(
        repository: SqlAlchemyMarketDataImportRepository,
        record: MarketDataImportRecord,
    ) -> tuple[MarketDataImportRecord, bool]:
        del repository, record
        raise RuntimeError("injected history failure")

    monkeypatch.setattr(SqlAlchemyMarketDataImportRepository, "stage", fail_history_stage)

    with (
        session_factory() as session,
        pytest.raises(RuntimeError, match="injected history failure"),
    ):
        SqlAlchemyHistoricalDatasetCommitter(session).commit(
            dataset=dataset,
            record=build_record(import_id=import_id, dataset=dataset),
        )

    with session_factory() as session:
        assert SqlAlchemyDatasetRepository(session).count() == 0
        assert SqlAlchemyMarketDataImportRepository(session).count() == 0


def test_equal_content_reuses_snapshot_but_preserves_each_import_record(
    session_factory: sessionmaker[Session],
) -> None:
    first_id = "market-data-import-shared-first"
    second_id = "market-data-import-shared-second"
    first_dataset = build_dataset(first_id)
    second_dataset = build_dataset(second_id)

    with session_factory() as session:
        committer = SqlAlchemyHistoricalDatasetCommitter(session)
        first = committer.commit(
            dataset=first_dataset,
            record=build_record(import_id=first_id, dataset=first_dataset),
        )
        second = committer.commit(
            dataset=second_dataset,
            record=build_record(import_id=second_id, dataset=second_dataset),
        )

    assert first.created_snapshot is True
    assert second.created_snapshot is False
    assert second.dataset.provenance.import_id == first_id
    assert second.record.dataset_id == first.record.dataset_id
    assert second.record.root_import_id is None
    assert second.record.version_number is None

    with session_factory() as session:
        assert SqlAlchemyDatasetRepository(session).count() == 1
        assert SqlAlchemyMarketDataImportRepository(session).count() == 2


def test_stale_refresh_is_rejected_before_creating_an_orphan_snapshot(
    session_factory: sessionmaker[Session],
) -> None:
    root_id = "market-data-import-refresh-root"
    winner_id = "market-data-import-refresh-winner"
    stale_id = "market-data-import-refresh-stale"
    root_dataset = build_dataset(root_id)
    winner_dataset = build_dataset(winner_id, close_price="106")
    stale_dataset = build_dataset(stale_id, close_price="107")

    with session_factory() as session:
        committer = SqlAlchemyHistoricalDatasetCommitter(session)
        root = committer.commit(
            dataset=root_dataset,
            record=build_record(import_id=root_id, dataset=root_dataset),
        )
        committer.commit(
            dataset=winner_dataset,
            record=build_record(
                import_id=winner_id,
                dataset=winner_dataset,
                operation=MarketDataImportOperation.REFRESH,
                source_dataset_id=root_dataset.dataset_id,
                root_import_id=root.record.import_id,
                parent_import_id=root.record.import_id,
                version_number=2,
                content_changed=True,
            ),
            expected_parent_import_id=root.record.import_id,
        )

        with pytest.raises(HistoricalDatasetRefreshConflictError, match="concurrency race"):
            committer.commit(
                dataset=stale_dataset,
                record=build_record(
                    import_id=stale_id,
                    dataset=stale_dataset,
                    operation=MarketDataImportOperation.REFRESH,
                    source_dataset_id=root_dataset.dataset_id,
                    root_import_id=root.record.import_id,
                    parent_import_id=root.record.import_id,
                    version_number=2,
                    content_changed=True,
                ),
                expected_parent_import_id=root.record.import_id,
            )

    with session_factory() as session:
        datasets = SqlAlchemyDatasetRepository(session)
        history = SqlAlchemyMarketDataImportRepository(session)
        assert datasets.count() == 2
        assert datasets.get(stale_dataset.dataset_id) is None
        assert history.count(root_import_id=root_id) == 2
        assert history.get(stale_id) is None
