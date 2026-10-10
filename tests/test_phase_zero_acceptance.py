import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from scripts import freeze_v0_3_phase_zero

from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    serialize_capacity_benchmark_report,
)
from trd_bot.phase_zero_acceptance import (
    default_phase_zero_acceptance_matrix,
    evaluate_phase_zero_acceptance,
    parse_phase_zero_freeze_record,
    serialize_phase_zero_freeze_record,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
GENERATED_AT = datetime(2026, 10, 10, 8, tzinfo=UTC)


def provider_metrics(*, failure_fraction: str = "0") -> dict[str, Decimal]:
    metrics: dict[str, Decimal] = {}
    for provider_id in ("nobitex-public", "kraken-public"):
        prefix = f"{provider_id}."
        metrics[f"{prefix}samples"] = Decimal(30)
        metrics[f"{prefix}success_fraction"] = Decimal(1) - Decimal(failure_fraction)
        metrics[f"{prefix}failure_fraction"] = Decimal(failure_fraction)
        metrics[f"{prefix}http_latency_p50_ms"] = Decimal(100)
        metrics[f"{prefix}http_latency_p95_ms"] = Decimal(200)
    return metrics


def complete_report(
    *,
    provider_failure_fraction: str = "0",
    event_throughput: str = "2000",
) -> CapacityBenchmarkReport:
    job_metrics = {
        "queue_wait_p95_ms": Decimal(100),
        **{f"{kind.value}.runtime_p95_seconds": Decimal(1) for kind in BackgroundJobKind},
    }
    return CapacityBenchmarkReport(
        environment_label="macbook-pro-reference",
        commit_sha="a" * 40,
        generated_at=GENERATED_AT,
        python_version="3.12.14",
        platform="macOS-x86_64",
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.PROVIDER,
                method=CapacityEvidenceMethod.LIVE_PROBE,
                complete=True,
                observed_count=60,
                metrics=provider_metrics(failure_fraction=provider_failure_fraction),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.EVENT_PROCESSING,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=20_000,
                metrics={
                    "contract_latency_p95_ms": Decimal(2),
                    "contract_throughput_per_second": Decimal(event_throughput),
                },
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.DATABASE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=200,
                metrics={
                    "inbox_lookup_latency_p95_ms": Decimal(5),
                    "current_window_latency_p95_ms": Decimal(6),
                    "time_range_latency_p95_ms": Decimal(7),
                    "pool_utilization_p95_fraction": Decimal("0.2"),
                    "event_count": Decimal(100_000),
                },
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.BACKGROUND_JOBS,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=350,
                metrics=job_metrics,
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.STORAGE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=100_000,
                metrics={
                    "events_total_bytes": Decimal(100_000_000),
                    "projected_events_per_30_days": Decimal(3_810),
                },
            ),
        ),
    )


def evaluate(report: CapacityBenchmarkReport):  # type: ignore[no-untyped-def]
    return evaluate_phase_zero_acceptance(
        capacity_report=report,
        primary_provider="nobitex-public",
        fallback_providers=("kraken-public",),
        repository_root=REPOSITORY_ROOT,
        generated_at=GENERATED_AT,
    )


def test_default_matrix_assigns_owner_phase_and_evidence_to_every_decision() -> None:
    matrix = default_phase_zero_acceptance_matrix()

    assert len(matrix.requirements) == 8
    assert all(item.owner for item in matrix.requirements)
    assert all(item.delivery_phase for item in matrix.requirements)
    assert all(item.evidence_references for item in matrix.requirements)


def test_complete_evidence_and_eligible_provider_order_freeze_phase_zero() -> None:
    record = evaluate(complete_report())

    assert record.ready_to_freeze is True
    assert record.missing_requirements == ()
    assert len(record.capacity_report_checksum) == 64
    assert all(check.passed for check in record.checks)
    capacity_check = next(check for check in record.checks if check.requirement_id == "P0-A07")
    assert capacity_check.observations["projected_actual_storage_bytes_per_30_days"] == Decimal(
        3_810_000
    )


def test_provider_budget_failure_blocks_provider_selection() -> None:
    record = evaluate(complete_report(provider_failure_fraction="0.02"))
    provider_check = next(check for check in record.checks if check.requirement_id == "P0-A06")

    assert record.ready_to_freeze is False
    assert provider_check.passed is False
    assert any("failure budget" in reason for reason in provider_check.failure_reasons)


def test_capacity_target_failure_blocks_phase_zero_freeze() -> None:
    record = evaluate(complete_report(event_throughput="999"))
    capacity_check = next(check for check in record.checks if check.requirement_id == "P0-A07")

    assert record.ready_to_freeze is False
    assert capacity_check.passed is False
    assert any("below its target" in reason for reason in capacity_check.failure_reasons)


def test_missing_capacity_scopes_fail_closed_without_hiding_repository_acceptance() -> None:
    incomplete = complete_report().model_copy(update={"evidence": complete_report().evidence[:2]})
    record = evaluate(incomplete)

    assert record.ready_to_freeze is False
    assert {"P0-A07"}.issubset(record.missing_requirements)
    assert next(check for check in record.checks if check.requirement_id == "P0-A01").passed


def test_freeze_record_round_trip_rejects_a_tampered_decision() -> None:
    record = evaluate(complete_report())
    serialized = serialize_phase_zero_freeze_record(record)

    assert parse_phase_zero_freeze_record(serialized) == record
    tampered = serialized.replace('"ready_to_freeze": true', '"ready_to_freeze": false')
    with pytest.raises(ValueError, match="freeze decision is inconsistent"):
        parse_phase_zero_freeze_record(tampered)

    missing_check = json.loads(serialized)
    missing_check["checks"] = missing_check["checks"][:-1]
    missing_check.pop("ready_to_freeze")
    missing_check.pop("missing_requirements")
    with pytest.raises(ValueError, match="every frozen requirement ID"):
        parse_phase_zero_freeze_record(json.dumps(missing_check))


def test_freeze_cli_writes_a_complete_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capacity_path = tmp_path / "reference-capacity.json"
    output_path = tmp_path / "phase-zero-freeze.json"
    capacity_path.write_text(
        serialize_capacity_benchmark_report(complete_report()),
        encoding="utf-8",
    )
    monkeypatch.setattr(freeze_v0_3_phase_zero, "_commit_sha", lambda: "a" * 40)
    monkeypatch.setattr(
        "sys.argv",
        [
            "freeze_v0_3_phase_zero.py",
            "--capacity-report",
            str(capacity_path),
            "--primary-provider",
            "nobitex-public",
            "--fallback-provider",
            "kraken-public",
            "--output",
            str(output_path),
        ],
    )

    assert freeze_v0_3_phase_zero.main() == 0
    assert parse_phase_zero_freeze_record(output_path.read_bytes()).ready_to_freeze
