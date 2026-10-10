#!/usr/bin/env python3
import argparse
import math
import platform
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from trd_bot.job_capacity import (
    BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION,
    BackgroundJobWorkload,
    build_background_job_workloads,
)
from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    default_market_data_service_level_policy,
    parse_capacity_benchmark_report,
    serialize_capacity_benchmark_report,
)

_MIN_REFERENCE_SAMPLES_PER_KIND = 20
_MIN_REFERENCE_QUEUE_SAMPLES = 250
_QUEUE_METRICS = frozenset(
    {
        "enqueue_latency_p95_ms",
        "claim_latency_p95_ms",
        "terminal_write_latency_p95_ms",
        "queue_wait_p50_ms",
        "queue_wait_p95_ms",
        "synthetic_job_throughput_per_second",
    }
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure the versioned real workload for every background-job kind and "
            "combine it with isolated PostgreSQL queue evidence for P0-04."
        )
    )
    parser.add_argument(
        "--queue-report",
        type=Path,
        required=True,
        help="PostgreSQL capacity report from this exact commit and environment.",
    )
    parser.add_argument(
        "--samples-per-kind",
        type=int,
        default=_MIN_REFERENCE_SAMPLES_PER_KIND,
    )
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )
    return result.stdout.strip().lower()


def _percentile(values: Sequence[float], fraction: float) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return Decimal(str(round(ordered[index], 6)))


def _fraction(numerator: int, denominator: int) -> Decimal:
    if denominator <= 0:
        return Decimal(0)
    return Decimal(numerator) / Decimal(denominator)


def _background_evidence(report: CapacityBenchmarkReport) -> CapacityEvidence | None:
    return next(
        (item for item in report.evidence if item.scope is CapacityEvidenceScope.BACKGROUND_JOBS),
        None,
    )


def validate_queue_report_identity(
    report: CapacityBenchmarkReport,
    *,
    commit_sha: str,
) -> None:
    if report.commit_sha != commit_sha:
        raise ValueError("queue report commit does not match the checked-out commit")
    if report.python_version != platform.python_version():
        raise ValueError("queue report Python version does not match this runtime")
    if report.platform != platform.platform():
        raise ValueError("queue report platform does not match this runtime")


