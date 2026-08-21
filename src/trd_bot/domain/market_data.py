from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MarketType(StrEnum):
    """Supported market types."""

    SPOT = "spot"


class Timeframe(StrEnum):
    """Supported candle timeframes."""

    MINUTES_15 = "15m"
    HOUR_1 = "1h"
    HOURS_4 = "4h"
    DAY_1 = "1d"


class TradingPair(BaseModel):
    """A normalized cryptocurrency trading pair."""

    model_config = ConfigDict(frozen=True)

    base_asset: str = Field(
        min_length=2,
        max_length=15,
        pattern=r"^[A-Z0-9]+$",
    )
    quote_asset: str = Field(
        min_length=2,
        max_length=15,
        pattern=r"^[A-Z0-9]+$",
    )
    market_type: MarketType = MarketType.SPOT

    @field_validator("base_asset", "quote_asset", mode="before")
    @classmethod
    def normalize_asset(cls, value: str) -> str:
        if not isinstance(value, str):
            raise ValueError("asset must be a string")

        return value.strip().upper()

    @model_validator(mode="after")
    def assets_must_be_different(self) -> Self:
        if self.base_asset == self.quote_asset:
            raise ValueError("base asset and quote asset must be different")

        return self

    @property
    def symbol(self) -> str:
        """Return the canonical symbol representation."""

        return f"{self.base_asset}/{self.quote_asset}"


class OHLCVCandle(BaseModel):
    """A validated OHLCV market candle."""

    model_config = ConfigDict(frozen=True)

    source: str = Field(min_length=1, max_length=50)
    pair: TradingPair
    timeframe: Timeframe

    open_time: datetime
    close_time: datetime
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    open_price: Decimal = Field(gt=0)
    high_price: Decimal = Field(gt=0)
    low_price: Decimal = Field(gt=0)
    close_price: Decimal = Field(gt=0)
    volume: Decimal = Field(ge=0)

    is_closed: bool = True

    @field_validator("open_time", "close_time", "received_at")
    @classmethod
    def timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include timezone information")

        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_candle(self) -> Self:
        if self.close_time <= self.open_time:
            raise ValueError("close time must be after open time")

        if self.high_price < self.low_price:
            raise ValueError("high price cannot be lower than low price")

        highest_body_price = max(self.open_price, self.close_price)
        lowest_body_price = min(self.open_price, self.close_price)

        if self.high_price < highest_body_price:
            raise ValueError("high price cannot be lower than open or close price")

        if self.low_price > lowest_body_price:
            raise ValueError("low price cannot be higher than open or close price")

        return self
