import hashlib
import json
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from trd_bot.research.datasets import DatasetRepository, calculate_dataset_checksum
from trd_bot.research.experiments import ResearchExperiment
from trd_bot.research.pipeline import ResearchPipeline, ResearchPipelineResult
from trd_bot.strategies import (
    StrategyParameterKind,
    StrategyParameterValue,
    StrategyRegistry,
    build_default_strategy_registry,
)


class ExperimentReplayStatus(StrEnum):
    """High-level outcome of a non-mutating experiment replay verification."""

    VERIFIED = "verified"
    MISMATCH = "mismatch"
    UNVERIFIABLE = "unverifiable"


class ExperimentReplayCode(StrEnum):
    """Stable machine-readable reason for one replay verification outcome."""

    VERIFIED = "verified"
    LEGACY_FINGERPRINT_MISSING = "legacy_fingerprint_missing"
    DATASET_NOT_FOUND = "dataset_not_found"
    DATASET_INTEGRITY_MISMATCH = "dataset_integrity_mismatch"
    STRATEGY_VERSION_NOT_FOUND = "strategy_version_not_found"
    STRATEGY_FINGERPRINT_MISMATCH = "strategy_fingerprint_mismatch"
    INVALID_STRATEGY_PARAMETERS = "invalid_strategy_parameters"
    REPLAY_FAILED = "replay_failed"
    RESULT_MISMATCH = "result_mismatch"


class ExperimentReplayVerification(BaseModel):
    """Compact evidence returned after replaying an immutable experiment."""

    model_config = ConfigDict(frozen=True)

    experiment_id: str
    checked_at: datetime
    status: ExperimentReplayStatus
    code: ExperimentReplayCode
    dataset_id: str
    strategy_name: str
    strategy_version: str
    recorded_strategy_fingerprint: str | None
    current_strategy_fingerprint: str | None
    recorded_result_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    replayed_result_checksum: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{64}$",
    )
    mismatch_fields: tuple[str, ...] = ()


