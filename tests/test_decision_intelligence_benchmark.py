import json
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from trd_bot.decision_intelligence import (
    DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
    DecisionPipelineBenchmarkReport,
    parse_decision_pipeline_benchmark_report,
    run_decision_pipeline_benchmark,
    serialize_decision_pipeline_benchmark_report,
)


def test_decision_benchmark_is_deterministic_and_within_budget() -> None:
    report = run_decision_pipeline_benchmark(
        samples=DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )

    assert report.passed is True
    assert report.successful_samples == report.requested_samples
    assert len(report.unique_output_fingerprints) == 1
    assert (
        parse_decision_pipeline_benchmark_report(
            serialize_decision_pipeline_benchmark_report(report)
        )
        == report
    )


def test_decision_benchmark_parser_rejects_tampered_decision() -> None:
    report = run_decision_pipeline_benchmark(
        samples=DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )
    payload = json.loads(serialize_decision_pipeline_benchmark_report(report))
    payload["passed"] = False

    with pytest.raises(ValueError, match="decision is inconsistent"):
        parse_decision_pipeline_benchmark_report(json.dumps(payload))


def test_decision_benchmark_rejects_noncanonical_policy_checksum() -> None:
    report = run_decision_pipeline_benchmark(
        samples=DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )
    payload = report.model_dump()
    payload["risk_policy_checksum"] = "0" * 64

    with pytest.raises(ValueError, match="risk_policy_checksum is not canonical"):
        DecisionPipelineBenchmarkReport.model_validate(payload)


def test_decision_benchmark_rejects_relaxed_runtime_budget() -> None:
    report = run_decision_pipeline_benchmark(
        samples=DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )

    with pytest.raises(ValueError, match="runtime budget is not canonical"):
        DecisionPipelineBenchmarkReport.model_validate(
            {**report.model_dump(), "runtime_budget_ms": Decimal("1000")}
        )


def test_decision_benchmark_requires_timezone_aware_timestamp() -> None:
    report = run_decision_pipeline_benchmark(
        samples=DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )

    with pytest.raises(ValueError, match="timezone"):
        DecisionPipelineBenchmarkReport.model_validate(
            {**report.model_dump(), "generated_at": datetime(2026, 10, 21)}
        )

    assert report.generated_at.tzinfo is UTC
