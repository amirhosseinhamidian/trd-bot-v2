from datetime import UTC, datetime, timedelta

from trd_bot.db import (
    DatabaseBase,
    SqlAlchemyMonitoringRuntimeStateRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.monitoring import InMemoryMonitoringRuntimeStateRepository

CHECKED_AT = datetime(2026, 8, 26, 12, tzinfo=UTC)


def test_in_memory_runtime_state_is_monotonic() -> None:
    repository = InMemoryMonitoringRuntimeStateRepository()

    assert repository.get().last_checked_at is None

    repository.mark_checked(checked_at=CHECKED_AT)
    repository.mark_checked(
        checked_at=(CHECKED_AT - timedelta(minutes=5)),
    )

    assert repository.get().last_checked_at == CHECKED_AT


def test_sqlalchemy_runtime_state_persists_across_sessions() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            repository = SqlAlchemyMonitoringRuntimeStateRepository(session)
            assert repository.get().last_checked_at is None
            repository.mark_checked(checked_at=CHECKED_AT)

        with factory() as session:
            repository = SqlAlchemyMonitoringRuntimeStateRepository(session)
            assert repository.get().last_checked_at == CHECKED_AT
    finally:
        engine.dispose()
