from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import datetime

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair


class MarketDataProvider(ABC):
    """Interface for retrieving historical market candles."""

    @abstractmethod
    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        """Return closed candles in chronological order."""

        raise NotImplementedError


class InMemoryMarketDataProvider(MarketDataProvider):
    """Market-data provider backed by an in-memory candle collection."""

    def __init__(self, candles: Iterable[OHLCVCandle]) -> None:
        self._candles = tuple(
            sorted(
                candles,
                key=lambda candle: candle.open_time,
            )
        )

    async def get_candles(
        self,
        pair: TradingPair,
        timeframe: Timeframe,
        start_time: datetime,
        end_time: datetime,
        limit: int | None = None,
    ) -> list[OHLCVCandle]:
        self._validate_query(
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )

        result = [
            candle
            for candle in self._candles
            if candle.pair == pair
            and candle.timeframe == timeframe
            and candle.is_closed
            and start_time <= candle.open_time < end_time
        ]

        if limit is not None:
            return result[:limit]

        return result

    @staticmethod
    def _validate_query(
        start_time: datetime,
        end_time: datetime,
        limit: int | None,
    ) -> None:
        if start_time.tzinfo is None or start_time.utcoffset() is None:
            raise ValueError("start time must include timezone information")

        if end_time.tzinfo is None or end_time.utcoffset() is None:
            raise ValueError("end time must include timezone information")

        if end_time <= start_time:
            raise ValueError("end time must be after start time")

        if limit is not None and limit <= 0:
            raise ValueError("limit must be greater than zero")
