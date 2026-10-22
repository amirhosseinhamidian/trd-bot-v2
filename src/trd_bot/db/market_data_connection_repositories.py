from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import MarketDataConnectionRow
from trd_bot.market_data.connections import (
    MarketDataConnection,
    MarketDataConnectionHealth,
    MarketDataConnectionState,
)
from trd_bot.market_data.providers import MarketDataProviderErrorCode


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class SqlAlchemyMarketDataConnectionRepository:
    """Persist configured read-only market-data connections."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, connection: MarketDataConnection) -> MarketDataConnection:
        row = self._session.get(MarketDataConnectionRow, connection.connection_id)

        if row is None:
            row = MarketDataConnectionRow(
                connection_id=connection.connection_id,
                provider_id=connection.provider_id,
                display_name=connection.display_name,
                state=connection.state.value,
                health_status=connection.health_status.value,
                created_at=connection.created_at,
                updated_at=connection.updated_at,
                last_tested_at=connection.last_tested_at,
                last_error_code=(
                    connection.last_error_code.value
                    if connection.last_error_code is not None
                    else None
                ),
                last_error=connection.last_error,
            )
            self._session.add(row)
        else:
            row.provider_id = connection.provider_id
            row.display_name = connection.display_name
            row.state = connection.state.value
            row.health_status = connection.health_status.value
            row.created_at = connection.created_at
            row.updated_at = connection.updated_at
            row.last_tested_at = connection.last_tested_at
            row.last_error_code = (
                connection.last_error_code.value if connection.last_error_code is not None else None
            )
            row.last_error = connection.last_error

        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            raise ValueError("market-data connection could not be persisted") from exc

        return connection

    def get(self, connection_id: str) -> MarketDataConnection | None:
        row = self._session.get(MarketDataConnectionRow, connection_id)
        if row is None:
            return None
        return self._to_model(row)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(MarketDataConnectionRow))
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[MarketDataConnection, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        rows = self._session.scalars(
            select(MarketDataConnectionRow)
            .order_by(
                MarketDataConnectionRow.created_at.desc(),
                MarketDataConnectionRow.connection_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(self._to_model(row) for row in rows)

    @staticmethod
    def _to_model(row: MarketDataConnectionRow) -> MarketDataConnection:
        return MarketDataConnection(
            connection_id=row.connection_id,
            provider_id=row.provider_id,
            display_name=row.display_name,
            state=MarketDataConnectionState(row.state),
            health_status=MarketDataConnectionHealth(row.health_status),
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
            last_tested_at=(
                _as_utc(row.last_tested_at) if row.last_tested_at is not None else None
            ),
            last_error_code=(
                MarketDataProviderErrorCode(row.last_error_code)
                if row.last_error_code is not None
                else None
            ),
            last_error=row.last_error,
        )
