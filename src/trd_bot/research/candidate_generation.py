from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.domain.market_data import OHLCVCandle
from trd_bot.research.candidates import (
    CandidateBuilder,
    CandidateEntryZone,
    CandidateTarget,
    CandidateTradePlan,
    ResearchCandidate,
)
from trd_bot.research.datasets import DatasetSnapshot
from trd_bot.research.experiments import ResearchExperiment
from trd_bot.strategies.signals import SignalDirection, StrategySignal


class CandidateGenerationPolicy(BaseModel):
    """Deterministic policy for deriving historical research candidates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    confidence_prior: Decimal = Field(
        default=Decimal("0.50"),
        ge=0,
        le=1,
    )
    reward_risk_ratio: Decimal = Field(
        default=Decimal("2.00"),
        gt=0,
    )


class CandidateGenerator:
    """Derive replayable candidates from immutable experiment signals."""

    def __init__(
        self,
        *,
        policy: CandidateGenerationPolicy | None = None,
    ) -> None:
        self._policy = policy or CandidateGenerationPolicy()

    @property
    def policy(self) -> CandidateGenerationPolicy:
        return self._policy

    def generate(
        self,
        *,
        experiment: ResearchExperiment,
        dataset: DatasetSnapshot,
    ) -> tuple[ResearchCandidate, ...]:
        if experiment.dataset_id != dataset.dataset_id:
            raise ValueError("experiment and candidate dataset lineage must match")

        candidates: list[ResearchCandidate] = []

        for signal in experiment.result.signals:
            self._validate_signal_lineage(
                signal=signal,
                dataset=dataset,
            )

            if signal.direction is SignalDirection.NEUTRAL:
                continue

            source_candle = self._source_candle(
                signal=signal,
                dataset=dataset,
            )

            trade_plan = self._trade_plan(
                signal=signal,
                candle=source_candle,
            )

            if trade_plan is None:
                continue

            candidates.append(
                CandidateBuilder.from_signal(
                    signal=signal,
                    experiment_id=experiment.experiment_id,
                    horizon_candles=experiment.horizon_candles,
                    confidence=self._policy.confidence_prior,
                    created_at=signal.generated_at,
                    valid_until=(
                        signal.generated_at
                        + dataset.timeframe.duration * experiment.horizon_candles
                    ),
                    trade_plan=trade_plan,
                )
            )

        return tuple(candidates)

    @staticmethod
    def _validate_signal_lineage(
        *,
        signal: StrategySignal,
        dataset: DatasetSnapshot,
    ) -> None:
        if signal.dataset_id != dataset.dataset_id:
            raise ValueError("candidate source signal dataset lineage must match")

        if signal.pair != dataset.pair:
            raise ValueError("candidate source signal pair must match dataset")

        if signal.timeframe is not dataset.timeframe:
            raise ValueError("candidate source signal timeframe must match dataset")

    @staticmethod
    def _source_candle(
        *,
        signal: StrategySignal,
        dataset: DatasetSnapshot,
    ) -> OHLCVCandle:
        matches = tuple(
            candle
            for candle in dataset.candles
            if candle.open_time == signal.candle_open_time
            and candle.close_time == signal.candle_close_time
        )

        if len(matches) != 1:
            raise ValueError("candidate source signal must map to exactly one dataset candle")

        return matches[0]

    def _trade_plan(
        self,
        *,
        signal: StrategySignal,
        candle: OHLCVCandle,
    ) -> CandidateTradePlan | None:
        entry_price = candle.close_price

        if signal.direction is SignalDirection.LONG:
            invalidation_price = candle.low_price
            unit_risk = entry_price - invalidation_price

            if unit_risk <= 0:
                return None

            target_price = entry_price + unit_risk * self._policy.reward_risk_ratio

        elif signal.direction is SignalDirection.SHORT:
            invalidation_price = candle.high_price
            unit_risk = invalidation_price - entry_price

            if unit_risk <= 0:
                return None

            target_price = entry_price - unit_risk * self._policy.reward_risk_ratio

            if target_price <= 0:
                return None

        else:
            return None

        return CandidateTradePlan(
            entry_zone=CandidateEntryZone(
                lower_price=entry_price,
                upper_price=entry_price,
            ),
            invalidation_price=invalidation_price,
            targets=(
                CandidateTarget(
                    label="target-1",
                    price=target_price,
                ),
            ),
        )
