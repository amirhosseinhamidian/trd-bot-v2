import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from trd_bot.domain.market_data import TradingPair


class PositionSide(StrEnum):
    """Possible simulated position sides."""

    LONG = "long"
    SHORT = "short"


class BacktestEventType(StrEnum):
    """Types of events generated during a backtest."""

    POSITION_OPENED = "position_opened"
    POSITION_CLOSED = "position_closed"


class ExitReason(StrEnum):
    """Reasons for closing a simulated position."""

    OPPOSITE_SIGNAL = "opposite_signal"
    END_OF_DATA = "end_of_data"


class BacktestConfig(BaseModel):
    """Configuration for an offline research backtest."""

    model_config = ConfigDict(frozen=True)

    starting_balance: Decimal = Field(gt=0)
    allocation_fraction: Decimal = Field(gt=0, le=1)
    fee_rate: Decimal = Field(ge=0, lt=1)
    slippage_rate: Decimal = Field(ge=0, lt=1)


class BacktestEvent(BaseModel):
    """An immutable event produced by a backtest."""

    model_config = ConfigDict(frozen=True)

    event_id: str = Field(
        pattern=r"^event-[a-f0-9]{16}$",
    )
    sequence_number: int = Field(ge=1)

    event_type: BacktestEventType
    timestamp: datetime

    pair: TradingPair
    side: PositionSide

    price: Decimal = Field(gt=0)
    quantity: Decimal = Field(gt=0)

    signal_id: str | None = Field(
        default=None,
        pattern=r"^signal-[a-f0-9]{16}$",
    )
    exit_reason: ExitReason | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.event_type == BacktestEventType.POSITION_OPENED and self.signal_id is None:
            raise ValueError("position-opened event requires a signal ID")

        if self.event_type == BacktestEventType.POSITION_OPENED and self.exit_reason is not None:
            raise ValueError("position-opened event cannot have an exit reason")

        if self.event_type == BacktestEventType.POSITION_CLOSED and self.exit_reason is None:
            raise ValueError("position-closed event requires an exit reason")

        return self


def build_backtest_event_id(
    *,
    run_id: str,
    sequence_number: int,
    event_type: BacktestEventType,
    timestamp: datetime,
) -> str:
    """Build a deterministic backtest event identifier."""

    identity = "::".join(
        [
            run_id,
            str(sequence_number),
            event_type.value,
            timestamp.isoformat(),
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"event-{digest[:16]}"
