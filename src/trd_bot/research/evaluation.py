from collections.abc import Sequence
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

from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.strategies.signals import (
    SignalDirection,
    StrategySignal,
)


class SignalOutcome(StrEnum):
    """Possible outcomes of a research signal."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    FLAT = "flat"


class SignalEvaluation(BaseModel):
    """Result of evaluating one signal on future candles."""

    model_config = ConfigDict(frozen=True)

    signal_id: str
    direction: SignalDirection
    horizon_candles: int = Field(ge=1)

    reference_time: datetime
    reference_price: Decimal = Field(gt=0)

    evaluation_time: datetime
    evaluation_price: Decimal = Field(gt=0)

    directional_return: Decimal
    outcome: SignalOutcome

    @field_validator(
        "reference_time",
        "evaluation_time",
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
    def validate_times(self) -> Self:
        if self.evaluation_time <= self.reference_time:
            raise ValueError("evaluation time must be after reference time")

        return self


class SignalEvaluationReport(BaseModel):
    """Aggregated research-signal evaluation report."""

    model_config = ConfigDict(frozen=True)

    dataset_id: str
    horizon_candles: int = Field(ge=1)

    total_signals: int = Field(ge=0)
    resolved_signals: int = Field(ge=0)
    unresolved_signals: int = Field(ge=0)
    ignored_neutral_signals: int = Field(ge=0)

    correct_signals: int = Field(ge=0)
    incorrect_signals: int = Field(ge=0)
    flat_signals: int = Field(ge=0)

    hit_rate: Decimal | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    evaluations: tuple[SignalEvaluation, ...] = ()


class SignalEvaluator:
    """Evaluate strategy signals without creating trades."""

    def evaluate(
        self,
        *,
        dataset: DatasetSnapshot,
        signals: Sequence[StrategySignal],
        horizon_candles: int = 1,
    ) -> SignalEvaluationReport:
        if horizon_candles < 1:
            raise ValueError("evaluation horizon must be at least 1")

        candle_indices = {
            (
                candle.open_time,
                candle.close_time,
            ): index
            for index, candle in enumerate(dataset.candles)
        }

        evaluations: list[SignalEvaluation] = []
        unresolved_signals = 0
        ignored_neutral_signals = 0

        for signal in signals:
            self._validate_signal(
                dataset=dataset,
                signal=signal,
            )

            if signal.direction == SignalDirection.NEUTRAL:
                ignored_neutral_signals += 1
                continue

            signal_window = (
                signal.candle_open_time,
                signal.candle_close_time,
            )

            signal_index = candle_indices.get(signal_window)

            if signal_index is None:
                raise ValueError("signal candle does not exist in the dataset")

            reference_index = signal_index + 1
            evaluation_index = signal_index + horizon_candles

            if reference_index >= len(dataset.candles) or evaluation_index >= len(dataset.candles):
                unresolved_signals += 1
                continue

            reference_candle = dataset.candles[reference_index]
            evaluation_candle = dataset.candles[evaluation_index]

            directional_return = self._directional_return(
                direction=signal.direction,
                reference_price=reference_candle.open_price,
                evaluation_price=(evaluation_candle.close_price),
            )

            outcome = self._outcome_from_return(directional_return)

            evaluations.append(
                SignalEvaluation(
                    signal_id=signal.signal_id,
                    direction=signal.direction,
                    horizon_candles=horizon_candles,
                    reference_time=reference_candle.open_time,
                    reference_price=(reference_candle.open_price),
                    evaluation_time=(evaluation_candle.close_time),
                    evaluation_price=(evaluation_candle.close_price),
                    directional_return=directional_return,
                    outcome=outcome,
                )
            )

        correct_signals = sum(
            evaluation.outcome == SignalOutcome.CORRECT for evaluation in evaluations
        )

        incorrect_signals = sum(
            evaluation.outcome == SignalOutcome.INCORRECT for evaluation in evaluations
        )

        flat_signals = sum(evaluation.outcome == SignalOutcome.FLAT for evaluation in evaluations)

        resolved_signals = len(evaluations)

        hit_rate = (
            Decimal(correct_signals) / Decimal(resolved_signals) if resolved_signals else None
        )

        return SignalEvaluationReport(
            dataset_id=dataset.dataset_id,
            horizon_candles=horizon_candles,
            total_signals=len(signals),
            resolved_signals=resolved_signals,
            unresolved_signals=unresolved_signals,
            ignored_neutral_signals=(ignored_neutral_signals),
            correct_signals=correct_signals,
            incorrect_signals=incorrect_signals,
            flat_signals=flat_signals,
            hit_rate=hit_rate,
            evaluations=tuple(evaluations),
        )

    @staticmethod
    def _validate_signal(
        *,
        dataset: DatasetSnapshot,
        signal: StrategySignal,
    ) -> None:
        if signal.dataset_id != dataset.dataset_id:
            raise ValueError("signal does not belong to the dataset")

        if signal.pair != dataset.pair:
            raise ValueError("signal pair does not match the dataset")

        if signal.timeframe != dataset.timeframe:
            raise ValueError("signal timeframe does not match the dataset")

    @staticmethod
    def _directional_return(
        *,
        direction: SignalDirection,
        reference_price: Decimal,
        evaluation_price: Decimal,
    ) -> Decimal:
        raw_return = (evaluation_price - reference_price) / reference_price

        if direction == SignalDirection.LONG:
            return raw_return

        if direction == SignalDirection.SHORT:
            return -raw_return

        return Decimal("0")

    @staticmethod
    def _outcome_from_return(
        directional_return: Decimal,
    ) -> SignalOutcome:
        if directional_return > 0:
            return SignalOutcome.CORRECT

        if directional_return < 0:
            return SignalOutcome.INCORRECT

        return SignalOutcome.FLAT
