from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from trd_bot.domain.market_data import Timeframe
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    MarketDataRetentionPolicy,
    TimeframeServiceLevel,
    default_market_data_service_level_policy,
    merge_capacity_benchmark_reports,
    parse_capacity_benchmark_report,
    serialize_capacity_benchmark_report,
)


def measured_evidence(scope: CapacityEvidenceScope) -> CapacityEvidence:
    return CapacityEvidence(
        scope=scope,
        method=(
            CapacityEvidenceMethod.LIVE_PROBE
            if scope is CapacityEvidenceScope.PROVIDER
            else CapacityEvidenceMethod.SYNTHETIC_BENCHMARK
        ),
        complete=True,
        observed_count=100,
        metrics={"latency_p95_ms": Decimal("1.25")},
    )


def test_default_policy_covers_all_supported_timeframes_and_providers() -> None:
    policy = default_market_data_service_level_policy()

    assert {item.timeframe for item in policy.timeframes} == set(Timeframe)
    assert {item.provider_id for item in policy.providers} == {
        "binance-public",
        "kraken-public",
        "nobitex-public",
    }
    assert policy.for_timeframe(Timeframe.HOUR_1).allowed_lateness_seconds == 300
    assert policy.for_provider("nobitex-public").sustained_requests_per_minute == 10
    assert policy.capacity.worker_concurrency == 1
    assert policy.retention.finalized_window_days is None


def test_timeframe_policy_rejects_invalid_polling_and_finalization_budgets() -> None:
    with pytest.raises(ValidationError, match="polling interval"):
        TimeframeServiceLevel(
            timeframe=Timeframe.MINUTES_15,
            polling_interval_seconds=900,
            allowed_lateness_seconds=180,
            maximum_future_clock_skew_seconds=30,
            provisional_freshness_p95_seconds=900,
            finalized_freshness_p95_seconds=1_080,
            minimum_eligible_window_success_fraction=Decimal("0.99"),
        )

    with pytest.raises(ValidationError, match="polling and lateness"):
        TimeframeServiceLevel(
            timeframe=Timeframe.HOUR_1,
            polling_interval_seconds=120,
            allowed_lateness_seconds=300,
            maximum_future_clock_skew_seconds=30,
            provisional_freshness_p95_seconds=300,
            finalized_freshness_p95_seconds=419,
            minimum_eligible_window_success_fraction=Decimal("0.99"),
        )


def test_retention_policy_preserves_dedupe_and_revision_evidence() -> None:
    with pytest.raises(ValidationError, match="deduplication must outlive"):
        MarketDataRetentionPolicy(
            raw_observation_days=30,
            normalized_event_days=90,
            inbox_deduplication_days=60,
            delivered_outbox_days=7,
            failed_outbox_days=30,
            provisional_window_days_after_finalization=30,
            finalized_window_days=None,
            revision_evidence_days=365,
            benchmark_evidence_days=365,
        )

    with pytest.raises(ValidationError, match="revision evidence must outlive"):
        MarketDataRetentionPolicy(
            raw_observation_days=30,
            normalized_event_days=90,
            inbox_deduplication_days=180,
            delivered_outbox_days=7,
            failed_outbox_days=30,
            provisional_window_days_after_finalization=30,
            finalized_window_days=None,
            revision_evidence_days=90,
            benchmark_evidence_days=365,
        )


def test_unavailable_evidence_is_explicit_and_contains_no_metrics() -> None:
    evidence = CapacityEvidence(
        scope=CapacityEvidenceScope.DATABASE,
        method=CapacityEvidenceMethod.UNAVAILABLE,
        complete=False,
        observed_count=0,
        limitation="PostgreSQL was not available in this environment.",
    )

    assert evidence.metrics == {}

    with pytest.raises(ValidationError, match="requires only a limitation"):
        CapacityEvidence(
            scope=CapacityEvidenceScope.DATABASE,
            method=CapacityEvidenceMethod.UNAVAILABLE,
            complete=False,
            observed_count=1,
            metrics={"query_latency_p95_ms": Decimal("10")},
            limitation="PostgreSQL was not available in this environment.",
        )


