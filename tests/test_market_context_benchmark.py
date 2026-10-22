import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError
from scripts import benchmark_market_context

from trd_bot.domain.market_data import Timeframe
from trd_bot.market_context import (
    MARKET_CONTEXT_GOLDEN_FIXTURE_VERSION,
    MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
    MarketContextGoldenBenchmarkReport,
    MarketContextGoldenFailureCode,
    MarketContextGoldenScenarioId,
    build_market_context_golden_windows,
    execute_market_context_golden_scenario,
    market_context_golden_fixture_v1,
    parse_market_context_golden_benchmark_report,
    run_market_context_golden_benchmark,
    serialize_market_context_golden_benchmark_report,
)

COMMIT_SHA = "a" * 40
GENERATED_AT = datetime(2026, 10, 17, 8, tzinfo=UTC)


def test_golden_fixture_freezes_inputs_outputs_and_contract_checksums() -> None:
    fixture = market_context_golden_fixture_v1()

    assert fixture.fixture_version == MARKET_CONTEXT_GOLDEN_FIXTURE_VERSION
    assert fixture.definition_checksum == (
        "79d082e0a2152032b033fc31d5cbb419d807b6669d93c2d2f5a994b6807ff521"
    )
    assert tuple(item.scenario_id.value for item in fixture.scenarios) == (
        "trending_up_low",
        "trending_down_high",
        "ranging_normal",
    )
    assert tuple(
        execute_market_context_golden_scenario(item, fixture=fixture) for item in fixture.scenarios
    ) == tuple(item.expected for item in fixture.scenarios)


def test_golden_window_builder_can_seed_a_current_hourly_acceptance_boundary() -> None:
    current_boundary = datetime(2026, 10, 17, 8, tzinfo=UTC)

    windows = build_market_context_golden_windows(
        MarketContextGoldenScenarioId.TRENDING_UP_LOW,
        as_of=current_boundary,
    )

    assert len(windows) == 56
    hourly = [item for item in windows if item.timeframe is Timeframe.HOUR_1]
    assert hourly[-1].window_end == current_boundary


def test_benchmark_accepts_repeated_golden_outputs_and_records_sanitized_metrics() -> None:
    report = run_market_context_golden_benchmark(
        commit_sha=COMMIT_SHA,
        environment_label="macbook-pro-reference",
        samples_per_scenario=MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
        warmup_iterations=1,
        generated_at=GENERATED_AT,
    )

    assert report.ready_for_phase_three_acceptance is True
    assert report.failed_scenarios == ()
    assert report.scope == "crypto-spot-public-read-only"
    assert report.windows_per_scenario == 56
    assert report.features_per_scenario == 5
    assert report.minimum_samples_per_scenario == 30
    assert all(item.passed for item in report.scenarios)
    assert all(
        item.successful_samples == MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES
        for item in report.scenarios
    )
    assert all(item.failed_samples == 0 for item in report.scenarios)
    assert all(
        item.unique_output_fingerprints == (item.expected.output_fingerprint,)
        for item in report.scenarios
    )
    assert all(item.runtime_p95_ms <= item.runtime_budget_ms for item in report.scenarios)

    serialized = serialize_market_context_golden_benchmark_report(report)
    assert parse_market_context_golden_benchmark_report(serialized) == report
    assert "open_price" not in serialized
    assert "credential" not in serialized


def test_benchmark_fails_closed_below_sample_floor() -> None:
    report = run_market_context_golden_benchmark(
        commit_sha=COMMIT_SHA,
        environment_label="local-fast-check",
        samples_per_scenario=MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES - 1,
        warmup_iterations=0,
        generated_at=GENERATED_AT,
    )

    assert report.ready_for_phase_three_acceptance is False
    assert report.failed_scenarios == tuple(item.scenario_id for item in report.scenarios)
    assert all(
        item.failure_codes == (MarketContextGoldenFailureCode.INSUFFICIENT_SAMPLES,)
        for item in report.scenarios
    )


def test_report_rejects_noncanonical_expected_output_and_tampered_derived_state() -> None:
    report = run_market_context_golden_benchmark(
        commit_sha=COMMIT_SHA,
        environment_label="tamper-test",
        samples_per_scenario=MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
        warmup_iterations=0,
        generated_at=GENERATED_AT,
    )
    payload = report.model_dump()
    first = payload["scenarios"][0]
    second = payload["scenarios"][1]
    first["expected"] = second["expected"]
    with pytest.raises(ValidationError, match="expected output is not canonical"):
        MarketContextGoldenBenchmarkReport.model_validate(payload)

    serialized = json.loads(serialize_market_context_golden_benchmark_report(report))
    serialized["ready_for_phase_three_acceptance"] = False
    with pytest.raises(ValueError, match="acceptance decision is inconsistent"):
        parse_market_context_golden_benchmark_report(json.dumps(serialized))

    serialized = json.loads(serialize_market_context_golden_benchmark_report(report))
    serialized["scenarios"][0]["failure_codes"] = ["golden_mismatch"]
    with pytest.raises(ValueError, match="scenario failures are inconsistent"):
        parse_market_context_golden_benchmark_report(json.dumps(serialized))


def test_cli_requires_same_sha_and_writes_exclusive_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "market-context-golden.json"
    monkeypatch.setattr(benchmark_market_context, "_repository_commit_sha", lambda: COMMIT_SHA)
    monkeypatch.setattr(
        "sys.argv",
        [
            "benchmark_market_context.py",
            "--samples-per-scenario",
            str(MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES),
            "--warmup-iterations",
            "0",
            "--environment-label",
            "macbook-pro-reference",
            "--commit-sha",
            COMMIT_SHA,
            "--output",
            str(output),
        ],
    )

    assert benchmark_market_context.main() == 0
    parsed = parse_market_context_golden_benchmark_report(output.read_bytes())
    assert parsed.commit_sha == COMMIT_SHA
    assert parsed.ready_for_phase_three_acceptance is True

    with pytest.raises(SystemExit) as duplicate:
        benchmark_market_context.main()
    assert duplicate.value.code == 2

    with pytest.raises(ValueError, match="does not match"):
        benchmark_market_context.validate_commit_sha(
            "b" * 40,
            repository_commit_sha=COMMIT_SHA,
        )
