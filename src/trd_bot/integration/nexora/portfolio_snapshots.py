from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, TypeVar, cast

from pydantic import JsonValue
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import InstrumentedAttribute, Session

from trd_bot.db.models import (
    DecisionPortfolioIntelligenceRow,
    PortfolioTimelineEventRow,
    SimulatedPortfolioRow,
    SimulatedPositionRow,
)
from trd_bot.integration.nexora.snapshots import (
    SnapshotProtocolError,
    SnapshotRecord,
    normalize_database_timestamp,
)

PAPER_SHADOW_PORTFOLIO: Final = "paper_shadow_portfolio"
PAPER_SHADOW_POSITION: Final = "paper_shadow_position"
PORTFOLIO_INTELLIGENCE: Final = "portfolio_intelligence"
SIMULATION_OUTCOME: Final = "simulation_outcome"
PORTFOLIO_SNAPSHOT_RESOURCE_TYPES: Final = (
    PAPER_SHADOW_PORTFOLIO,
    PAPER_SHADOW_POSITION,
    PORTFOLIO_INTELLIGENCE,
    SIMULATION_OUTCOME,
)
RESOURCE_SCHEMA_VERSIONS: Final = {
    PAPER_SHADOW_PORTFOLIO: "trd-bot-paper-shadow-portfolio-v1",
    PAPER_SHADOW_POSITION: "trd-bot-paper-shadow-position-v1",
    PORTFOLIO_INTELLIGENCE: "trd-bot-portfolio-intelligence-v1",
    SIMULATION_OUTCOME: "trd-bot-simulation-outcome-v1",
}
_OUTCOME_EVENT_TYPES: Final = ("position_closed", "portfolio_completed")
_RowT = TypeVar("_RowT")


def _canonical_timestamp(value: datetime) -> str:
    normalized = normalize_database_timestamp(value)
    return normalized.isoformat(timespec="microseconds").replace("+00:00", "Z")


def _sort_key(observed_at: datetime, resource_id: str) -> str:
    return f"{_canonical_timestamp(observed_at)}|{resource_id}"


def _parse_boundary(value: str) -> datetime:
    try:
        boundary = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise SnapshotProtocolError("portfolio snapshot boundary is invalid") from error
    normalized = boundary.astimezone(UTC)
    if _canonical_timestamp(normalized) != value:
        raise SnapshotProtocolError("portfolio snapshot boundary is not canonical")
    return normalized


def _parse_after_sort_key(value: str) -> tuple[datetime, str]:
    timestamp, separator, resource_id = value.partition("|")
    if not separator or not resource_id:
        raise SnapshotProtocolError("portfolio snapshot sort key is invalid")
    return _parse_boundary(timestamp), resource_id


def _loaded_payload(payload_json: str) -> dict[str, JsonValue]:
    loaded = json.loads(payload_json)
    if not isinstance(loaded, dict):
        raise SnapshotProtocolError("portfolio snapshot payload must be an object")
    return cast(dict[str, JsonValue], loaded)


def _decimal(value: Decimal) -> str:
    return format(value, "f")


