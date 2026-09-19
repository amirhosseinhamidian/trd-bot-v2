from datetime import UTC, datetime, timedelta

from trd_bot.db import DatabaseBase, create_database_engine, create_session_factory
from trd_bot.db.market_data_connection_repositories import (
    SqlAlchemyMarketDataConnectionRepository,
)
from trd_bot.market_data import (
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
    MarketDataProviderErrorCode,
)

BASE_TIME = datetime(2026, 8, 31, 12, tzinfo=UTC)


def build_connection(
    connection_id: str,
    *,
    created_at: datetime = BASE_TIME,
) -> MarketDataConnection:
    return MarketDataConnection(
        connection_id=connection_id,
        provider_id="binance-public",
        display_name="Binance historical data",
        created_at=created_at,
        updated_at=created_at,
    )


def test_sqlalchemy_connection_repository_persists_health_and_state_updates() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            repository = SqlAlchemyMarketDataConnectionRepository(session)
            connection = build_connection("market-data-connection-1")
            repository.save(connection)

            tested_at = BASE_TIME + timedelta(minutes=1)
            healthy = MarketDataConnection.model_validate(
                connection.model_copy(
                    update={
                        "state": MarketDataConnectionState.ENABLED,
                        "health_status": MarketDataConnectionHealth.HEALTHY,
                        "updated_at": tested_at,
                        "last_tested_at": tested_at,
                        "last_error": None,
                    }
                ).model_dump()
            )
            repository.save(healthy)

            stored = repository.get(connection.connection_id)

            assert stored is not None
            assert stored.state is MarketDataConnectionState.ENABLED
            assert stored.health_status is MarketDataConnectionHealth.HEALTHY
            assert stored.last_tested_at == tested_at
            assert stored.last_error_code is None
            assert stored.last_error is None

            failed_at = BASE_TIME + timedelta(minutes=2)
            unhealthy = MarketDataConnection.model_validate(
                healthy.model_copy(
                    update={
                        "state": MarketDataConnectionState.DISABLED,
                        "health_status": MarketDataConnectionHealth.UNHEALTHY,
                        "updated_at": failed_at,
                        "last_tested_at": failed_at,
                        "last_error_code": MarketDataProviderErrorCode.TIMEOUT,
                        "last_error": "market-data provider health check timed out",
                    }
                ).model_dump()
            )
            repository.save(unhealthy)

            failed = repository.get(connection.connection_id)
            assert failed is not None
            assert failed.health_status is MarketDataConnectionHealth.UNHEALTHY
            assert failed.last_error_code is MarketDataProviderErrorCode.TIMEOUT
            assert failed.last_error == "market-data provider health check timed out"
    finally:
        engine.dispose()


def test_sqlalchemy_connection_repository_lists_newest_first() -> None:
    engine = create_database_engine("sqlite+pysqlite:///:memory:")
    DatabaseBase.metadata.create_all(engine)
    factory = create_session_factory(engine)

    try:
        with factory() as session:
            repository = SqlAlchemyMarketDataConnectionRepository(session)
            repository.save(
                build_connection(
                    "market-data-connection-older",
                    created_at=BASE_TIME,
                )
            )
            repository.save(
                build_connection(
                    "market-data-connection-newer",
                    created_at=BASE_TIME + timedelta(minutes=1),
                )
            )

            page = repository.list_page(limit=1, offset=0)

            assert repository.count() == 2
            assert [item.connection_id for item in page] == ["market-data-connection-newer"]
    finally:
        engine.dispose()
