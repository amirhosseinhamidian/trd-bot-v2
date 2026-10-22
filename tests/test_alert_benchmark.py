import json
from datetime import UTC, datetime

import pytest

from trd_bot.alerts import (
    ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
    AlertPipelineBenchmarkReport,
    parse_alert_pipeline_benchmark_report,
    run_alert_pipeline_benchmark,
    serialize_alert_pipeline_benchmark_report,
)


def test_alert_benchmark_is_deterministic_and_within_budget() -> None:
    report = run_alert_pipeline_benchmark(
        samples=ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )

    assert report.passed is True
    assert report.successful_samples == report.requested_samples
    assert len(report.unique_output_fingerprints) == 1
    assert (
        parse_alert_pipeline_benchmark_report(serialize_alert_pipeline_benchmark_report(report))
        == report
    )


def test_alert_benchmark_parser_rejects_tampered_decision() -> None:
    report = run_alert_pipeline_benchmark(
        samples=ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )
    payload = json.loads(serialize_alert_pipeline_benchmark_report(report))
    payload["passed"] = False

    with pytest.raises(ValueError, match="decision is inconsistent"):
        parse_alert_pipeline_benchmark_report(json.dumps(payload))


def test_report_rejects_noncanonical_policy_checksum() -> None:
    report = run_alert_pipeline_benchmark(
        samples=ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )
    payload = report.model_dump()
    payload["outcome_policy_checksum"] = "0" * 64

    with pytest.raises(ValueError, match="outcome policy checksum"):
        AlertPipelineBenchmarkReport.model_validate(payload)


def test_report_requires_timezone_aware_timestamp() -> None:
    report = run_alert_pipeline_benchmark(
        samples=ALERT_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
        commit_sha="a" * 40,
        environment_label="test-reference",
    )

    with pytest.raises(ValueError, match="timezone"):
        AlertPipelineBenchmarkReport.model_validate(
            {**report.model_dump(), "generated_at": datetime(2026, 10, 19)}
        )

    assert report.generated_at.tzinfo is UTC
