from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from trd_bot.db.models import (
    PortfolioTimelineEventRow,
    SimulatedPortfolioRow,
    SimulatedPositionRow,
)
from trd_bot.paper import (
    PortfolioTimelineEvent,
    SimulatedPortfolio,
    SimulatedPosition,
)


class SqlAlchemySimulatedPortfolioRepository:
    """Persist an offline simulated portfolio aggregate with SQLAlchemy."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, portfolio: SimulatedPortfolio) -> SimulatedPortfolio:
        row = self._session.get(SimulatedPortfolioRow, portfolio.portfolio_id)

        if row is None:
            self._session.add(self._build_portfolio_row(portfolio))
        else:
            self._update_portfolio_row(row=row, portfolio=portfolio)

        try:
            self._replace_children(portfolio)
            self._session.commit()
        except IntegrityError as error:
            self._session.rollback()
            raise ValueError("simulated portfolio could not be persisted") from error

        return portfolio

    def get(self, portfolio_id: str) -> SimulatedPortfolio | None:
        row = self._session.get(SimulatedPortfolioRow, portfolio_id)

        if row is None:
            return None

        return SimulatedPortfolio.model_validate_json(row.payload_json)

    def get_position(self, position_id: str) -> SimulatedPosition | None:
        row = self._session.get(SimulatedPositionRow, position_id)

        if row is None:
            return None

        return SimulatedPosition.model_validate_json(row.payload_json)

    def count(self) -> int:
        value = self._session.scalar(select(func.count()).select_from(SimulatedPortfolioRow))
        return int(value or 0)

    def count_positions(self, portfolio_id: str) -> int:
        value = self._session.scalar(
            select(func.count())
            .select_from(SimulatedPositionRow)
            .where(SimulatedPositionRow.portfolio_id == portfolio_id)
        )
        return int(value or 0)

    def count_timeline(self, portfolio_id: str) -> int:
        value = self._session.scalar(
            select(func.count())
            .select_from(PortfolioTimelineEventRow)
            .where(PortfolioTimelineEventRow.portfolio_id == portfolio_id)
        )
        return int(value or 0)

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPortfolio, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(SimulatedPortfolioRow)
            .order_by(
                SimulatedPortfolioRow.created_at.desc(),
                SimulatedPortfolioRow.portfolio_id.desc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(SimulatedPortfolio.model_validate_json(row.payload_json) for row in rows)

    def list_positions(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPosition, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(SimulatedPositionRow)
            .where(SimulatedPositionRow.portfolio_id == portfolio_id)
            .order_by(
                SimulatedPositionRow.opened_at.asc(),
                SimulatedPositionRow.position_id.asc(),
            )
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(SimulatedPosition.model_validate_json(row.payload_json) for row in rows)

    def list_timeline(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[PortfolioTimelineEvent, ...]:
        self._validate_pagination(limit=limit, offset=offset)

        rows = self._session.scalars(
            select(PortfolioTimelineEventRow)
            .where(PortfolioTimelineEventRow.portfolio_id == portfolio_id)
            .order_by(PortfolioTimelineEventRow.sequence_number.asc())
            .offset(offset)
            .limit(limit)
        ).all()

        return tuple(PortfolioTimelineEvent.model_validate_json(row.payload_json) for row in rows)

    def _replace_children(self, portfolio: SimulatedPortfolio) -> None:
        self._session.execute(
            delete(PortfolioTimelineEventRow).where(
                PortfolioTimelineEventRow.portfolio_id == portfolio.portfolio_id
            )
        )
        self._session.execute(
            delete(SimulatedPositionRow).where(
                SimulatedPositionRow.portfolio_id == portfolio.portfolio_id
            )
        )

        self._session.add_all(
            [self._build_position_row(position) for position in portfolio.positions]
        )
        self._session.add_all([self._build_timeline_row(event) for event in portfolio.timeline])

    @staticmethod
    def _build_portfolio_row(portfolio: SimulatedPortfolio) -> SimulatedPortfolioRow:
        return SimulatedPortfolioRow(
            portfolio_id=portfolio.portfolio_id,
            mode=portfolio.mode.value,
            status=portfolio.status.value,
            dataset_id=portfolio.dataset_id,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
            starting_cash=portfolio.starting_cash,
            cash=portfolio.cash,
            equity=portfolio.equity,
            fee_rate=portfolio.fee_rate,
            fees_paid=portfolio.fees_paid,
            realized_pnl=portfolio.realized_pnl,
            unrealized_pnl=portfolio.unrealized_pnl,
            payload_json=portfolio.model_dump_json(),
        )

    @staticmethod
    def _update_portfolio_row(
        *,
        row: SimulatedPortfolioRow,
        portfolio: SimulatedPortfolio,
    ) -> None:
        row.mode = portfolio.mode.value
        row.status = portfolio.status.value
        row.dataset_id = portfolio.dataset_id
        row.created_at = portfolio.created_at
        row.updated_at = portfolio.updated_at
        row.starting_cash = portfolio.starting_cash
        row.cash = portfolio.cash
        row.equity = portfolio.equity
        row.fee_rate = portfolio.fee_rate
        row.fees_paid = portfolio.fees_paid
        row.realized_pnl = portfolio.realized_pnl
        row.unrealized_pnl = portfolio.unrealized_pnl
        row.payload_json = portfolio.model_dump_json()

    @staticmethod
    def _build_position_row(position: SimulatedPosition) -> SimulatedPositionRow:
        return SimulatedPositionRow(
            position_id=position.position_id,
            portfolio_id=position.portfolio_id,
            base_asset=position.pair.base_asset,
            quote_asset=position.pair.quote_asset,
            market_type=position.pair.market_type.value,
            side=position.side.value,
            status=position.status.value,
            quantity=position.quantity,
            entry_price=position.entry_price,
            opened_at=position.opened_at,
            current_price=position.current_price,
            current_at=position.current_at,
            reserved_notional=position.reserved_notional,
            entry_fee=position.entry_fee,
            unrealized_pnl=position.unrealized_pnl,
            exit_price=position.exit_price,
            closed_at=position.closed_at,
            exit_fee=position.exit_fee,
            gross_realized_pnl=position.gross_realized_pnl,
            realized_pnl=position.realized_pnl,
            payload_json=position.model_dump_json(),
        )

    @staticmethod
    def _build_timeline_row(event: PortfolioTimelineEvent) -> PortfolioTimelineEventRow:
        return PortfolioTimelineEventRow(
            event_id=event.event_id,
            portfolio_id=event.portfolio_id,
            sequence_number=event.sequence_number,
            event_type=event.event_type.value,
            occurred_at=event.occurred_at,
            equity=event.equity,
            position_id=event.position_id,
            payload_json=event.model_dump_json(),
        )

    @staticmethod
    def _validate_pagination(*, limit: int, offset: int) -> None:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")
        if offset < 0:
            raise ValueError("offset cannot be negative")