class PortfolioSnapshotResourceReader:
    """Read the four fail-closed Paper/Shadow portfolio snapshot resources."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def capture_boundary(self, *, resource_type: str, captured_at: datetime) -> str:
        self._require_resource_type(resource_type)
        return _canonical_timestamp(captured_at)

    def list_records(
        self,
        *,
        resource_type: str,
        boundary_key: str,
        after_sort_key: str | None,
        limit: int,
    ) -> Sequence[SnapshotRecord]:
        self._require_resource_type(resource_type)
        if limit < 1:
            raise SnapshotProtocolError("portfolio snapshot read limit must be positive")
        boundary = _parse_boundary(boundary_key)
        after = None if after_sort_key is None else _parse_after_sort_key(after_sort_key)
        if resource_type == PAPER_SHADOW_PORTFOLIO:
            portfolios = self._page_rows(
                SimulatedPortfolioRow,
                timestamp=SimulatedPortfolioRow.updated_at,
                identity=SimulatedPortfolioRow.portfolio_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.portfolio_id,
                    observed_at=row.updated_at,
                    payload=self._portfolio_payload(row),
                )
                for row in portfolios
            )
        if resource_type == PAPER_SHADOW_POSITION:
            positions = self._page_rows(
                SimulatedPositionRow,
                timestamp=SimulatedPositionRow.current_at,
                identity=SimulatedPositionRow.position_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.position_id,
                    observed_at=row.current_at,
                    payload=self._position_payload(row),
                )
                for row in positions
            )
        if resource_type == PORTFOLIO_INTELLIGENCE:
            intelligence_records = self._page_rows(
                DecisionPortfolioIntelligenceRow,
                timestamp=DecisionPortfolioIntelligenceRow.analyzed_at,
                identity=DecisionPortfolioIntelligenceRow.evaluation_id,
                boundary=boundary,
                after=after,
                limit=limit,
            )
            return tuple(
                self._record(
                    resource_type=resource_type,
                    resource_id=row.evaluation_id,
                    observed_at=row.analyzed_at,
                    payload=self._intelligence_payload(row),
                )
                for row in intelligence_records
            )
        outcomes = self._page_rows(
            PortfolioTimelineEventRow,
            timestamp=PortfolioTimelineEventRow.occurred_at,
            identity=PortfolioTimelineEventRow.event_id,
            boundary=boundary,
            after=after,
            limit=limit,
            event_types=_OUTCOME_EVENT_TYPES,
        )
        return tuple(
            self._record(
                resource_type=resource_type,
                resource_id=row.event_id,
                observed_at=row.occurred_at,
                payload=self._outcome_payload(row),
            )
            for row in outcomes
        )

    def _record(
        self,
        *,
        resource_type: str,
        resource_id: str,
        observed_at: datetime,
        payload: dict[str, JsonValue],
    ) -> SnapshotRecord:
        normalized = normalize_database_timestamp(observed_at)
        schema_version = RESOURCE_SCHEMA_VERSIONS[resource_type]
        return SnapshotRecord(
            resource_type=resource_type,
            resource_id=resource_id,
            resource_schema_version=schema_version,
            observed_at=normalized,
            sort_key=_sort_key(normalized, resource_id),
            payload={"resource_schema_version": schema_version, **payload},
        )

    @staticmethod
    def _portfolio_payload(row: SimulatedPortfolioRow) -> dict[str, JsonValue]:
        return {
            "portfolio_id": row.portfolio_id,
            "mode": row.mode,
            "status": row.status,
            "dataset_id": row.dataset_id,
            "created_at": _canonical_timestamp(row.created_at),
            "updated_at": _canonical_timestamp(row.updated_at),
            "starting_cash": _decimal(row.starting_cash),
            "cash": _decimal(row.cash),
            "equity": _decimal(row.equity),
            "fee_rate": _decimal(row.fee_rate),
            "fees_paid": _decimal(row.fees_paid),
            "realized_pnl": _decimal(row.realized_pnl),
            "unrealized_pnl": _decimal(row.unrealized_pnl),
            "offline_only": True,
            "external_order_submission_allowed": False,
        }

    @staticmethod
    def _position_payload(row: SimulatedPositionRow) -> dict[str, JsonValue]:
        return {
            "position_id": row.position_id,
            "portfolio_id": row.portfolio_id,
            "base_asset": row.base_asset,
            "quote_asset": row.quote_asset,
            "market_type": row.market_type,
            "side": row.side,
            "status": row.status,
            "quantity": _decimal(row.quantity),
            "entry_price": _decimal(row.entry_price),
            "opened_at": _canonical_timestamp(row.opened_at),
            "current_price": _decimal(row.current_price),
            "current_at": _canonical_timestamp(row.current_at),
            "reserved_notional": _decimal(row.reserved_notional),
            "entry_fee": _decimal(row.entry_fee),
            "unrealized_pnl": _decimal(row.unrealized_pnl),
            "exit_price": None if row.exit_price is None else _decimal(row.exit_price),
            "closed_at": None if row.closed_at is None else _canonical_timestamp(row.closed_at),
            "exit_fee": _decimal(row.exit_fee),
            "gross_realized_pnl": _decimal(row.gross_realized_pnl),
            "realized_pnl": _decimal(row.realized_pnl),
            "offline_only": True,
            "external_order_submission_allowed": False,
        }

    @staticmethod
    def _intelligence_payload(
        row: DecisionPortfolioIntelligenceRow,
    ) -> dict[str, JsonValue]:
        return {
            "evaluation_id": row.evaluation_id,
            "outcome_id": row.outcome_id,
            "record_schema_version": row.schema_version,
            "risk_gate_checksum": row.risk_gate_checksum,
            "policy_version": row.policy_version,
            "policy_checksum": row.policy_checksum,
            "disposition": row.disposition,
            "recommendation": row.recommendation,
            "has_analysis": row.has_analysis,
            "snapshot_id": row.snapshot_id,
            "candidate_id": row.candidate_id,
            "analyzed_at": _canonical_timestamp(row.analyzed_at),
            "offline_only": row.offline_only,
            "external_order_submission_allowed": row.external_order_submission_allowed,
            "record_checksum": row.record_checksum,
            "record": _loaded_payload(row.payload_json),
        }

    @staticmethod
    def _outcome_payload(row: PortfolioTimelineEventRow) -> dict[str, JsonValue]:
        return {
            "event_id": row.event_id,
            "portfolio_id": row.portfolio_id,
            "sequence_number": row.sequence_number,
            "event_type": row.event_type,
            "occurred_at": _canonical_timestamp(row.occurred_at),
            "equity": _decimal(row.equity),
            "position_id": row.position_id,
            "outcome": _loaded_payload(row.payload_json),
            "offline_only": True,
            "external_order_submission_allowed": False,
        }

    def _page_rows(
        self,
        model: type[_RowT],
        *,
        timestamp: InstrumentedAttribute[datetime],
        identity: InstrumentedAttribute[str],
        boundary: datetime,
        after: tuple[datetime, str] | None,
        limit: int,
        event_types: tuple[str, ...] | None = None,
    ) -> Sequence[_RowT]:
        statement = select(model).where(timestamp <= boundary)
        if event_types is not None:
            statement = statement.where(PortfolioTimelineEventRow.event_type.in_(event_types))
        if after is not None:
            after_timestamp, after_identity = after
            statement = statement.where(
                or_(
                    timestamp > after_timestamp,
                    and_(timestamp == after_timestamp, identity > after_identity),
                )
            )
        return self._session.scalars(
            statement.order_by(timestamp.asc(), identity.asc()).limit(limit)
        ).all()

    @staticmethod
    def _require_resource_type(resource_type: str) -> None:
        if resource_type not in PORTFOLIO_SNAPSHOT_RESOURCE_TYPES:
            raise SnapshotProtocolError("snapshot resource type is not available in this stage")
