from decimal import Decimal

from scripts.benchmark_background_job_workloads import build_background_job_evidence

from trd_bot.job_capacity import (
    BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
    BackgroundJobWorkload,
    build_background_job_workloads,
)
from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data import (
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
)


def queue_evidence(*, observed_count: int = 250) -> CapacityEvidence:
    return CapacityEvidence(
        scope=CapacityEvidenceScope.BACKGROUND_JOBS,
        method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
        complete=False,
        observed_count=observed_count,
        metrics={
            "enqueue_latency_p95_ms": Decimal("1"),
            "claim_latency_p95_ms": Decimal("1"),
            "terminal_write_latency_p95_ms": Decimal("1"),
            "queue_wait_p50_ms": Decimal("2"),
            "queue_wait_p95_ms": Decimal("3"),
            "synthetic_job_throughput_per_second": Decimal("100"),
        },
        limitation="Real workload runtimes are measured by the dedicated runner.",
    )


def fake_workloads() -> dict[BackgroundJobKind, BackgroundJobWorkload]:
    return {
        kind: BackgroundJobWorkload(
            kind=kind,
            fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
            dimensions=(("units", 1),),
            execute=lambda: None,
        )
        for kind in BackgroundJobKind
    }


def test_real_workload_fixtures_cover_and_execute_every_job_kind() -> None:
    workloads = build_background_job_workloads()

    assert set(workloads) == set(BackgroundJobKind)
    assert {workload.fixture_version for workload in workloads.values()} == {
        BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION
    }

    for workload in workloads.values():
        workload.execute()


def test_background_job_evidence_combines_queue_and_real_runtime_samples() -> None:
    evidence = build_background_job_evidence(
        queue_evidence=queue_evidence(),
        workloads=fake_workloads(),
        samples_per_kind=20,
        warmup_iterations=1,
    )

    assert evidence.complete is True
    assert evidence.observed_count == 350
    assert evidence.metrics["queue_wait_p95_ms"] == 3
    for kind in BackgroundJobKind:
        prefix = f"{kind.value}."
        assert evidence.metrics[f"{prefix}samples"] == 20
        assert evidence.metrics[f"{prefix}success_fraction"] == 1
        assert evidence.metrics[f"{prefix}failure_count"] == 0
        assert evidence.metrics[f"{prefix}runtime_p95_seconds"] >= 0


def test_background_job_evidence_stays_incomplete_below_both_sample_floors() -> None:
    evidence = build_background_job_evidence(
        queue_evidence=queue_evidence(observed_count=249),
        workloads=fake_workloads(),
        samples_per_kind=19,
        warmup_iterations=0,
    )

    assert evidence.complete is False
    assert evidence.limitation is not None
    assert "250" in evidence.limitation
    assert "20" in evidence.limitation


def test_background_job_evidence_fails_closed_when_one_workload_raises() -> None:
    workloads = fake_workloads()

    def fail() -> None:
        raise RuntimeError("synthetic test failure")

    workloads[BackgroundJobKind.OPTIMIZATION_EXECUTION] = BackgroundJobWorkload(
        kind=BackgroundJobKind.OPTIMIZATION_EXECUTION,
        fixture_version=BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
        dimensions=(("units", 1),),
        execute=fail,
    )
    evidence = build_background_job_evidence(
        queue_evidence=queue_evidence(),
        workloads=workloads,
        samples_per_kind=20,
        warmup_iterations=1,
    )

    assert evidence.complete is False
    assert evidence.metrics["optimization_execution.failure_count"] == 21
    assert evidence.limitation is not None
    assert "failed 21 time(s)" in evidence.limitation
