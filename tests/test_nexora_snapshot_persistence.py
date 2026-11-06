from datetime import UTC, datetime, timedelta

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyNexoraSnapshotScanStore,
    create_database_engine,
    create_session_factory,
)

NOW = datetime(2026, 11, 6, 8, tzinfo=UTC)


def test_sqlalchemy_store_persists_and_reuses_opaque_cursor() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)
    try:
        with factory.begin() as session:
            store = SqlAlchemyNexoraSnapshotScanStore(session)
            scan = store.create_scan(
                resource_type="candidate",
                boundary_key="candidate:0009",
                boundary_at=NOW,
                page_limit=2,
                opened_at=NOW,
                expires_at=NOW + timedelta(hours=1),
            )
            cursor = store.get_or_create_cursor(
                scan=scan, after_sort_key="candidate:0002", created_at=NOW
            )
            repeated = store.get_or_create_cursor(
                scan=scan, after_sort_key="candidate:0002", created_at=NOW + timedelta(minutes=1)
            )
            assert repeated == cursor
            assert cursor.cursor.startswith("snp_")
            assert "candidate" not in cursor.cursor
        with factory() as session:
            assert SqlAlchemyNexoraSnapshotScanStore(session).resolve_cursor(cursor.cursor) == (
                scan,
                cursor,
            )
    finally:
        engine.dispose()
