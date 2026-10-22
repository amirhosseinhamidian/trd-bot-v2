import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from scripts import benchmark_v0_3_release_capacity as benchmark_script
from scripts.benchmark_v0_3_release_capacity import (
    validate_release_benchmark_database_url,
)

from trd_bot.jobs import BackgroundJobKind
from trd_bot.release_capacity import (
    QueuePressureLevel,
    ReleaseCapacityObservations,
    build_release_capacity_report,
    classify_queue_pressure,
    default_release_capacity_policy,
    evaluate_release_capacity,
    parse_release_capacity_report,
    serialize_release_capacity_report,
)

COMMIT_SHA = "a" * 40
GENERATED_AT = datetime(2026, 10, 21, 18, tzinfo=UTC)
EXPECTED_POLICY_CHECKSUM = "8a6e4210cc88bdeb051fa879399a91baac6d94d4d9a143d3804c8fdf5ebdf76a"
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def passing_observations() -> ReleaseCapacityObservations:
    return ReleaseCapacityObservations(
        requested_jobs=100,
        covered_job_kinds=tuple(sorted(kind.value for kind in BackgroundJobKind)),
        overload_depth_observed=100,
        overload_level=QueuePressureLevel.OVERLOAD,
        succeeded_jobs=100,
        failed_jobs=0,
        remaining_active_jobs=0,
        enqueue_latency_p95_milliseconds=Decimal("2.5"),
        queue_wait_p95_milliseconds=Decimal("100"),
        worker_cycle_latency_p95_milliseconds=Decimal("3.5"),
        overload_drain_throughput_per_second=Decimal("50"),
        duplicate_enqueue_attempts=8,
        duplicate_created_count=1,
        duplicate_unique_job_count=1,
        contention_workers=8,
        contention_claim_winner_count=1,
        contention_unique_job_count=1,
        recovery_attempt_count=2,
        recovery_reused_job=True,
        stale_owner_fenced=True,
        retry_attempt_count=2,
        retry_reused_job=True,
        recovery_transition_milliseconds=Decimal("4"),
        cleanup_verified=True,
    )


def test_release_capacity_policy_matches_the_frozen_service_level_budget() -> None:
    policy = default_release_capacity_policy()

    assert policy.queue_warning_depth == 25
    assert policy.queue_overload_depth == 100
    assert policy.worker_concurrency == 1
    assert policy.minimum_contention_workers == 8
    assert policy.database_operation_p95_budget_milliseconds == 250
    assert policy.queue_wait_p95_budget_milliseconds == 10_000
    assert policy.minimum_overload_drain_throughput_per_second == 10
    assert policy.definition_checksum == EXPECTED_POLICY_CHECKSUM


@pytest.mark.parametrize(
    ("depth", "expected"),
    [
        (0, QueuePressureLevel.NORMAL),
        (24, QueuePressureLevel.NORMAL),
        (25, QueuePressureLevel.WARNING),
        (99, QueuePressureLevel.WARNING),
        (100, QueuePressureLevel.OVERLOAD),
    ],
)
def test_queue_pressure_boundaries_are_explicit(
    depth: int,
    expected: QueuePressureLevel,
) -> None:
    assert classify_queue_pressure(depth) is expected


def test_release_capacity_report_round_trips_with_derived_checksums() -> None:
    report = build_release_capacity_report(
        environment_label="unit-test",
        commit_sha=COMMIT_SHA,
        generated_at=GENERATED_AT,
        python_version="3.13.7",
        platform="test-platform",
        observations=passing_observations(),
    )

    assert report.passed is True
    assert report.failure_reasons == ()
    assert parse_release_capacity_report(serialize_release_capacity_report(report)) == report
    assert len(report.report_checksum) == 64


def test_release_capacity_fails_closed_for_overload_and_recovery_regressions() -> None:
    observations = passing_observations().model_copy(
        update={
            "overload_depth_observed": 99,
            "overload_level": QueuePressureLevel.WARNING,
            "stale_owner_fenced": False,
        }
    )

    reasons = evaluate_release_capacity(default_release_capacity_policy(), observations)

    assert "release queue did not expose the overload state" in reasons
    assert "release expired-lease recovery or stale-owner fencing failed" in reasons


def test_release_capacity_fails_closed_when_performance_budget_is_exceeded() -> None:
    observations = passing_observations().model_copy(
        update={
            "enqueue_latency_p95_milliseconds": Decimal("251"),
            "queue_wait_p95_milliseconds": Decimal("10001"),
            "overload_drain_throughput_per_second": Decimal("9.99"),
        }
    )

    reasons = evaluate_release_capacity(default_release_capacity_policy(), observations)

    assert "release enqueue latency exceeded the database p95 budget" in reasons
    assert "release queue wait exceeded the p95 budget" in reasons
    assert "release overload drain throughput is below the minimum budget" in reasons


def test_release_capacity_parser_rejects_tampering() -> None:
    report = build_release_capacity_report(
        environment_label="unit-test",
        commit_sha=COMMIT_SHA,
        generated_at=GENERATED_AT,
        python_version="3.13.7",
        platform="test-platform",
        observations=passing_observations(),
    )
    payload = json.loads(serialize_release_capacity_report(report))
    payload["observations"]["enqueue_latency_p95_milliseconds"] = "2.6"

    with pytest.raises(ValueError, match="checksum is inconsistent"):
        parse_release_capacity_report(json.dumps(payload))


@pytest.mark.parametrize(
    "database_url",
    [
        None,
        "",
        "sqlite+pysqlite:///:memory:",
        "postgresql+psycopg://localhost/trd_bot",
        "postgresql+psycopg://localhost/production",
    ],
)
def test_release_capacity_rejects_unsafe_database_targets(database_url: str | None) -> None:
    with pytest.raises(ValueError):
        validate_release_benchmark_database_url(database_url)


def test_release_capacity_accepts_dedicated_test_or_benchmark_database() -> None:
    test_url = "postgresql+psycopg://localhost/trd_bot_test"
    benchmark_url = "postgresql+psycopg://localhost/trd_bot_benchmark"

    assert validate_release_benchmark_database_url(test_url) == test_url
    assert validate_release_benchmark_database_url(benchmark_url) == benchmark_url


def test_release_capacity_preserves_preflight_error_without_schema_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = Mock()
    cleanup = Mock()
    monkeypatch.setattr(benchmark_script, "create_database_engine", lambda _: engine)
    monkeypatch.setattr(benchmark_script, "create_session_factory", lambda _: object())
    monkeypatch.setattr(
        benchmark_script,
        "_assert_current_migration_head",
        Mock(side_effect=ValueError("database is not at migration head")),
    )
    monkeypatch.setattr(benchmark_script, "_cleanup", cleanup)

    with pytest.raises(ValueError, match="database is not at migration head"):
        benchmark_script.run_release_capacity_benchmark(
            database_url="postgresql+psycopg://localhost/trd_bot_test",
            environment_label="unit-test",
            commit_sha=COMMIT_SHA,
            job_count=100,
            contention_workers=8,
        )

    cleanup.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_release_capacity_runbook_migrates_the_explicit_benchmark_database() -> None:
    runbook = (REPOSITORY_ROOT / "docs/v0.3/49-capacity-overload-recovery-benchmark.md").read_text(
        encoding="utf-8"
    )

    assert 'TRD_BOT_DATABASE_URL="$TRD_BOT_TEST_DATABASE_URL"' in runbook
    assert '--database-url "$TRD_BOT_TEST_DATABASE_URL"' in runbook
