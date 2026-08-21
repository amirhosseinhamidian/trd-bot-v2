from abc import ABC, abstractmethod

from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies.signals import StrategySignal


class BaseStrategy(ABC):
    """Base interface for all research strategies."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique strategy name."""

        raise NotImplementedError

    @property
    @abstractmethod
    def version(self) -> str:
        """Return the strategy version."""

        raise NotImplementedError

    @abstractmethod
    def generate(
        self,
        dataset: DatasetSnapshot,
    ) -> tuple[StrategySignal, ...]:
        """Generate research signals from a validated dataset."""

        raise NotImplementedError
