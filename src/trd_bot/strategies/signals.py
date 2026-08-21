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

from trd_bot.domain.market_data import Timeframe, TradingPair


class SignalDirection(StrEnum):
    """Possible research signal directions."""

    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class StrategyFeature(BaseModel):
    """An indicator or feature used to produce a signal."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(min_length=1, max_length=100)
    value: Decimal


class StrategySignal(BaseModel):
    """A research signal produced by a strategy."""

    model_config = ConfigDict(frozen=True)

    signal_id: str = Field(
        pattern=r"^signal-[a-f0-9]{16}$",
    )

    strategy_name: str = Field(min_length=1, max_length=100)
    strategy_version: str = Field(min_length=1, max_length=30)
    dataset_id: str = Field(min_length=1)

    pair: TradingPair
    timeframe: Timeframe

    candle_open_time: datetime
    candle_close_time: datetime
    generated_at: datetime

    direction: SignalDirection

    # Directional research score:
    # LONG: greater than 0
    # SHORT: lower than 0
    # NEUTRAL: exactly 0
    score: Decimal = Field(ge=-1, le=1)

    reason: str = Field(min_length=1, max_length=500)
    features: tuple[StrategyFeature, ...] = ()

    @field_validator(
        "candle_open_time",
        "candle_close_time",
        "generated_at",
    )
    @classmethod
    def timestamp_must_be_timezone_aware(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_signal(self) -> Self:
        if self.candle_close_time <= self.candle_open_time:
            raise ValueError("candle close time must be after open time")

        if self.direction == SignalDirection.LONG and self.score <= 0:
            raise ValueError("long signal score must be greater than zero")

        if self.direction == SignalDirection.SHORT and self.score >= 0:
            raise ValueError("short signal score must be lower than zero")

        if self.direction == SignalDirection.NEUTRAL and self.score != 0:
            raise ValueError("neutral signal score must be zero")

        return self


def build_signal_id(
    *,
    strategy_name: str,
    strategy_version: str,
    dataset_id: str,
    candle_close_time: datetime,
    direction: SignalDirection,
) -> str:
    """Build a deterministic signal identifier."""

    identity = "::".join(
        [
            strategy_name,
            strategy_version,
            dataset_id,
            candle_close_time.isoformat(),
            direction.value,
        ]
    )

    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()

    return f"signal-{digest[:16]}"
