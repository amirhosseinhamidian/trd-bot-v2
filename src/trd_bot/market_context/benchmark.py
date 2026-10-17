import hashlib
import json
import math
import platform
from collections.abc import Callable, Sequence
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from time import perf_counter
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_context.alignment import (
    align_market_context_windows,
    floor_market_context_boundary,
)
from trd_bot.market_context.contracts import MarketTrendRegime, MarketVolatilityRegime
from trd_bot.market_context.features import (
    calculate_market_context_feature_snapshot_v1,
    market_context_feature_set_v1,
)
from trd_bot.market_context.regimes import (
    evaluate_market_regime_v1,
    market_regime_policy_v1,
)
from trd_bot.market_data.events import (
    MarketDataEvent,
    MarketDataWindowSnapshot,
    MarketDataWindowState,
)
from trd_bot.market_data.service_levels import default_market_data_service_level_policy

MARKET_CONTEXT_GOLDEN_FIXTURE_VERSION: Final = "market-context-golden-v1"
MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES: Final = 30
_FIXTURE_SOURCE: Final = "market-context-golden-synthetic"
_FIXTURE_AS_OF: Final = datetime(2026, 10, 16, 12, tzinfo=UTC)
_FIXTURE_PAIR: Final = TradingPair(base_asset="BTC", quote_asset="USDT")
_TIMEFRAME_ORDER: Final = (Timeframe.HOUR_1, Timeframe.HOURS_4, Timeframe.DAY_1)
_WINDOW_COUNTS: Final = {
    Timeframe.HOUR_1: 24,
    Timeframe.HOURS_4: 18,
    Timeframe.DAY_1: 14,
}


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def _checksum(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalize_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("market-context benchmark timestamps must include timezone information")
    return value.astimezone(UTC)


class MarketContextGoldenScenarioId(StrEnum):
    TRENDING_UP_LOW = "trending_up_low"
    TRENDING_DOWN_HIGH = "trending_down_high"
    RANGING_NORMAL = "ranging_normal"


class MarketContextGoldenFailureCode(StrEnum):
    EXECUTION_FAILED = "execution_failed"
    GOLDEN_MISMATCH = "golden_mismatch"
    INSUFFICIENT_SAMPLES = "insufficient_samples"
    NON_DETERMINISTIC_OUTPUT = "non_deterministic_output"
    RUNTIME_BUDGET_EXCEEDED = "runtime_budget_exceeded"


class MarketContextGoldenSeriesDefinition(BaseModel):
    """Compact deterministic price-series definition for one required timeframe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    timeframe: Timeframe
    window_count: int = Field(ge=2, le=100)
    start_price: Decimal = Field(gt=0)
    base_return: Decimal = Field(gt=Decimal("-1"), lt=Decimal("1"))
    alternating_return: Decimal = Field(ge=0, lt=Decimal("1"))


class MarketContextGoldenOutput(BaseModel):
    """Stable lineage and classification signature produced by one golden scenario."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    input_manifest_id: str = Field(pattern=r"^market-context-input-[a-f0-9]{16}$")
    input_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    feature_snapshot_id: str = Field(pattern=r"^market-context-features-[a-f0-9]{16}$")
    feature_snapshot_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    assessment_id: str = Field(pattern=r"^market-regime-[a-f0-9]{16}$")
    trend: MarketTrendRegime
    volatility: MarketVolatilityRegime
    confidence: Decimal = Field(ge=0, le=1)
    evidence_values: tuple[tuple[str, Decimal], ...] = Field(min_length=5, max_length=5)
    output_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_fingerprint(self) -> Self:
        if len({key for key, _ in self.evidence_values}) != len(self.evidence_values):
            raise ValueError("golden output evidence keys must be unique")
        if self.output_fingerprint != _checksum(self._fingerprint_payload()):
            raise ValueError("golden output fingerprint is inconsistent")
        return self

    def _fingerprint_payload(self) -> dict[str, object]:
        return {
            "assessment_id": self.assessment_id,
            "confidence": str(self.confidence),
            "evidence_values": [[key, str(value)] for key, value in self.evidence_values],
            "feature_snapshot_checksum": self.feature_snapshot_checksum,
            "feature_snapshot_id": self.feature_snapshot_id,
            "input_checksum": self.input_checksum,
            "input_manifest_id": self.input_manifest_id,
            "trend": self.trend.value,
            "volatility": self.volatility.value,
        }

    @classmethod
    def build(
        cls,
        *,
        input_manifest_id: str,
        input_checksum: str,
        feature_snapshot_id: str,
        feature_snapshot_checksum: str,
        assessment_id: str,
        trend: MarketTrendRegime,
        volatility: MarketVolatilityRegime,
        confidence: Decimal,
        evidence_values: tuple[tuple[str, Decimal], ...],
    ) -> Self:
        payload: dict[str, object] = {
            "assessment_id": assessment_id,
            "confidence": str(confidence),
            "evidence_values": [[key, str(value)] for key, value in evidence_values],
            "feature_snapshot_checksum": feature_snapshot_checksum,
            "feature_snapshot_id": feature_snapshot_id,
            "input_checksum": input_checksum,
            "input_manifest_id": input_manifest_id,
            "trend": trend.value,
            "volatility": volatility.value,
        }
        return cls(
            input_manifest_id=input_manifest_id,
            input_checksum=input_checksum,
            feature_snapshot_id=feature_snapshot_id,
            feature_snapshot_checksum=feature_snapshot_checksum,
            assessment_id=assessment_id,
            trend=trend,
            volatility=volatility,
            confidence=confidence,
            evidence_values=evidence_values,
            output_fingerprint=_checksum(payload),
        )


class MarketContextGoldenScenarioDefinition(BaseModel):
    """Synthetic inputs and frozen expected output for one classification case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: MarketContextGoldenScenarioId
    series: tuple[MarketContextGoldenSeriesDefinition, ...] = Field(min_length=3, max_length=3)
    expected: MarketContextGoldenOutput

    @model_validator(mode="after")
    def validate_series(self) -> Self:
        if tuple(item.timeframe for item in self.series) != _TIMEFRAME_ORDER:
            raise ValueError("golden scenario timeframes must use canonical order")
        if any(item.window_count != _WINDOW_COUNTS[item.timeframe] for item in self.series):
            raise ValueError("golden scenario window counts must satisfy the v1 feature set")
        return self


class MarketContextGoldenFixtureDefinition(BaseModel):
    """Versioned, tamper-evident benchmark fixture with no external data dependency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-golden-fixture-v1"] = "market-context-golden-fixture-v1"
    fixture_version: Literal["market-context-golden-v1"] = MARKET_CONTEXT_GOLDEN_FIXTURE_VERSION
    source: Literal["market-context-golden-synthetic"] = _FIXTURE_SOURCE
    pair: TradingPair = _FIXTURE_PAIR
    as_of: datetime = _FIXTURE_AS_OF
    scenarios: tuple[MarketContextGoldenScenarioDefinition, ...] = Field(
        min_length=3,
        max_length=3,
    )
    definition_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")

    @field_validator("as_of")
    @classmethod
    def normalize_as_of(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_fixture(self) -> Self:
        expected_ids = tuple(MarketContextGoldenScenarioId)
        if tuple(item.scenario_id for item in self.scenarios) != expected_ids:
            raise ValueError("golden fixture must contain every scenario in canonical order")
        if self.definition_checksum != _checksum(self._checksum_payload()):
            raise ValueError("golden fixture checksum is inconsistent")
        return self

    def _checksum_payload(self) -> dict[str, object]:
        return self.model_dump(mode="json", exclude={"definition_checksum"})


class MarketContextGoldenScenarioEvidence(BaseModel):
    """Measured deterministic output and latency evidence for one golden case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    scenario_id: MarketContextGoldenScenarioId
    requested_samples: int = Field(ge=1, le=10_000)
    successful_samples: int = Field(ge=0)
    failed_samples: int = Field(ge=0)
    expected: MarketContextGoldenOutput
    observed: MarketContextGoldenOutput | None
    unique_output_fingerprints: tuple[str, ...]
    runtime_p50_ms: Decimal = Field(ge=0)
    runtime_p95_ms: Decimal = Field(ge=0)
    runtime_budget_ms: Decimal = Field(gt=0)

    @field_validator("unique_output_fingerprints")
    @classmethod
    def validate_fingerprints(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != tuple(sorted(set(value))):
            raise ValueError("golden output fingerprints must be sorted and unique")
        if any(len(item) != 64 for item in value):
            raise ValueError("golden output fingerprint must be a SHA-256 digest")
        return value

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.successful_samples + self.failed_samples != self.requested_samples:
            raise ValueError("golden benchmark sample counts are inconsistent")
        if self.successful_samples == 0:
            if self.observed is not None or self.unique_output_fingerprints:
                raise ValueError("failed golden scenario cannot expose an observed output")
        elif self.observed is None:
            raise ValueError("successful golden scenario requires an observed output")
        if self.runtime_p50_ms > self.runtime_p95_ms:
            raise ValueError("golden runtime percentiles are inconsistent")
        return self

    @property
    def failure_codes(self) -> tuple[MarketContextGoldenFailureCode, ...]:
        failures: set[MarketContextGoldenFailureCode] = set()
        if self.requested_samples < MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES:
            failures.add(MarketContextGoldenFailureCode.INSUFFICIENT_SAMPLES)
        if self.failed_samples or self.successful_samples != self.requested_samples:
            failures.add(MarketContextGoldenFailureCode.EXECUTION_FAILED)
        if len(self.unique_output_fingerprints) > 1:
            failures.add(MarketContextGoldenFailureCode.NON_DETERMINISTIC_OUTPUT)
        if self.observed != self.expected or self.unique_output_fingerprints != (
            self.expected.output_fingerprint,
        ):
            failures.add(MarketContextGoldenFailureCode.GOLDEN_MISMATCH)
        if self.runtime_p95_ms > self.runtime_budget_ms:
            failures.add(MarketContextGoldenFailureCode.RUNTIME_BUDGET_EXCEEDED)
        return tuple(sorted(failures, key=lambda item: item.value))

    @property
    def passed(self) -> bool:
        return not self.failure_codes


class MarketContextGoldenBenchmarkReport(BaseModel):
    """Same-SHA, sanitized evidence consumed by the Phase 3 acceptance gate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["market-context-golden-benchmark-v1"] = (
        "market-context-golden-benchmark-v1"
    )
    scope: Literal["crypto-spot-public-read-only"] = "crypto-spot-public-read-only"
    fixture_version: Literal["market-context-golden-v1"] = MARKET_CONTEXT_GOLDEN_FIXTURE_VERSION
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    python_version: str = Field(min_length=1, max_length=40)
    platform: str = Field(min_length=1, max_length=200)
    feature_set_version: Literal["market-context-features-v1"] = "market-context-features-v1"
    feature_set_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    algorithm_version: Literal["market-regime-v1"] = "market-regime-v1"
    algorithm_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    windows_per_scenario: Literal[56] = 56
    features_per_scenario: Literal[5] = 5
    minimum_samples_per_scenario: Literal[30] = MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES
    warmup_iterations: int = Field(ge=0, le=1_000)
    scenarios: tuple[MarketContextGoldenScenarioEvidence, ...] = Field(
        min_length=3,
        max_length=3,
    )

    @field_validator("environment_label")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("golden benchmark environment cannot be empty")
        return normalized

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        return _normalize_timestamp(value)

    @model_validator(mode="after")
    def validate_contract_identity(self) -> Self:
        fixture = market_context_golden_fixture_v1()
        feature_set = market_context_feature_set_v1()
        policy = market_regime_policy_v1()
        if self.fixture_checksum != fixture.definition_checksum:
            raise ValueError("golden benchmark fixture checksum is not canonical")
        if self.feature_set_checksum != feature_set.definition_checksum:
            raise ValueError("golden benchmark feature-set checksum is not canonical")
        if self.algorithm_policy_checksum != policy.definition_checksum:
            raise ValueError("golden benchmark regime-policy checksum is not canonical")
        if tuple(item.scenario_id for item in self.scenarios) != tuple(
            item.scenario_id for item in fixture.scenarios
        ):
            raise ValueError("golden benchmark scenarios must use canonical order")
        for evidence, definition in zip(self.scenarios, fixture.scenarios, strict=True):
            if evidence.expected != definition.expected:
                raise ValueError("golden benchmark expected output is not canonical")
        return self

    @property
    def failed_scenarios(self) -> tuple[MarketContextGoldenScenarioId, ...]:
        return tuple(item.scenario_id for item in self.scenarios if not item.passed)

    @property
    def ready_for_phase_three_acceptance(self) -> bool:
        return not self.failed_scenarios


def _scenario(
    scenario_id: MarketContextGoldenScenarioId,
    *,
    hourly: tuple[str, str],
    four_hour: tuple[str, str],
    daily: tuple[str, str],
    expected: MarketContextGoldenOutput,
) -> MarketContextGoldenScenarioDefinition:
    series = tuple(
        MarketContextGoldenSeriesDefinition(
            timeframe=timeframe,
            window_count=_WINDOW_COUNTS[timeframe],
            start_price=Decimal("100"),
            base_return=Decimal(values[0]),
            alternating_return=Decimal(values[1]),
        )
        for timeframe, values in zip(
            _TIMEFRAME_ORDER,
            (hourly, four_hour, daily),
            strict=True,
        )
    )
    return MarketContextGoldenScenarioDefinition(
        scenario_id=scenario_id,
        series=series,
        expected=expected,
    )


def market_context_golden_fixture_v1() -> MarketContextGoldenFixtureDefinition:
    """Return a fresh immutable copy of the canonical P3-09 fixture."""

    scenarios = (
        _scenario(
            MarketContextGoldenScenarioId.TRENDING_UP_LOW,
            hourly=("0.010", "0"),
            four_hour=("0.006", "0"),
            daily=("0.004", "0"),
            expected=MarketContextGoldenOutput.build(
                input_manifest_id="market-context-input-ea57b9f80c58ca5a",
                input_checksum=("ea57b9f80c58ca5a9d1b6a6ab3b4af16d72c7b8334e0e2e75d8a634460556e35"),
                feature_snapshot_id="market-context-features-a278769ebd6fa90c",
                feature_snapshot_checksum=(
                    "a278769ebd6fa90cbbc5a1c41d287b77d1bb62b4ebb90af165102a9bef51184a"
                ),
                assessment_id="market-regime-4283301875554310",
                trend=MarketTrendRegime.TRENDING_UP,
                volatility=MarketVolatilityRegime.LOW,
                confidence=Decimal("1.0000"),
                evidence_values=(
                    ("realized_volatility_1d", Decimal("0E-12")),
                    ("realized_volatility_1h", Decimal("0E-12")),
                    ("trend_slope_1d", Decimal("0.004097278537")),
                    ("trend_slope_1h", Decimal("0.011172487385")),
                    ("trend_slope_4h", Decimal("0.006295923196")),
                ),
            ),
        ),
        _scenario(
            MarketContextGoldenScenarioId.TRENDING_DOWN_HIGH,
            hourly=("-0.010", "0.020"),
            four_hour=("-0.006", "0"),
            daily=("-0.010", "0.050"),
            expected=MarketContextGoldenOutput.build(
                input_manifest_id="market-context-input-6c5eeb18becc8909",
                input_checksum=("6c5eeb18becc8909cd341d4208ebb9f808d9fe7e46d5b1dca2d8306c7b9d6482"),
                feature_snapshot_id="market-context-features-9142655860e9622a",
                feature_snapshot_checksum=(
                    "9142655860e9622a0a170378b9230b8179e6c07a3285ad6a934a8e29412332b0"
                ),
                assessment_id="market-regime-52eb028d72a89621",
                trend=MarketTrendRegime.TRENDING_DOWN,
                volatility=MarketVolatilityRegime.HIGH,
                confidence=Decimal("1.0000"),
                evidence_values=(
                    ("realized_volatility_1d", Decimal("0.049851851526")),
                    ("realized_volatility_1h", Decimal("0.019981087466")),
                    ("trend_slope_1d", Decimal("-0.010059484773")),
                    ("trend_slope_1h", Decimal("-0.009125295424")),
                    ("trend_slope_4h", Decimal("-0.005719632848")),
                ),
            ),
        ),
        _scenario(
            MarketContextGoldenScenarioId.RANGING_NORMAL,
            hourly=("0.001", "0.006"),
            four_hour=("-0.002", "0"),
            daily=("0", "0.020"),
            expected=MarketContextGoldenOutput.build(
                input_manifest_id="market-context-input-a02a49bda4be5efa",
                input_checksum=("a02a49bda4be5efabc604dc5001c04a0ec72e87fac7a4e616d9b5e499619eff6"),
                feature_snapshot_id="market-context-features-6db28d63f2837d7f",
                feature_snapshot_checksum=(
                    "6db28d63f2837d7f642badfdd339a8ff03feeee9d29fa13265fff394879e982d"
                ),
                assessment_id="market-regime-b230710db15cef8c",
                trend=MarketTrendRegime.RANGING,
                volatility=MarketVolatilityRegime.NORMAL,
                confidence=Decimal("0.9500"),
                evidence_values=(
                    ("realized_volatility_1d", Decimal("0.019940740610")),
                    ("realized_volatility_1h", Decimal("0.005994326240")),
                    ("trend_slope_1d", Decimal("0.000108629812")),
                    ("trend_slope_1h", Decimal("0.001027401379")),
                    ("trend_slope_4h", Decimal("-0.001968286216")),
                ),
            ),
        ),
    )
    unvalidated = MarketContextGoldenFixtureDefinition.model_construct(
        scenarios=scenarios,
        definition_checksum="0" * 64,
    )
    payload = unvalidated.model_dump()
    payload["definition_checksum"] = _checksum(unvalidated._checksum_payload())
    return MarketContextGoldenFixtureDefinition.model_validate(payload)


def _build_windows(
    fixture: MarketContextGoldenFixtureDefinition,
    scenario: MarketContextGoldenScenarioDefinition,
) -> tuple[MarketDataWindowSnapshot, ...]:
    windows: list[MarketDataWindowSnapshot] = []
    for definition in scenario.series:
        expected_end = floor_market_context_boundary(fixture.as_of, definition.timeframe)
        close_price = definition.start_price
        for index in range(definition.window_count):
            if index:
                alternating = (
                    definition.alternating_return if index % 2 else -definition.alternating_return
                )
                close_price *= Decimal(1) + definition.base_return + alternating
            window_start = expected_end - definition.timeframe.duration * (
                definition.window_count - index
            )
            window_end = window_start + definition.timeframe.duration
            candle = OHLCVCandle(
                source=fixture.source,
                pair=fixture.pair,
                timeframe=definition.timeframe,
                open_time=window_start,
                close_time=window_end,
                received_at=window_end + timedelta(seconds=30),
                open_price=close_price,
                high_price=close_price + Decimal(1),
                low_price=close_price - Decimal(1),
                close_price=close_price,
                volume=Decimal(1_000 + index),
            )
            event = MarketDataEvent.from_candle(candle)
            windows.append(
                MarketDataWindowSnapshot(
                    window_id=event.window_id,
                    version=2,
                    state=MarketDataWindowState.FINALIZED,
                    source=fixture.source,
                    pair=fixture.pair,
                    timeframe=definition.timeframe,
                    window_start=window_start,
                    window_end=window_end,
                    event_id=event.event_id,
                    payload_checksum=event.payload_checksum,
                    candle=candle,
                    created_at=window_end + timedelta(seconds=30),
                    finalized_at=window_end + timedelta(minutes=1),
                )
            )
    return tuple(windows)


def execute_market_context_golden_scenario(
    scenario: MarketContextGoldenScenarioDefinition,
    *,
    fixture: MarketContextGoldenFixtureDefinition | None = None,
) -> MarketContextGoldenOutput:
    """Execute the real deterministic context pipeline for one synthetic scenario."""

    selected_fixture = fixture or market_context_golden_fixture_v1()
    windows = _build_windows(selected_fixture, scenario)
    alignment = align_market_context_windows(
        source=selected_fixture.source,
        pair=selected_fixture.pair,
        as_of=selected_fixture.as_of,
        windows=windows,
        feature_set=market_context_feature_set_v1(),
        aligned_at=selected_fixture.as_of + timedelta(minutes=2),
    )
    if alignment.manifest is None:
        raise RuntimeError("golden scenario did not produce an input manifest")
    snapshot = calculate_market_context_feature_snapshot_v1(
        manifest=alignment.manifest,
        windows=windows,
    )
    assessment = evaluate_market_regime_v1(snapshot)
    return MarketContextGoldenOutput.build(
        input_manifest_id=alignment.manifest.manifest_id,
        input_checksum=alignment.manifest.input_checksum,
        feature_snapshot_id=snapshot.snapshot_id,
        feature_snapshot_checksum=snapshot.snapshot_checksum,
        assessment_id=assessment.assessment_id,
        trend=assessment.trend,
        volatility=assessment.volatility,
        confidence=assessment.confidence,
        evidence_values=tuple((item.feature_key, item.value) for item in assessment.evidence),
    )


def _percentile(values: Sequence[float], fraction: float) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return Decimal(str(round(ordered[index] * 1_000, 6)))


def run_market_context_golden_benchmark(
    *,
    commit_sha: str,
    environment_label: str,
    samples_per_scenario: int,
    warmup_iterations: int,
    generated_at: datetime | None = None,
    clock: Callable[[], float] = perf_counter,
) -> MarketContextGoldenBenchmarkReport:
    """Measure every canonical scenario and retain only sanitized aggregate evidence."""

    if not 1 <= samples_per_scenario <= 10_000:
        raise ValueError("samples per scenario must be between 1 and 10,000")
    if not 0 <= warmup_iterations <= 1_000:
        raise ValueError("warmup iterations must be between zero and 1,000")
    fixture = market_context_golden_fixture_v1()
    runtime_budget_ms = default_market_data_service_level_policy().capacity.job_runtime_p95_seconds[
        "market_context_evaluation"
    ] * Decimal(1_000)
    evidence_items: list[MarketContextGoldenScenarioEvidence] = []
    for scenario in fixture.scenarios:
        for _ in range(warmup_iterations):
            with suppress(Exception):
                execute_market_context_golden_scenario(scenario, fixture=fixture)

        outputs: list[MarketContextGoldenOutput] = []
        runtimes: list[float] = []
        failures = 0
        for _ in range(samples_per_scenario):
            started_at = clock()
            try:
                output = execute_market_context_golden_scenario(scenario, fixture=fixture)
            except Exception:
                failures += 1
            else:
                outputs.append(output)
                runtimes.append(clock() - started_at)
        fingerprints = tuple(sorted({item.output_fingerprint for item in outputs}))
        evidence_items.append(
            MarketContextGoldenScenarioEvidence(
                scenario_id=scenario.scenario_id,
                requested_samples=samples_per_scenario,
                successful_samples=len(outputs),
                failed_samples=failures,
                expected=scenario.expected,
                observed=outputs[0] if outputs else None,
                unique_output_fingerprints=fingerprints,
                runtime_p50_ms=_percentile(runtimes, 0.50),
                runtime_p95_ms=_percentile(runtimes, 0.95),
                runtime_budget_ms=runtime_budget_ms,
            )
        )

    feature_set = market_context_feature_set_v1()
    policy = market_regime_policy_v1()
    return MarketContextGoldenBenchmarkReport(
        fixture_checksum=fixture.definition_checksum,
        commit_sha=commit_sha,
        environment_label=environment_label,
        generated_at=generated_at or datetime.now(UTC),
        python_version=platform.python_version(),
        platform=platform.platform(),
        feature_set_checksum=feature_set.definition_checksum,
        algorithm_policy_checksum=policy.definition_checksum,
        warmup_iterations=warmup_iterations,
        scenarios=tuple(evidence_items),
    )


def market_context_golden_benchmark_report_to_dict(
    report: MarketContextGoldenBenchmarkReport,
) -> dict[str, object]:
    payload = report.model_dump(mode="json")
    scenarios = payload["scenarios"]
    if not isinstance(scenarios, list):
        raise TypeError("serialized golden benchmark scenarios must be a list")
    for scenario_payload, evidence in zip(scenarios, report.scenarios, strict=True):
        if not isinstance(scenario_payload, dict):
            raise TypeError("serialized golden benchmark scenario must be an object")
        scenario_payload["failure_codes"] = [item.value for item in evidence.failure_codes]
        scenario_payload["passed"] = evidence.passed
    payload["failed_scenarios"] = [item.value for item in report.failed_scenarios]
    payload["ready_for_phase_three_acceptance"] = report.ready_for_phase_three_acceptance
    return payload


def serialize_market_context_golden_benchmark_report(
    report: MarketContextGoldenBenchmarkReport,
) -> str:
    return json.dumps(
        market_context_golden_benchmark_report_to_dict(report),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )


def parse_market_context_golden_benchmark_report(
    value: str | bytes,
) -> MarketContextGoldenBenchmarkReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("market-context golden benchmark report is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("market-context golden benchmark report must be a JSON object")

    payload = dict(raw)
    persisted_ready = payload.pop("ready_for_phase_three_acceptance", None)
    persisted_failed = payload.pop("failed_scenarios", None)
    raw_scenarios = payload.get("scenarios")
    persisted_outcomes: list[object] = []
    persisted_failures: list[object] = []
    if isinstance(raw_scenarios, list):
        for raw_scenario in raw_scenarios:
            if isinstance(raw_scenario, dict):
                persisted_outcomes.append(raw_scenario.pop("passed", None))
                persisted_failures.append(raw_scenario.pop("failure_codes", None))

    report = MarketContextGoldenBenchmarkReport.model_validate(payload)
    expected_outcomes = [item.passed for item in report.scenarios]
    expected_failures = [[code.value for code in item.failure_codes] for item in report.scenarios]
    if persisted_outcomes and persisted_outcomes != expected_outcomes:
        raise ValueError("market-context golden scenario outcomes are inconsistent")
    if persisted_failures and persisted_failures != expected_failures:
        raise ValueError("market-context golden scenario failures are inconsistent")
    if persisted_failed is not None and persisted_failed != [
        item.value for item in report.failed_scenarios
    ]:
        raise ValueError("market-context golden failed scenarios are inconsistent")
    if (
        persisted_ready is not None
        and persisted_ready is not report.ready_for_phase_three_acceptance
    ):
        raise ValueError("market-context golden acceptance decision is inconsistent")
    return report
