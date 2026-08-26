import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.backtesting import PositionSide
from trd_bot.backtesting.performance import quantize_money
from trd_bot.domain.market_data import TradingPair


class SimulationMode(StrEnum):
    """Offline execution mode; neither mode can submit an external order."""

    PAPER = "paper"
    SHADOW = "shadow"


class PortfolioStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"


class PositionStatus(StrEnum):
    OPEN = "open"
    CLOSED = "closed"


class PortfolioEventType(StrEnum):
    PORTFOLIO_CREATED = "portfolio_created"
    POSITION_OPENED = "position_opened"
    POSITION_MARKED = "position_marked"
    POSITION_CLOSED = "position_closed"
    PORTFOLIO_COMPLETED = "portfolio_completed"


def _utc_timestamp(value: datetime, *, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value.astimezone(UTC)


def _digest(*parts: object) -> str:
    identity = "::".join(str(part) for part in parts)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]


def build_portfolio_id(
    *,
    mode: SimulationMode,
    dataset_id: str,
    created_at: datetime,
    starting_cash: Decimal,
    fee_rate: Decimal,
) -> str:
    digest = _digest(
        mode.value,
        dataset_id,
        created_at.isoformat(),
        starting_cash,
        fee_rate,
    )
    return f"portfolio-{digest}"


def build_position_id(
    *,
    portfolio_id: str,
    position_number: int,
    opened_at: datetime,
) -> str:
    return f"position-{_digest(portfolio_id, position_number, opened_at.isoformat())}"


def build_portfolio_event_id(
    *,
    portfolio_id: str,
    sequence_number: int,
    event_type: PortfolioEventType,
    occurred_at: datetime,
) -> str:
    digest = _digest(
        portfolio_id,
        sequence_number,
        event_type.value,
        occurred_at.isoformat(),
    )
    return f"portfolio-event-{digest}"


