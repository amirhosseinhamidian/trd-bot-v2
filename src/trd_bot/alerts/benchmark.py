import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from trd_bot.alerts.contracts import (
    AlertSourceKind,
    build_alert_deduplication_key,
    build_alert_id,
    build_alert_rule_id,
)
from trd_bot.alerts.evaluations import build_alert_evaluation_id
from trd_bot.alerts.outcomes import alert_outcome_policy_checksum, build_alert_outcome_id
from trd_bot.alerts.publication import AlertPublicationPolicy
from trd_bot.alerts.simulations import AlertSimulationMode, build_alert_simulation_id

ALERT_PIPELINE_BENCHMARK_FIXTURE_VERSION = "alert-pipeline-golden-v1"
ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES = 100
ALERT_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS = Decimal("5")


def _checksum(value: object) -> str:
    encoded = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _percentile(values: list[Decimal], percentile: Decimal) -> Decimal:
    ordered = sorted(values)
    index = int((Decimal(len(ordered) - 1) * percentile).to_integral_value())
    return ordered[index]


def alert_pipeline_benchmark_fixture_checksum() -> str:
    return _checksum(
        {
            "fixture_version": ALERT_PIPELINE_BENCHMARK_FIXTURE_VERSION,
            "modes": [mode.value for mode in AlertSimulationMode],
            "outcome_policy_checksum": alert_outcome_policy_checksum(),
            "publication_policy_checksum": AlertPublicationPolicy.default().policy_checksum,
            "source_kind": AlertSourceKind.MARKET_CONTEXT.value,
        }
    )


class AlertPipelineBenchmarkReport(BaseModel):
    """Same-SHA, tamper-evident synthetic evidence for the P4 alert path."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["alert-pipeline-benchmark-v1"] = "alert-pipeline-benchmark-v1"
    fixture_version: Literal["alert-pipeline-golden-v1"] = "alert-pipeline-golden-v1"
    fixture_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    publication_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    outcome_policy_checksum: str = Field(pattern=r"^[a-f0-9]{64}$")
    commit_sha: str = Field(pattern=r"^[a-f0-9]{40}$")
    environment_label: str = Field(min_length=1, max_length=64)
    generated_at: datetime
    python_version: str = Field(min_length=1, max_length=50)
    platform: str = Field(min_length=1, max_length=200)
    requested_samples: int = Field(ge=1)
    successful_samples: int = Field(ge=0)
    unique_output_fingerprints: tuple[str, ...]
    runtime_p50_ms: Decimal = Field(ge=0)
    runtime_p95_ms: Decimal = Field(ge=0)
    runtime_budget_ms: Decimal = Field(gt=0)

    @field_validator("generated_at")
    @classmethod
    def normalize_generated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("benchmark timestamp must include timezone information")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.fixture_checksum != alert_pipeline_benchmark_fixture_checksum():
            raise ValueError("alert benchmark fixture checksum is not canonical")
        if self.publication_policy_checksum != AlertPublicationPolicy.default().policy_checksum:
            raise ValueError("alert publication policy checksum is not canonical")
        if self.outcome_policy_checksum != alert_outcome_policy_checksum():
            raise ValueError("alert outcome policy checksum is not canonical")
        if self.successful_samples > self.requested_samples:
            raise ValueError("successful samples cannot exceed requested samples")
        return self

    @property
    def passed(self) -> bool:
        return (
            self.requested_samples >= ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES
            and self.successful_samples == self.requested_samples
            and len(self.unique_output_fingerprints) == 1
            and self.runtime_p95_ms <= self.runtime_budget_ms
        )


def run_alert_pipeline_benchmark(
    *, samples: int, commit_sha: str, environment_label: str
) -> AlertPipelineBenchmarkReport:
    runtimes: list[Decimal] = []
    fingerprints: set[str] = set()
    for _ in range(samples):
        started = perf_counter()
        rule_id = build_alert_rule_id(rule_key="golden.trending-up")
        source_event_id = "market-regime-0123456789abcdef"
        alert_id = build_alert_id(
            rule_id=rule_id,
            rule_version=1,
            source_kind=AlertSourceKind.MARKET_CONTEXT,
            source_event_id=source_event_id,
        )
        evaluation_id = build_alert_evaluation_id(
            rule_id=rule_id,
            rule_version=1,
            source_kind=AlertSourceKind.MARKET_CONTEXT,
            source_event_id=source_event_id,
        )
        dedupe = build_alert_deduplication_key(
            rule_id=rule_id,
            rule_version=1,
            source_kind=AlertSourceKind.MARKET_CONTEXT,
            source_event_id=source_event_id,
        )
        simulations = tuple(
            build_alert_simulation_id(alert_id=alert_id, mode=mode, horizon_seconds=3_600)
            for mode in AlertSimulationMode
        )
        outcomes = tuple(build_alert_outcome_id(item) for item in simulations)
        fingerprints.add(
            _checksum(
                {
                    "alert_id": alert_id,
                    "deduplication_key": dedupe,
                    "evaluation_id": evaluation_id,
                    "outcomes": outcomes,
                    "simulations": simulations,
                }
            )
        )
        runtimes.append(Decimal(str((perf_counter() - started) * 1_000)))
    return AlertPipelineBenchmarkReport(
        fixture_checksum=alert_pipeline_benchmark_fixture_checksum(),
        publication_policy_checksum=AlertPublicationPolicy.default().policy_checksum,
        outcome_policy_checksum=alert_outcome_policy_checksum(),
        commit_sha=commit_sha,
        environment_label=environment_label,
        generated_at=datetime.now(UTC),
        python_version=platform.python_version() or sys.version.split()[0],
        platform=platform.platform(),
        requested_samples=samples,
        successful_samples=len(runtimes),
        unique_output_fingerprints=tuple(sorted(fingerprints)),
        runtime_p50_ms=_percentile(runtimes, Decimal("0.50")),
        runtime_p95_ms=_percentile(runtimes, Decimal("0.95")),
        runtime_budget_ms=ALERT_PIPELINE_BENCHMARK_RUNTIME_BUDGET_MS,
    )


def serialize_alert_pipeline_benchmark_report(report: AlertPipelineBenchmarkReport) -> str:
    payload = report.model_dump(mode="json")
    payload["passed"] = report.passed
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)


def parse_alert_pipeline_benchmark_report(value: str | bytes) -> AlertPipelineBenchmarkReport:
    try:
        raw = json.loads(value)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("alert pipeline benchmark is not valid JSON") from exc
    if not isinstance(raw, dict):
        raise ValueError("alert pipeline benchmark must be a JSON object")
    payload = dict(raw)
    persisted_passed = payload.pop("passed", None)
    report = AlertPipelineBenchmarkReport.model_validate(payload)
    if persisted_passed is not None and persisted_passed is not report.passed:
        raise ValueError("alert pipeline benchmark decision is inconsistent")
    return report