def test_capacity_report_lists_missing_scopes_and_fails_closed() -> None:
    report = CapacityBenchmarkReport(
        environment_label="developer-mac",
        commit_sha="a" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="macOS-arm64",
        evidence=(
            measured_evidence(CapacityEvidenceScope.EVENT_PROCESSING),
            CapacityEvidence(
                scope=CapacityEvidenceScope.DATABASE,
                method=CapacityEvidenceMethod.UNAVAILABLE,
                complete=False,
                observed_count=0,
                limitation="Reference PostgreSQL benchmark has not run.",
            ),
        ),
    )

    assert report.ready_to_freeze is False
    assert set(report.missing_scopes) == {
        CapacityEvidenceScope.PROVIDER,
        CapacityEvidenceScope.DATABASE,
        CapacityEvidenceScope.BACKGROUND_JOBS,
        CapacityEvidenceScope.STORAGE,
    }


def test_capacity_report_is_ready_only_with_every_measured_scope() -> None:
    report = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="b" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=tuple(measured_evidence(scope) for scope in CapacityEvidenceScope),
    )

    assert report.missing_scopes == ()
    assert report.ready_to_freeze is True


def test_capacity_report_rejects_duplicate_scopes() -> None:
    with pytest.raises(ValidationError, match="duplicate evidence scopes"):
        CapacityBenchmarkReport(
            environment_label="reference",
            commit_sha="c" * 40,
            generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
            python_version="3.12.10",
            platform="linux-x86_64",
            evidence=(
                measured_evidence(CapacityEvidenceScope.EVENT_PROCESSING),
                measured_evidence(CapacityEvidenceScope.EVENT_PROCESSING),
            ),
        )


def test_capacity_report_round_trip_verifies_derived_gate_fields() -> None:
    report = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="d" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(measured_evidence(CapacityEvidenceScope.EVENT_PROCESSING),),
    )

    serialized = serialize_capacity_benchmark_report(report)

    assert parse_capacity_benchmark_report(serialized) == report

    inconsistent = serialized.replace('"ready_to_freeze": false', '"ready_to_freeze": true')
    with pytest.raises(ValueError, match="freeze decision is inconsistent"):
        parse_capacity_benchmark_report(inconsistent)


def test_capacity_reports_merge_only_for_the_same_environment() -> None:
    event_report = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="e" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(measured_evidence(CapacityEvidenceScope.EVENT_PROCESSING),),
    )
    provider_report = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="e" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(measured_evidence(CapacityEvidenceScope.PROVIDER),),
    )

    merged = merge_capacity_benchmark_reports((event_report, provider_report))

    assert {item.scope for item in merged.evidence} == {
        CapacityEvidenceScope.PROVIDER,
        CapacityEvidenceScope.EVENT_PROCESSING,
    }
    assert merged.ready_to_freeze is False

    incompatible = provider_report.model_copy(update={"platform": "macOS-arm64"})
    with pytest.raises(ValueError, match="same reference environment"):
        merge_capacity_benchmark_reports((event_report, incompatible))


def test_capacity_report_merge_preserves_complementary_scope_metrics() -> None:
    complete = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="f" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.STORAGE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=100_000,
                metrics={"events_total_bytes": Decimal(100_000_000)},
            ),
        ),
    )
    projection = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="f" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.STORAGE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=False,
                observed_count=20_000,
                metrics={"projected_events_per_30_days": Decimal(3_810)},
                limitation="Projection is incomplete without PostgreSQL row evidence.",
            ),
        ),
    )

    merged = merge_capacity_benchmark_reports((complete, projection))

    assert merged.evidence[0].complete is True
    assert merged.evidence[0].metrics == {
        "events_total_bytes": Decimal(100_000_000),
        "projected_events_per_30_days": Decimal(3_810),
    }


def test_capacity_report_merge_rejects_conflicting_scope_metrics() -> None:
    first = CapacityBenchmarkReport(
        environment_label="reference",
        commit_sha="1" * 40,
        generated_at=datetime(2026, 10, 9, 20, tzinfo=UTC),
        python_version="3.12.10",
        platform="linux-x86_64",
        evidence=(measured_evidence(CapacityEvidenceScope.DATABASE),),
    )
    conflicting = first.model_copy(
        update={
            "evidence": (
                CapacityEvidence(
                    scope=CapacityEvidenceScope.DATABASE,
                    method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                    complete=False,
                    observed_count=10,
                    metrics={"latency_p95_ms": Decimal("2.50")},
                    limitation="Partial benchmark disagrees with the complete report.",
                ),
            )
        }
    )

    with pytest.raises(ValueError, match="conflicting metric"):
        merge_capacity_benchmark_reports((first, conflicting))
