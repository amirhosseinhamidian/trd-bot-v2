from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from trd_bot.strategies.signals import StrategySignal

if TYPE_CHECKING:
    from trd_bot.research.datasets import DatasetSnapshot


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