def build_background_job_evidence(
    *,
    queue_evidence: CapacityEvidence | None,
    workloads: Mapping[BackgroundJobKind, BackgroundJobWorkload],
    samples_per_kind: int,
    warmup_iterations: int,
) -> CapacityEvidence:
    if not 1 <= samples_per_kind <= 1_000:
        raise ValueError("samples per kind must be between 1 and 1,000")
    if not 0 <= warmup_iterations <= 100:
        raise ValueError("warmup iterations must be between zero and 100")
    if set(workloads) != set(BackgroundJobKind):
        raise ValueError("workloads must cover every background job kind")
    if any(
        workload.kind is not kind
        or workload.fixture_version != BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION
        for kind, workload in workloads.items()
    ):
        raise ValueError("workload kind or fixture version is inconsistent")

    metrics: dict[str, Decimal] = {}
    limitations: list[str] = []
    queue_observations = 0
    queue_complete = False
    if queue_evidence is None:
        limitations.append("PostgreSQL queue evidence is missing.")
    elif queue_evidence.method is CapacityEvidenceMethod.UNAVAILABLE:
        limitations.append("PostgreSQL queue evidence is unavailable.")
    else:
        queue_observations = queue_evidence.observed_count
        missing_metrics = sorted(_QUEUE_METRICS - queue_evidence.metrics.keys())
        metrics.update(
            {
                name: value
                for name, value in queue_evidence.metrics.items()
                if name in _QUEUE_METRICS
            }
        )
        queue_complete = queue_observations >= _MIN_REFERENCE_QUEUE_SAMPLES and not missing_metrics
        if queue_observations < _MIN_REFERENCE_QUEUE_SAMPLES:
            limitations.append(
                "PostgreSQL queue evidence requires at least "
                f"{_MIN_REFERENCE_QUEUE_SAMPLES} lifecycle samples."
            )
        if missing_metrics:
            limitations.append("PostgreSQL queue metrics are incomplete.")

    targets = default_market_data_service_level_policy().capacity.job_runtime_p95_seconds
    workload_failures = 0
    for kind in BackgroundJobKind:
        workload = workloads[kind]
        failures = 0
        for _ in range(warmup_iterations):
            try:
                workload.execute()
            except Exception:
                failures += 1

        runtimes: list[float] = []
        for _ in range(samples_per_kind):
            started_at = time.perf_counter()
            try:
                workload.execute()
            except Exception:
                failures += 1
            else:
                runtimes.append(time.perf_counter() - started_at)

        prefix = f"{kind.value}."
        metrics[f"{prefix}samples"] = Decimal(samples_per_kind)
        metrics[f"{prefix}success_fraction"] = _fraction(
            len(runtimes),
            samples_per_kind,
        )
        metrics[f"{prefix}failure_count"] = Decimal(failures)
        for name, value in workload.dimensions:
            metrics[f"{prefix}fixture_{name}"] = Decimal(value)
        if runtimes:
            runtime_p50 = _percentile(runtimes, 0.50)
            runtime_p95 = _percentile(runtimes, 0.95)
            target = targets[kind.value]
            metrics[f"{prefix}runtime_p50_seconds"] = runtime_p50
            metrics[f"{prefix}runtime_p95_seconds"] = runtime_p95
            metrics[f"{prefix}runtime_target_seconds"] = target
            metrics[f"{prefix}runtime_within_target"] = Decimal(runtime_p95 <= target)
        workload_failures += failures

    workloads_complete = (
        samples_per_kind >= _MIN_REFERENCE_SAMPLES_PER_KIND and workload_failures == 0
    )
    if samples_per_kind < _MIN_REFERENCE_SAMPLES_PER_KIND:
        limitations.append(
            "Each job kind requires at least "
            f"{_MIN_REFERENCE_SAMPLES_PER_KIND} measured workload samples."
        )
    if workload_failures:
        limitations.append(f"Canonical workload executions failed {workload_failures} time(s).")

    complete = queue_complete and workloads_complete
    if complete:
        limitations.append(
            "Runtime uses canonical in-memory repositories; PostgreSQL queue persistence "
            "is measured independently in the attached queue evidence."
        )
    return CapacityEvidence(
        scope=CapacityEvidenceScope.BACKGROUND_JOBS,
        method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
        complete=complete,
        observed_count=queue_observations + samples_per_kind * len(BackgroundJobKind),
        metrics=metrics,
        evidence_reference=(f"{BACKGROUND_JOB_WORKLOAD_FIXTURE_VERSION}+postgresql-queue-v1"),
        limitation=" ".join(limitations),
    )


def run_background_job_benchmark(
    *,
    queue_report: CapacityBenchmarkReport,
    samples_per_kind: int,
    warmup_iterations: int,
    commit_sha: str,
    workloads: Mapping[BackgroundJobKind, BackgroundJobWorkload] | None = None,
) -> CapacityBenchmarkReport:
    validate_queue_report_identity(queue_report, commit_sha=commit_sha)
    evidence = build_background_job_evidence(
        queue_evidence=_background_evidence(queue_report),
        workloads=workloads or build_background_job_workloads(),
        samples_per_kind=samples_per_kind,
        warmup_iterations=warmup_iterations,
    )
    return CapacityBenchmarkReport(
        environment_label=queue_report.environment_label,
        commit_sha=queue_report.commit_sha,
        generated_at=datetime.now(UTC),
        python_version=queue_report.python_version,
        platform=queue_report.platform,
        evidence=(evidence,),
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")
    try:
        queue_report = parse_capacity_benchmark_report(args.queue_report.read_bytes())
        report = run_background_job_benchmark(
            queue_report=queue_report,
            samples_per_kind=args.samples_per_kind,
            warmup_iterations=args.warmup_iterations,
            commit_sha=_commit_sha(),
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_capacity_benchmark_report(report) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote sanitized background-job capacity report to {args.output}")
    return 0 if report.evidence[0].complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
