#!/usr/bin/env python3
import argparse
import json
import math
import os
import platform
import re
import subprocess
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import delete, func, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

from trd_bot.db import (
    BackgroundJobConflictError,
    SqlAlchemyBackgroundJobRepository,
    create_database_engine,
    create_session_factory,
)
from trd_bot.db.models import BackgroundJobRow
from trd_bot.jobs import (
    BackgroundJob,
    BackgroundJobBuilder,
    BackgroundJobContext,
    BackgroundJobHandlerRegistry,
    BackgroundJobKind,
    BackgroundJobStatus,
    BackgroundJobWorker,
)
from trd_bot.release_capacity import (
    ReleaseCapacityBenchmarkReport,
    ReleaseCapacityObservations,
    ReleaseCapacityPolicy,
    build_release_capacity_report,
    classify_queue_pressure,
    default_release_capacity_policy,
    serialize_release_capacity_report,
)

_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    policy = default_release_capacity_policy()
    parser = argparse.ArgumentParser(
        description=(
            "Measure v0.3 PostgreSQL queue capacity, overload drain, contention, "
            "idempotency, retry, lease recovery, and stale-owner fencing."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("TRD_BOT_TEST_DATABASE_URL"),
        help=("Dedicated PostgreSQL test/benchmark URL; defaults to TRD_BOT_TEST_DATABASE_URL."),
    )
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--job-count", type=int, default=policy.queue_overload_depth)
    parser.add_argument(
        "--contention-workers",
        type=int,
        default=policy.minimum_contention_workers,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def validate_release_benchmark_database_url(database_url: str | None) -> str:
    if database_url is None or not database_url.strip():
        raise ValueError("a dedicated PostgreSQL release benchmark database URL is required")
    normalized = database_url.strip()
    url = make_url(normalized)
    if url.get_backend_name() != "postgresql":
        raise ValueError("release capacity benchmark requires PostgreSQL")
    if re.search(r"(?:test|bench)", (url.database or "").casefold()) is None:
        raise ValueError("release benchmark database name must contain test or bench")
    return normalized


def _commit_sha(explicit_sha: str | None) -> str:
    if explicit_sha is not None:
        return explicit_sha.strip().casefold()
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        cwd=_ROOT,
        text=True,
    )
    return result.stdout.strip().casefold()


def _percentile(values: Sequence[float], fraction: float) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return Decimal(str(round(ordered[index], 6)))


def _milliseconds_since(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1_000


def _assert_current_migration_head(engine: Engine) -> None:
    config = Config(str(_ROOT / "alembic.ini"))
    expected = tuple(sorted(ScriptDirectory.from_config(config).get_heads()))
    with engine.connect() as connection:
        current = tuple(sorted(MigrationContext.configure(connection).get_current_heads()))
    if current != expected:
        raise ValueError(
            "release benchmark database is not at the repository migration head: "
            f"current={current}, expected={expected}"
        )


def _active_job_count(factory: sessionmaker[Session]) -> int:
    with factory() as session:
        statement = (
            select(func.count())
            .select_from(BackgroundJobRow)
            .where(
                BackgroundJobRow.status.in_(
                    (BackgroundJobStatus.QUEUED.value, BackgroundJobStatus.RUNNING.value)
                )
            )
        )
        return int(session.scalar(statement) or 0)


def _benchmark_row_count(factory: sessionmaker[Session], prefix: str) -> int:
    with factory() as session:
        statement = (
            select(func.count())
            .select_from(BackgroundJobRow)
            .where(BackgroundJobRow.idempotency_key.like(f"{prefix}%"))
        )
        return int(session.scalar(statement) or 0)


def _cleanup(factory: sessionmaker[Session], prefix: str) -> bool:
    with factory() as session:
        session.execute(
            delete(BackgroundJobRow).where(BackgroundJobRow.idempotency_key.like(f"{prefix}%"))
        )
        session.commit()
    return _benchmark_row_count(factory, prefix) == 0


def _enqueue_overload_batch(
    factory: sessionmaker[Session],
    *,
    prefix: str,
    job_count: int,
) -> tuple[tuple[str, ...], tuple[str, ...], list[float]]:
    kinds = tuple(BackgroundJobKind)
    job_ids: list[str] = []
    covered_kinds: set[str] = set()
    latencies: list[float] = []
    for index in range(job_count):
        kind = kinds[index % len(kinds)]
        job = BackgroundJobBuilder().build(
            kind=kind,
            payload={"benchmark": "v0.3-release-capacity-v1", "ordinal": index},
            idempotency_key=f"{prefix}overload-{index:04d}",
        )
        started_at = time.perf_counter()
        with factory() as session:
            stored, created = SqlAlchemyBackgroundJobRepository(session).enqueue(job)
        latencies.append(_milliseconds_since(started_at))
        if not created or stored.job_id != job.job_id:
            raise ValueError("release overload fixture collided with an existing job")
        job_ids.append(job.job_id)
        covered_kinds.add(kind.value)
    return tuple(job_ids), tuple(sorted(covered_kinds)), latencies


def _drain_overload_batch(
    factory: sessionmaker[Session],
    *,
    job_ids: tuple[str, ...],
) -> tuple[list[float], list[float], float]:
    handlers = BackgroundJobHandlerRegistry()

    def complete_job(
        context: BackgroundJobContext,
        payload: Mapping[str, object],
    ) -> str:
        del payload
        return f"release-capacity:{context.job.kind.value}"

    for kind in BackgroundJobKind:
        handlers.register(kind, complete_job)

    cycle_latencies: list[float] = []
    queue_waits: list[float] = []
    started_at = time.perf_counter()
    with factory() as session:
        worker = BackgroundJobWorker(
            repository=SqlAlchemyBackgroundJobRepository(session),
            handlers=handlers,
            worker_id="release-capacity-single-worker",
        )
        completed_ids: set[str] = set()
        for _ in job_ids:
            cycle_started_at = time.perf_counter()
            completed = worker.run_once()
            cycle_latencies.append(_milliseconds_since(cycle_started_at))
            if completed is None or completed.status is not BackgroundJobStatus.SUCCEEDED:
                raise ValueError("release overload worker did not complete the queued fixture")
            if completed.started_at is None:
                raise ValueError("release overload job did not persist its start time")
            completed_ids.add(completed.job_id)
            queue_waits.append(
                (completed.started_at - completed.created_at).total_seconds() * 1_000
            )
        if worker.run_once() is not None:
            raise ValueError("release benchmark found an unexpected active job")
    elapsed_seconds = time.perf_counter() - started_at
    if completed_ids != set(job_ids):
        raise ValueError("release overload worker completed an unexpected job set")
    return cycle_latencies, queue_waits, elapsed_seconds


def _status_counts(
    factory: sessionmaker[Session],
    job_ids: tuple[str, ...],
) -> tuple[int, int, int]:
    with factory() as session:
        rows = session.execute(
            select(BackgroundJobRow.status, func.count())
            .where(BackgroundJobRow.job_id.in_(job_ids))
            .group_by(BackgroundJobRow.status)
        ).all()
    counts = {str(status): int(count) for status, count in rows}
    succeeded = counts.get(BackgroundJobStatus.SUCCEEDED.value, 0)
    failed = counts.get(BackgroundJobStatus.FAILED.value, 0)
    active = counts.get(BackgroundJobStatus.QUEUED.value, 0) + counts.get(
        BackgroundJobStatus.RUNNING.value, 0
    )
    return succeeded, failed, active


def _measure_claim_contention(
    factory: sessionmaker[Session],
    *,
    prefix: str,
    workers: int,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.EXPERIMENT_EXECUTION,
        payload={"benchmark": "claim-contention"},
        idempotency_key=f"{prefix}contention",
        now=now,
    )
    with factory() as session:
        SqlAlchemyBackgroundJobRepository(session).enqueue(job)

    barrier = Barrier(workers)

    def claim(index: int) -> BackgroundJob | None:
        with factory() as session:
            barrier.wait(timeout=30)
            return SqlAlchemyBackgroundJobRepository(session).claim_next(
                worker_id=f"release-contention-{index}",
                lease_duration=timedelta(seconds=30),
                now=now,
            )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = tuple(executor.map(claim, range(workers)))
    winners = tuple(result for result in results if result is not None)
    if winners:
        winner = winners[0]
        if winner.lease_owner is None:
            raise ValueError("release contention winner has no lease owner")
        with factory() as session:
            SqlAlchemyBackgroundJobRepository(session).succeed(
                job_id=winner.job_id,
                worker_id=winner.lease_owner,
                now=now + timedelta(seconds=1),
            )
    return len(winners), len({winner.job_id for winner in winners})


def _measure_recovery(
    factory: sessionmaker[Session],
    *,
    prefix: str,
) -> tuple[int, bool, bool, float]:
    now = datetime.now(UTC)
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.WALK_FORWARD_EXECUTION,
        payload={"benchmark": "lease-recovery"},
        idempotency_key=f"{prefix}recovery",
        now=now,
    )
    with factory() as session:
        stored, _ = SqlAlchemyBackgroundJobRepository(session).enqueue(job)
    with factory() as session:
        claimed = SqlAlchemyBackgroundJobRepository(session).claim_next(
            worker_id="release-stale-worker",
            lease_duration=timedelta(seconds=1),
            now=now,
        )
    if claimed is None:
        raise ValueError("release recovery fixture could not be claimed")
    transition_started_at = time.perf_counter()
    with factory() as session:
        reclaimed = SqlAlchemyBackgroundJobRepository(session).claim_next(
            worker_id="release-recovery-worker",
            lease_duration=timedelta(seconds=30),
            now=now + timedelta(seconds=2),
        )
    transition_ms = _milliseconds_since(transition_started_at)
    if reclaimed is None:
        raise ValueError("release recovery fixture was not reclaimed")
    stale_owner_fenced = False
    try:
        with factory() as session:
            SqlAlchemyBackgroundJobRepository(session).succeed(
                job_id=stored.job_id,
                worker_id="release-stale-worker",
                now=now + timedelta(seconds=3),
            )
    except BackgroundJobConflictError:
        stale_owner_fenced = True
    with factory() as session:
        SqlAlchemyBackgroundJobRepository(session).succeed(
            job_id=reclaimed.job_id,
            worker_id="release-recovery-worker",
            now=now + timedelta(seconds=3),
        )
    return (
        reclaimed.attempt_count,
        reclaimed.job_id == stored.job_id,
        stale_owner_fenced,
        transition_ms,
    )


def _measure_retry(
    factory: sessionmaker[Session],
    *,
    prefix: str,
) -> tuple[int, bool]:
    now = datetime.now(UTC)
    job = BackgroundJobBuilder().build(
        kind=BackgroundJobKind.DECISION_EVALUATION,
        payload={"benchmark": "retry"},
        idempotency_key=f"{prefix}retry",
        now=now,
    )
    with factory() as session:
        stored, _ = SqlAlchemyBackgroundJobRepository(session).enqueue(job)
    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        claimed = repository.claim_next(
            worker_id="release-retry-worker-1",
            lease_duration=timedelta(seconds=30),
            now=now,
        )
        if claimed is None:
            raise ValueError("release retry fixture could not be claimed")
        repository.fail(
            job_id=claimed.job_id,
            worker_id="release-retry-worker-1",
            error_code="release_benchmark_retry",
            error_message="synthetic retryable release benchmark failure",
            retryable=True,
            now=now + timedelta(seconds=1),
        )
    with factory() as session:
        repository = SqlAlchemyBackgroundJobRepository(session)
        retried = repository.claim_next(
            worker_id="release-retry-worker-2",
            lease_duration=timedelta(seconds=30),
            now=now + timedelta(seconds=2),
        )
        if retried is None:
            raise ValueError("release retry fixture was not claimed again")
        repository.succeed(
            job_id=retried.job_id,
            worker_id="release-retry-worker-2",
            now=now + timedelta(seconds=3),
        )
    return retried.attempt_count, retried.job_id == stored.job_id


def _measure_duplicate_enqueue(
    factory: sessionmaker[Session],
    *,
    prefix: str,
    attempts: int,
) -> tuple[int, int]:
    now = datetime.now(UTC)
    jobs = tuple(
        BackgroundJobBuilder().build(
            kind=BackgroundJobKind.ALERT_EVALUATION,
            payload={"benchmark": "idempotent-enqueue"},
            idempotency_key=f"{prefix}duplicate",
            now=now,
        )
        for _ in range(attempts)
    )
    barrier = Barrier(attempts)

    def enqueue(job: BackgroundJob) -> tuple[BackgroundJob, bool]:
        with factory() as session:
            barrier.wait(timeout=30)
            return SqlAlchemyBackgroundJobRepository(session).enqueue(job)

    with ThreadPoolExecutor(max_workers=attempts) as executor:
        results = tuple(executor.map(enqueue, jobs))
    return sum(created for _, created in results), len({stored.job_id for stored, _ in results})


def run_release_capacity_benchmark(
    *,
    database_url: str,
    environment_label: str,
    commit_sha: str,
    job_count: int,
    contention_workers: int,
    policy: ReleaseCapacityPolicy | None = None,
) -> ReleaseCapacityBenchmarkReport:
    active_policy = policy or default_release_capacity_policy()
    if not active_policy.queue_overload_depth <= job_count <= 1_000:
        raise ValueError(
            "release benchmark job count must be between the overload threshold and 1,000"
        )
    if not active_policy.minimum_contention_workers <= contention_workers <= 32:
        raise ValueError("release contention workers must be between the policy minimum and 32")

    engine = create_database_engine(validate_release_benchmark_database_url(database_url))
    factory = create_session_factory(engine)
    prefix = f"p6-02-{uuid4().hex[:16]}-"
    cleanup_verified = False
    try:
        _assert_current_migration_head(engine)
        if _active_job_count(factory) != 0:
            raise ValueError(
                "release benchmark requires a dedicated database with no active background jobs"
            )

        try:
            job_ids, covered_kinds, enqueue_latencies = _enqueue_overload_batch(
                factory,
                prefix=prefix,
                job_count=job_count,
            )
            overload_depth = _active_job_count(factory)
            overload_level = classify_queue_pressure(overload_depth, active_policy)
            cycle_latencies, queue_waits, drain_seconds = _drain_overload_batch(
                factory,
                job_ids=job_ids,
            )
            succeeded, failed, remaining = _status_counts(factory, job_ids)
            contention_winners, contention_unique = _measure_claim_contention(
                factory,
                prefix=prefix,
                workers=contention_workers,
            )
            recovery_attempts, recovery_same_job, stale_fenced, recovery_ms = _measure_recovery(
                factory,
                prefix=prefix,
            )
            retry_attempts, retry_same_job = _measure_retry(factory, prefix=prefix)
            duplicate_created, duplicate_unique = _measure_duplicate_enqueue(
                factory,
                prefix=prefix,
                attempts=contention_workers,
            )
        finally:
            cleanup_verified = _cleanup(factory, prefix)
    finally:
        engine.dispose()

    observations = ReleaseCapacityObservations(
        requested_jobs=job_count,
        covered_job_kinds=covered_kinds,
        overload_depth_observed=overload_depth,
        overload_level=overload_level,
        succeeded_jobs=succeeded,
        failed_jobs=failed,
        remaining_active_jobs=remaining,
        enqueue_latency_p95_milliseconds=_percentile(enqueue_latencies, 0.95),
        queue_wait_p95_milliseconds=_percentile(queue_waits, 0.95),
        worker_cycle_latency_p95_milliseconds=_percentile(cycle_latencies, 0.95),
        overload_drain_throughput_per_second=Decimal(str(round(job_count / drain_seconds, 6))),
        duplicate_enqueue_attempts=contention_workers,
        duplicate_created_count=duplicate_created,
        duplicate_unique_job_count=duplicate_unique,
        contention_workers=contention_workers,
        contention_claim_winner_count=contention_winners,
        contention_unique_job_count=contention_unique,
        recovery_attempt_count=recovery_attempts,
        recovery_reused_job=recovery_same_job,
        stale_owner_fenced=stale_fenced,
        retry_attempt_count=retry_attempts,
        retry_reused_job=retry_same_job,
        recovery_transition_milliseconds=Decimal(str(round(recovery_ms, 6))),
        cleanup_verified=cleanup_verified,
    )
    return build_release_capacity_report(
        environment_label=environment_label,
        commit_sha=commit_sha,
        generated_at=datetime.now(UTC),
        python_version=platform.python_version(),
        platform=platform.platform(),
        observations=observations,
        policy=active_policy,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")
    try:
        report = run_release_capacity_benchmark(
            database_url=args.database_url,
            environment_label=args.environment_label,
            commit_sha=_commit_sha(args.commit_sha),
            job_count=args.job_count,
            contention_workers=args.contention_workers,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_release_capacity_report(report) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(
        json.dumps(
            {
                "commit_sha": report.commit_sha,
                "failure_reasons": list(report.failure_reasons),
                "passed": report.passed,
                "policy_checksum": report.policy.definition_checksum,
                "report_checksum": report.report_checksum,
                "throughput_per_second": str(
                    report.observations.overload_drain_throughput_per_second
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