def calculate_research_result_checksum(result: ResearchPipelineResult) -> str:
    """Return the canonical content checksum of a complete research result."""

    payload = json.dumps(
        result.model_dump(mode="json"),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ExperimentReplayVerifier:
    """Replay one stored experiment without mutating its historical record."""

    _BACKTEST_PARAMETER_NAMES = (
        "starting_balance",
        "allocation_fraction",
        "fee_rate",
        "slippage_rate",
    )

    def __init__(
        self,
        *,
        datasets: DatasetRepository,
        strategy_registry: StrategyRegistry | None = None,
    ) -> None:
        self._datasets = datasets
        self._strategy_registry = strategy_registry or build_default_strategy_registry()

    def verify(
        self,
        experiment: ResearchExperiment,
        *,
        checked_at: datetime | None = None,
    ) -> ExperimentReplayVerification:
        effective_checked_at = (checked_at or datetime.now(UTC)).astimezone(UTC)
        recorded_checksum = calculate_research_result_checksum(experiment.result)

        if experiment.strategy_fingerprint is None:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.UNVERIFIABLE,
                code=ExperimentReplayCode.LEGACY_FINGERPRINT_MISSING,
                recorded_checksum=recorded_checksum,
            )

        definition = self._strategy_registry.get(
            name=experiment.strategy_name,
            version=experiment.strategy_version,
        )
        if definition is None or definition.metadata is None:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.UNVERIFIABLE,
                code=ExperimentReplayCode.STRATEGY_VERSION_NOT_FOUND,
                recorded_checksum=recorded_checksum,
            )

        current_fingerprint = definition.metadata.behavior_fingerprint
        if current_fingerprint != experiment.strategy_fingerprint:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.MISMATCH,
                code=ExperimentReplayCode.STRATEGY_FINGERPRINT_MISMATCH,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
            )

        dataset = self._datasets.get(experiment.dataset_id)
        if dataset is None:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.UNVERIFIABLE,
                code=ExperimentReplayCode.DATASET_NOT_FOUND,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
            )

        if calculate_dataset_checksum(dataset.candles) != dataset.checksum:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.MISMATCH,
                code=ExperimentReplayCode.DATASET_INTEGRITY_MISMATCH,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
            )

        try:
            parameters = self._strategy_parameters(experiment)
            self._validate_recorded_backtest_parameters(experiment)
            strategy = definition.create(parameters)
        except (InvalidOperation, KeyError, TypeError, ValueError):
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.UNVERIFIABLE,
                code=ExperimentReplayCode.INVALID_STRATEGY_PARAMETERS,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
            )

        try:
            replayed_result = ResearchPipeline().run(
                dataset=dataset,
                strategy=strategy,
                horizon_candles=experiment.horizon_candles,
                backtest_config=experiment.result.backtest_config,
            )
        except (ArithmeticError, ValueError):
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.UNVERIFIABLE,
                code=ExperimentReplayCode.REPLAY_FAILED,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
            )

        replayed_checksum = calculate_research_result_checksum(replayed_result)
        if replayed_result != experiment.result:
            return self._result(
                experiment=experiment,
                checked_at=effective_checked_at,
                status=ExperimentReplayStatus.MISMATCH,
                code=ExperimentReplayCode.RESULT_MISMATCH,
                recorded_checksum=recorded_checksum,
                current_fingerprint=current_fingerprint,
                replayed_checksum=replayed_checksum,
                mismatch_fields=self._mismatch_fields(
                    recorded=experiment.result,
                    replayed=replayed_result,
                ),
            )

        return self._result(
            experiment=experiment,
            checked_at=effective_checked_at,
            status=ExperimentReplayStatus.VERIFIED,
            code=ExperimentReplayCode.VERIFIED,
            recorded_checksum=recorded_checksum,
            current_fingerprint=current_fingerprint,
            replayed_checksum=replayed_checksum,
        )

    @staticmethod
    def _parameter_values(experiment: ResearchExperiment) -> dict[str, str]:
        return {parameter.name: parameter.value for parameter in experiment.parameters}

    def _strategy_parameters(
        self,
        experiment: ResearchExperiment,
    ) -> dict[str, StrategyParameterValue]:
        definition = self._strategy_registry.require(
            name=experiment.strategy_name,
            version=experiment.strategy_version,
        )
        if definition.metadata is None:
            raise ValueError("strategy metadata is unavailable")

        values = self._parameter_values(experiment)
        parsed: dict[str, StrategyParameterValue] = {}
        for parameter in definition.metadata.parameters:
            value = values[parameter.name].strip()
            if parameter.kind is StrategyParameterKind.INTEGER:
                integer_value = int(value)
                if str(integer_value) != value:
                    raise ValueError("integer strategy parameter is not canonical")
                parsed[parameter.name] = integer_value
            else:
                decimal_value = Decimal(value)
                if not decimal_value.is_finite():
                    raise ValueError("decimal strategy parameter must be finite")
                parsed[parameter.name] = decimal_value
        return parsed

    def _validate_recorded_backtest_parameters(
        self,
        experiment: ResearchExperiment,
    ) -> None:
        values = self._parameter_values(experiment)
        config = experiment.result.backtest_config
        config_values: dict[str, Decimal] = {
            "starting_balance": config.starting_balance,
            "allocation_fraction": config.allocation_fraction,
            "fee_rate": config.fee_rate,
            "slippage_rate": config.slippage_rate,
        }
        for name in self._BACKTEST_PARAMETER_NAMES:
            if name not in values:
                continue
            value = Decimal(values[name])
            if not value.is_finite() or value != config_values[name]:
                raise ValueError("recorded backtest parameter does not match result")

    @staticmethod
    def _mismatch_fields(
        *,
        recorded: ResearchPipelineResult,
        replayed: ResearchPipelineResult,
    ) -> tuple[str, ...]:
        recorded_payload = recorded.model_dump(mode="json")
        replayed_payload = replayed.model_dump(mode="json")
        return tuple(
            sorted(
                key
                for key in recorded_payload.keys() | replayed_payload.keys()
                if recorded_payload.get(key) != replayed_payload.get(key)
            )
        )

    @staticmethod
    def _result(
        *,
        experiment: ResearchExperiment,
        checked_at: datetime,
        status: ExperimentReplayStatus,
        code: ExperimentReplayCode,
        recorded_checksum: str,
        current_fingerprint: str | None = None,
        replayed_checksum: str | None = None,
        mismatch_fields: tuple[str, ...] = (),
    ) -> ExperimentReplayVerification:
        return ExperimentReplayVerification(
            experiment_id=experiment.experiment_id,
            checked_at=checked_at,
            status=status,
            code=code,
            dataset_id=experiment.dataset_id,
            strategy_name=experiment.strategy_name,
            strategy_version=experiment.strategy_version,
            recorded_strategy_fingerprint=experiment.strategy_fingerprint,
            current_strategy_fingerprint=current_fingerprint,
            recorded_result_checksum=recorded_checksum,
            replayed_result_checksum=replayed_checksum,
            mismatch_fields=mismatch_fields,
        )