class SimulatedPosition(BaseModel):
    """One hypothetical position backed only by historical data."""

    model_config = ConfigDict(frozen=True)

    position_id: str = Field(pattern=r"^position-[a-f0-9]{16}$")
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    pair: TradingPair
    side: PositionSide
    status: PositionStatus
    quantity: Decimal = Field(gt=0)
    entry_price: Decimal = Field(gt=0)
    opened_at: datetime
    current_price: Decimal = Field(gt=0)
    current_at: datetime
    reserved_notional: Decimal = Field(gt=0)
    entry_fee: Decimal = Field(ge=0)
    unrealized_pnl: Decimal = Decimal("0")
    exit_price: Decimal | None = Field(default=None, gt=0)
    closed_at: datetime | None = None
    exit_fee: Decimal = Field(default=Decimal("0"), ge=0)
    gross_realized_pnl: Decimal = Decimal("0")
    realized_pnl: Decimal = Decimal("0")

    @field_validator("opened_at", "current_at", "closed_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _utc_timestamp(value, field_name="position timestamp")

    @model_validator(mode="after")
    def validate_position(self) -> Self:
        if self.current_at < self.opened_at:
            raise ValueError("position mark time cannot be before open time")

        if self.side is PositionSide.LONG:
            expected_unrealized = quantize_money(
                (self.current_price - self.entry_price) * self.quantity
            )
        else:
            expected_unrealized = quantize_money(
                (self.entry_price - self.current_price) * self.quantity
            )

        if self.status is PositionStatus.OPEN:
            if self.exit_price is not None or self.closed_at is not None:
                raise ValueError("an open position cannot have exit details")
            if self.exit_fee != 0 or self.gross_realized_pnl != 0 or self.realized_pnl != 0:
                raise ValueError("an open position cannot have realized results")
            if self.unrealized_pnl != expected_unrealized:
                raise ValueError("position unrealized PnL is inconsistent with its mark")
            return self

        if self.exit_price is None or self.closed_at is None:
            raise ValueError("a closed position requires exit details")
        if self.closed_at <= self.opened_at:
            raise ValueError("position close time must be after open time")
        if self.current_at != self.closed_at or self.current_price != self.exit_price:
            raise ValueError("a closed position mark must match its exit")
        if self.unrealized_pnl != 0:
            raise ValueError("a closed position cannot have unrealized PnL")
        if self.realized_pnl != quantize_money(
            self.gross_realized_pnl - self.entry_fee - self.exit_fee
        ):
            raise ValueError("position realized PnL is inconsistent with gross PnL and fees")
        return self


class PortfolioTimelineEvent(BaseModel):
    """Auditable event in an offline simulated portfolio lifecycle."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(pattern=r"^portfolio-event-[a-f0-9]{16}$")
    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    sequence_number: int = Field(ge=1)
    event_type: PortfolioEventType
    occurred_at: datetime
    equity: Decimal
    position_id: str | None = Field(default=None, pattern=r"^position-[a-f0-9]{16}$")
    price: Decimal | None = Field(default=None, gt=0)
    quantity: Decimal | None = Field(default=None, gt=0)
    realized_pnl: Decimal | None = None

    @field_validator("occurred_at")
    @classmethod
    def occurred_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        return _utc_timestamp(value, field_name="event time")

    @model_validator(mode="after")
    def validate_event_details(self) -> Self:
        is_position_event = self.event_type in {
            PortfolioEventType.POSITION_OPENED,
            PortfolioEventType.POSITION_MARKED,
            PortfolioEventType.POSITION_CLOSED,
        }
        has_position_details = (
            self.position_id is not None and self.price is not None and self.quantity is not None
        )
        if is_position_event != has_position_details:
            raise ValueError("position event details are inconsistent with event type")
        if self.event_type is PortfolioEventType.POSITION_CLOSED:
            if self.realized_pnl is None:
                raise ValueError("a position-closed event requires realized PnL")
        elif self.realized_pnl is not None:
            raise ValueError("only a position-closed event can contain realized PnL")
        return self


class SimulatedPortfolio(BaseModel):
    """Immutable accounting snapshot for paper or shadow research."""

    model_config = ConfigDict(frozen=True)

    portfolio_id: str = Field(pattern=r"^portfolio-[a-f0-9]{16}$")
    mode: SimulationMode
    status: PortfolioStatus
    dataset_id: str = Field(min_length=1, max_length=100)
    created_at: datetime
    updated_at: datetime
    starting_cash: Decimal = Field(gt=0)
    cash: Decimal = Field(ge=0)
    equity: Decimal
    fee_rate: Decimal = Field(ge=0, lt=1)
    fees_paid: Decimal = Field(ge=0)
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    positions: tuple[SimulatedPosition, ...] = ()
    timeline: tuple[PortfolioTimelineEvent, ...]

    @field_validator("created_at", "updated_at")
    @classmethod
    def timestamps_must_be_timezone_aware(cls, value: datetime) -> datetime:
        return _utc_timestamp(value, field_name="portfolio timestamp")

    @field_validator("dataset_id")
    @classmethod
    def normalize_dataset_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("dataset ID cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_accounting(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("portfolio update time cannot be before creation time")
        if not self.timeline:
            raise ValueError("portfolio timeline cannot be empty")
        if self.timeline[0].event_type is not PortfolioEventType.PORTFOLIO_CREATED:
            raise ValueError("portfolio timeline must start with portfolio creation")

        for expected_sequence, event in enumerate(self.timeline, start=1):
            if event.portfolio_id != self.portfolio_id:
                raise ValueError("timeline event belongs to another portfolio")
            if event.sequence_number != expected_sequence:
                raise ValueError("portfolio timeline sequence must be continuous")
        if self.timeline[-1].occurred_at != self.updated_at:
            raise ValueError("latest timeline event must match portfolio update time")
        if self.timeline[-1].equity != self.equity:
            raise ValueError("latest timeline event must match portfolio equity")

        position_ids = [position.position_id for position in self.positions]
        if len(position_ids) != len(set(position_ids)):
            raise ValueError("portfolio position IDs must be unique")
        if any(position.portfolio_id != self.portfolio_id for position in self.positions):
            raise ValueError("position belongs to another portfolio")

        open_positions = tuple(
            position for position in self.positions if position.status is PositionStatus.OPEN
        )
        if len(open_positions) > 1:
            raise ValueError("portfolio cannot have more than one open position")
        if self.status is PortfolioStatus.COMPLETED and open_positions:
            raise ValueError("a completed portfolio cannot have an open position")
        if self.status is PortfolioStatus.COMPLETED:
            if self.timeline[-1].event_type is not PortfolioEventType.PORTFOLIO_COMPLETED:
                raise ValueError("a completed portfolio requires a completion event")
        elif self.timeline[-1].event_type is PortfolioEventType.PORTFOLIO_COMPLETED:
            raise ValueError("an active portfolio cannot have a completion event")

        expected_fees = quantize_money(
            sum(
                (position.entry_fee + position.exit_fee for position in self.positions),
                start=Decimal("0"),
            )
        )
        if self.fees_paid != expected_fees:
            raise ValueError("portfolio fees are inconsistent with positions")

        closed_realized = quantize_money(
            sum(
                (
                    position.realized_pnl
                    for position in self.positions
                    if position.status is PositionStatus.CLOSED
                ),
                start=Decimal("0"),
            )
        )
        open_unrealized = quantize_money(
            sum(
                (position.unrealized_pnl for position in open_positions),
                start=Decimal("0"),
            )
        )
        if self.realized_pnl != closed_realized:
            raise ValueError("portfolio realized PnL is inconsistent with positions")
        if self.unrealized_pnl != open_unrealized:
            raise ValueError("portfolio unrealized PnL is inconsistent with positions")

        open_commitment = quantize_money(
            sum(
                (position.reserved_notional + position.entry_fee for position in open_positions),
                start=Decimal("0"),
            )
        )
        expected_cash = quantize_money(self.starting_cash + closed_realized - open_commitment)
        expected_equity = quantize_money(
            self.cash
            + sum(
                (
                    position.reserved_notional + position.unrealized_pnl
                    for position in open_positions
                ),
                start=Decimal("0"),
            )
        )
        if self.cash != expected_cash:
            raise ValueError("portfolio cash is inconsistent with positions")
        if self.equity != expected_equity:
            raise ValueError("portfolio equity is inconsistent with positions")
        return self


class SimulatedPortfolioRepository(Protocol):
    """Persistence contract for simulated portfolio aggregates and views."""

    def save(self, portfolio: SimulatedPortfolio) -> SimulatedPortfolio: ...

    def get(self, portfolio_id: str) -> SimulatedPortfolio | None: ...

    def get_position(self, position_id: str) -> SimulatedPosition | None: ...

    def count(self) -> int: ...

    def count_positions(self, portfolio_id: str) -> int: ...

    def count_timeline(self, portfolio_id: str) -> int: ...

    def list_page(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPortfolio, ...]: ...

    def list_positions(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[SimulatedPosition, ...]: ...

    def list_timeline(
        self,
        *,
        portfolio_id: str,
        limit: int,
        offset: int,
    ) -> tuple[PortfolioTimelineEvent, ...]: ...


class SimulatedPortfolioLedger:
    """Pure state transitions for an offline historical simulation."""

    def create(
        self,
        *,
        mode: SimulationMode,
        dataset_id: str,
        starting_cash: Decimal,
        fee_rate: Decimal = Decimal("0"),
        created_at: datetime | None = None,
    ) -> SimulatedPortfolio:
        timestamp = _utc_timestamp(created_at or datetime.now(UTC), field_name="creation time")
        normalized_dataset_id = dataset_id.strip()
        portfolio_id = build_portfolio_id(
            mode=mode,
            dataset_id=normalized_dataset_id,
            created_at=timestamp,
            starting_cash=starting_cash,
            fee_rate=fee_rate,
        )
        equity = quantize_money(starting_cash)
        event = self._event(
            portfolio_id=portfolio_id,
            sequence_number=1,
            event_type=PortfolioEventType.PORTFOLIO_CREATED,
            occurred_at=timestamp,
            equity=equity,
        )
        return SimulatedPortfolio(
            portfolio_id=portfolio_id,
            mode=mode,
            status=PortfolioStatus.ACTIVE,
            dataset_id=normalized_dataset_id,
            created_at=timestamp,
            updated_at=timestamp,
            starting_cash=quantize_money(starting_cash),
            cash=quantize_money(starting_cash),
            equity=equity,
            fee_rate=fee_rate,
            fees_paid=Decimal("0"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            timeline=(event,),
        )

    def open_position(
        self,
        portfolio: SimulatedPortfolio,
        *,
        pair: TradingPair,
        side: PositionSide,
        price: Decimal,
        quantity: Decimal,
        occurred_at: datetime,
    ) -> SimulatedPortfolio:
        self._require_active(portfolio)
        if any(position.status is PositionStatus.OPEN for position in portfolio.positions):
            raise ValueError("cannot open a position while another position is open")
        timestamp = self._next_timestamp(portfolio, occurred_at)
        if price <= 0 or quantity <= 0:
            raise ValueError("position price and quantity must be greater than zero")

        notional = quantize_money(price * quantity)
        entry_fee = quantize_money(notional * portfolio.fee_rate)
        commitment = quantize_money(notional + entry_fee)
        if commitment > portfolio.cash:
            raise ValueError("portfolio has insufficient simulated cash")

        position = SimulatedPosition(
            position_id=build_position_id(
                portfolio_id=portfolio.portfolio_id,
                position_number=len(portfolio.positions) + 1,
                opened_at=timestamp,
            ),
            portfolio_id=portfolio.portfolio_id,
            pair=pair,
            side=side,
            status=PositionStatus.OPEN,
            quantity=quantity,
            entry_price=price,
            opened_at=timestamp,
            current_price=price,
            current_at=timestamp,
            reserved_notional=notional,
            entry_fee=entry_fee,
        )
        cash = quantize_money(portfolio.cash - commitment)
        equity = quantize_money(cash + notional)
        event = self._position_event(
            portfolio=portfolio,
            event_type=PortfolioEventType.POSITION_OPENED,
            occurred_at=timestamp,
            equity=equity,
            position=position,
            price=price,
        )
        return SimulatedPortfolio.model_validate(
            portfolio.model_copy(
                update={
                    "updated_at": timestamp,
                    "cash": cash,
                    "equity": equity,
                    "fees_paid": quantize_money(portfolio.fees_paid + entry_fee),
                    "positions": (*portfolio.positions, position),
                    "timeline": (*portfolio.timeline, event),
                }
            ).model_dump()
        )

    def mark_to_market(
        self,
        portfolio: SimulatedPortfolio,
        *,
        position_id: str,
        price: Decimal,
        occurred_at: datetime,
    ) -> SimulatedPortfolio:
        self._require_active(portfolio)
        index, position = self._open_position(portfolio, position_id)
        timestamp = self._next_timestamp(portfolio, occurred_at)
        if price <= 0:
            raise ValueError("mark price must be greater than zero")
        unrealized_pnl = self._gross_pnl(position=position, price=price)
        marked = position.model_copy(
            update={
                "current_price": price,
                "current_at": timestamp,
                "unrealized_pnl": unrealized_pnl,
            }
        )
        positions = list(portfolio.positions)
        positions[index] = marked
        equity = quantize_money(portfolio.cash + marked.reserved_notional + unrealized_pnl)
        event = self._position_event(
            portfolio=portfolio,
            event_type=PortfolioEventType.POSITION_MARKED,
            occurred_at=timestamp,
            equity=equity,
            position=marked,
            price=price,
        )
        return SimulatedPortfolio.model_validate(
            portfolio.model_copy(
                update={
                    "updated_at": timestamp,
                    "equity": equity,
                    "unrealized_pnl": unrealized_pnl,
                    "positions": tuple(positions),
                    "timeline": (*portfolio.timeline, event),
                }
            ).model_dump()
        )

    def close_position(
        self,
        portfolio: SimulatedPortfolio,
        *,
        position_id: str,
        price: Decimal,
        occurred_at: datetime,
    ) -> SimulatedPortfolio:
        self._require_active(portfolio)
        index, position = self._open_position(portfolio, position_id)
        timestamp = self._next_timestamp(portfolio, occurred_at)
        if price <= 0:
            raise ValueError("exit price must be greater than zero")
        gross_pnl = self._gross_pnl(position=position, price=price)
        exit_fee = quantize_money(price * position.quantity * portfolio.fee_rate)
        realized_pnl = quantize_money(gross_pnl - position.entry_fee - exit_fee)
        closed = position.model_copy(
            update={
                "status": PositionStatus.CLOSED,
                "current_price": price,
                "current_at": timestamp,
                "unrealized_pnl": Decimal("0"),
                "exit_price": price,
                "closed_at": timestamp,
                "exit_fee": exit_fee,
                "gross_realized_pnl": gross_pnl,
                "realized_pnl": realized_pnl,
            }
        )
        positions = list(portfolio.positions)
        positions[index] = closed
        cash = quantize_money(portfolio.cash + position.reserved_notional + gross_pnl - exit_fee)
        cumulative_realized = quantize_money(portfolio.realized_pnl + realized_pnl)
        event = self._position_event(
            portfolio=portfolio,
            event_type=PortfolioEventType.POSITION_CLOSED,
            occurred_at=timestamp,
            equity=cash,
            position=closed,
            price=price,
            realized_pnl=realized_pnl,
        )
        return SimulatedPortfolio.model_validate(
            portfolio.model_copy(
                update={
                    "updated_at": timestamp,
                    "cash": cash,
                    "equity": cash,
                    "fees_paid": quantize_money(portfolio.fees_paid + exit_fee),
                    "realized_pnl": cumulative_realized,
                    "unrealized_pnl": Decimal("0"),
                    "positions": tuple(positions),
                    "timeline": (*portfolio.timeline, event),
                }
            ).model_dump()
        )

    def complete(
        self,
        portfolio: SimulatedPortfolio,
        *,
        occurred_at: datetime,
    ) -> SimulatedPortfolio:
        self._require_active(portfolio)
        if any(position.status is PositionStatus.OPEN for position in portfolio.positions):
            raise ValueError("cannot complete a portfolio with an open position")
        timestamp = self._next_timestamp(portfolio, occurred_at)
        event = self._event(
            portfolio_id=portfolio.portfolio_id,
            sequence_number=len(portfolio.timeline) + 1,
            event_type=PortfolioEventType.PORTFOLIO_COMPLETED,
            occurred_at=timestamp,
            equity=portfolio.equity,
        )
        return SimulatedPortfolio.model_validate(
            portfolio.model_copy(
                update={
                    "status": PortfolioStatus.COMPLETED,
                    "updated_at": timestamp,
                    "timeline": (*portfolio.timeline, event),
                }
            ).model_dump()
        )

    @staticmethod
    def _require_active(portfolio: SimulatedPortfolio) -> None:
        if portfolio.status is not PortfolioStatus.ACTIVE:
            raise ValueError("portfolio is already completed")

    @staticmethod
    def _next_timestamp(portfolio: SimulatedPortfolio, value: datetime) -> datetime:
        timestamp = _utc_timestamp(value, field_name="transition time")
        if timestamp <= portfolio.updated_at:
            raise ValueError("portfolio transition time must move forward")
        return timestamp

    @staticmethod
    def _open_position(
        portfolio: SimulatedPortfolio,
        position_id: str,
    ) -> tuple[int, SimulatedPosition]:
        for index, position in enumerate(portfolio.positions):
            if position.position_id == position_id and position.status is PositionStatus.OPEN:
                return index, position
        raise ValueError("open simulated position was not found")

    @staticmethod
    def _gross_pnl(*, position: SimulatedPosition, price: Decimal) -> Decimal:
        if position.side is PositionSide.LONG:
            return quantize_money((price - position.entry_price) * position.quantity)
        return quantize_money((position.entry_price - price) * position.quantity)

    @staticmethod
    def _event(
        *,
        portfolio_id: str,
        sequence_number: int,
        event_type: PortfolioEventType,
        occurred_at: datetime,
        equity: Decimal,
        position_id: str | None = None,
        price: Decimal | None = None,
        quantity: Decimal | None = None,
        realized_pnl: Decimal | None = None,
    ) -> PortfolioTimelineEvent:
        return PortfolioTimelineEvent(
            event_id=build_portfolio_event_id(
                portfolio_id=portfolio_id,
                sequence_number=sequence_number,
                event_type=event_type,
                occurred_at=occurred_at,
            ),
            portfolio_id=portfolio_id,
            sequence_number=sequence_number,
            event_type=event_type,
            occurred_at=occurred_at,
            equity=equity,
            position_id=position_id,
            price=price,
            quantity=quantity,
            realized_pnl=realized_pnl,
        )

    def _position_event(
        self,
        *,
        portfolio: SimulatedPortfolio,
        event_type: PortfolioEventType,
        occurred_at: datetime,
        equity: Decimal,
        position: SimulatedPosition,
        price: Decimal,
        realized_pnl: Decimal | None = None,
    ) -> PortfolioTimelineEvent:
        return self._event(
            portfolio_id=portfolio.portfolio_id,
            sequence_number=len(portfolio.timeline) + 1,
            event_type=event_type,
            occurred_at=occurred_at,
            equity=equity,
            position_id=position.position_id,
            price=price,
            quantity=position.quantity,
            realized_pnl=realized_pnl,
        )
