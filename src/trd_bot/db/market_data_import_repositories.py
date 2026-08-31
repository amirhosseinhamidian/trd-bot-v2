from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from trd_bot.db.models import MarketDataImportRow
from trd_bot.market_data.import_history import (
    MarketDataImportOperation,
    MarketDataImportRecord,
    MarketDataImportStatus,
)


class SqlAlchemyMarketDataImportRepository:
    """Persist immutable historical market-data import audit records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, record: MarketDataImportRecord) -> MarketDataImportRecord:
        existing = self.get(record.import_id)
        if existing is not None:
            if existing != record:
                raise ValueError("market-data import ID already exists with different content")
            return existing

        self._session.add(
            MarketDataImportRow(
                import_id=record.import_id,
                connection_id=record.connection_id,
                provider_id=record.provider_id,
                dataset_name=record.dataset_name,
                base_asset=record.pair.base_asset,
                quote_asset=record.pair.quote_asset,
                market_type=record.pair.market_type.value,
                timeframe=record.timeframe.value,
                requested_start_time=record.requested_start_time,
                requested_end_time=record.requested_end_time,
                created_at=record.created_at,
                completed_at=record.completed_at,
                status=record.status.value,
                candle_count=record.candle_count,
                dataset_id=record.dataset_id,
                error_code=record.error_code,
                error_message=record.error_message,
                operation=record.operation.value,
                source_dataset_id=record.source_dataset_id,
                root_import_id=record.root_import_id,
                parent_import_id=record.parent_import_id,
                version_number=record.version_number,
                content_changed=record.content_changed,
                payload_json=record.model_dump_json(),
            )
        )

        try:
            self._session.commit()
        except IntegrityError as exc:
            self._session.rollback()
            existing = self.get(record.import_id)
            if existing is not None and existing == record:
                return existing
            raise ValueError("market-data import history could not be persisted") from exc

        return record

    def get(self, import_id: str) -> MarketDataImportRecord | None:
        row = self._session.get(MarketDataImportRow, import_id)
        if row is None:
            return None
        return self._record_from_row(row)

    def count(
        self,
        *,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> int:
        value = self._session.scalar(
            select(func.count())
            .select_from(MarketDataImportRow)
            .where(
                *self._conditions(
                    connection_id=connection_id,
                    status=status,
                    root_import_id=root_import_id,
                    dataset_id=dataset_id,
                )
            )
        )
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
        connection_id: str | None = None,
        status: MarketDataImportStatus | None = None,
        root_import_id: str | None = None,
        dataset_id: str | None = None,
    ) -> tuple[MarketDataImportRecord, ...]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")

        rows = self._session.scalars(
            select(MarketDataImportRow)
            .where(
                *self._conditions(
                    connection_id=connection_id,
                    status=status,
                    root_import_id=root_import_id,
                    dataset_id=dataset_id,
                )
            )
            .order_by(
                MarketDataImportRow.created_at.desc(),
                MarketDataImportRow.import_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(self._record_from_row(row) for row in rows)

    def get_latest_successful_version(
        self,
        root_import_id: str,
    ) -> MarketDataImportRecord | None:
        row = self._session.scalar(
            select(MarketDataImportRow)
            .where(
                MarketDataImportRow.root_import_id == root_import_id,
                MarketDataImportRow.status == MarketDataImportStatus.SUCCEEDED.value,
                MarketDataImportRow.version_number.is_not(None),
            )
            .order_by(
                MarketDataImportRow.version_number.desc(),
                MarketDataImportRow.created_at.desc(),
                MarketDataImportRow.import_id.desc(),
            )
            .limit(1)
        )
        return self._record_from_row(row) if row is not None else None

    @staticmethod
    def _record_from_row(row: MarketDataImportRow) -> MarketDataImportRecord:
        payload = MarketDataImportRecord.model_validate_json(row.payload_json).model_dump()
        payload.update(
            {
                "operation": MarketDataImportOperation(row.operation),
                "source_dataset_id": row.source_dataset_id,
                "root_import_id": row.root_import_id,
                "parent_import_id": row.parent_import_id,
                "version_number": row.version_number,
                "content_changed": row.content_changed,
            }
        )
        return MarketDataImportRecord.model_validate(payload)

    @staticmethod
    def _conditions(
        *,
        connection_id: str | None,
        status: MarketDataImportStatus | None,
        root_import_id: str | None,
        dataset_id: str | None,
    ) -> tuple[ColumnElement[bool], ...]:
        conditions: list[ColumnElement[bool]] = []
        if connection_id is not None:
            conditions.append(MarketDataImportRow.connection_id == connection_id)
        if status is not None:
            conditions.append(MarketDataImportRow.status == status.value)
        if root_import_id is not None:
            conditions.append(MarketDataImportRow.root_import_id == root_import_id)
        if dataset_id is not None:
            conditions.append(MarketDataImportRow.dataset_id == dataset_id)
        return tuple(conditions)
