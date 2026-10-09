#!/usr/bin/env python3
import argparse
import json
import math
import os
import platform
import re
import subprocess
import time
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError

from trd_bot.jobs import BackgroundJobKind
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    serialize_capacity_benchmark_report,
)

_MIN_REFERENCE_EVENTS = 100_000
_MIN_REFERENCE_QUERY_SAMPLES = 100


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Measure P0-04 PostgreSQL query, queue-lifecycle, row, index, and WAL evidence "
            "inside an isolated disposable schema."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("TRD_BOT_TEST_DATABASE_URL"),
        help=(
            "Dedicated PostgreSQL benchmark URL; defaults to TRD_BOT_TEST_DATABASE_URL. "
            "The database name must contain test or bench."
        ),
    )
    parser.add_argument("--event-count", type=int, default=_MIN_REFERENCE_EVENTS)
    parser.add_argument("--job-count", type=int, default=250)
    parser.add_argument("--query-samples", type=int, default=200)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _commit_sha(explicit_sha: str | None) -> str:
    if explicit_sha is not None:
        return explicit_sha.strip().lower()
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
    )
    return result.stdout.strip().lower()


def validate_benchmark_database_url(database_url: str | None) -> str:
    if database_url is None or not database_url.strip():
        raise ValueError("a dedicated PostgreSQL benchmark database URL is required")
    url = make_url(database_url.strip())
    if url.get_backend_name() != "postgresql":
        raise ValueError("capacity benchmark requires PostgreSQL")
    database_name = (url.database or "").lower()
    if re.search(r"(?:test|bench)", database_name) is None:
        raise ValueError("benchmark database name must contain test or bench")
    return database_url.strip()


def _percentile(values: Sequence[float], fraction: float) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return Decimal(str(round(ordered[index], 6)))


def _milliseconds_since(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1_000


def _pool_utilization(engine: Engine) -> Decimal:
    pool = engine.pool
    size = getattr(pool, "size", lambda: 0)()
    checked_out = getattr(pool, "checkedout", lambda: 0)()
    if not isinstance(size, int) or size <= 0 or not isinstance(checked_out, int):
        return Decimal(0)
    return Decimal(checked_out) / Decimal(size)


def _qualified(schema: str, table: str) -> str:
    if re.fullmatch(r"p0_04_bench_[a-f0-9]{12}", schema) is None:
        raise ValueError("invalid benchmark schema name")
    if table not in {"market_events", "background_jobs"}:
        raise ValueError("invalid benchmark table name")
    return f'"{schema}"."{table}"'


def _create_schema(engine: Engine, schema: str) -> None:
    events = _qualified(schema, "market_events")
    jobs = _qualified(schema, "background_jobs")
    with engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(
            text(
                f"""
                CREATE TABLE {events} (
                    event_id text PRIMARY KEY,
                    idempotency_key text NOT NULL UNIQUE,
                    window_id text NOT NULL,
                    event_time timestamptz NOT NULL,
                    observed_at timestamptz NOT NULL,
                    payload jsonb NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT clock_timestamp()
                )
                """
            )
        )
        connection.execute(
            text(f"CREATE INDEX market_events_window_idx ON {events} (window_id, event_time)")
        )
        connection.execute(
            text(f"CREATE INDEX market_events_time_idx ON {events} (event_time)")
        )
        connection.execute(
            text(
                f"""
                CREATE TABLE {jobs} (
                    job_id text PRIMARY KEY,
                    kind text NOT NULL,
                    status text NOT NULL,
                    run_after timestamptz NOT NULL,
                    payload jsonb NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
                    started_at timestamptz,
                    finished_at timestamptz
                )
                """
            )
        )
        connection.execute(
            text(
                f"CREATE INDEX background_jobs_claim_idx "
                f"ON {jobs} (status, run_after, created_at)"
            )
        )


def _drop_schema(engine: Engine, schema: str) -> None:
    _qualified(schema, "market_events")
    with engine.begin() as connection:
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


def _wal_lsn(engine: Engine) -> str:
    with engine.connect() as connection:
        return str(connection.scalar(text("SELECT pg_current_wal_lsn()")))


def _wal_bytes(engine: Engine, start_lsn: str, end_lsn: str) -> int:
    with engine.connect() as connection:
        value = connection.scalar(
            text("SELECT pg_wal_lsn_diff(CAST(:end AS pg_lsn), CAST(:start AS pg_lsn))"),
            {"start": start_lsn, "end": end_lsn},
        )
    return int(value or 0)


def _event_payload() -> str:
    return json.dumps(
        {
            "schema_version": "market-data-event-v1",
            "source": "capacity-benchmark",
            "pair": {"base_asset": "BTC", "quote_asset": "USDT"},
            "timeframe": "1h",
            "open": "100",
            "high": "110",
            "low": "95",
            "close": "105",
            "volume": "1250.5",
            "padding": "x" * 512,
        },
        separators=(",", ":"),
        sort_keys=True,
    )


def _insert_events(
    engine: Engine,
    schema: str,
    event_count: int,
) -> tuple[list[float], list[Decimal]]:
    table = _qualified(schema, "market_events")
    statement = text(
        f"""
        INSERT INTO {table} (
            event_id, idempotency_key, window_id, event_time, observed_at, payload
        ) VALUES (
            :event_id, :idempotency_key, :window_id, :event_time, :observed_at,
            CAST(:payload AS jsonb)
        )
        """
    )
    payload = _event_payload()
    base_time = datetime(2020, 1, 1, tzinfo=UTC)
    batch_latencies: list[float] = []
    pool_samples: list[Decimal] = []
    batch_size = 1_000
    for batch_start in range(0, event_count, batch_size):
        batch_end = min(batch_start + batch_size, event_count)
        parameters = []
        for index in range(batch_start, batch_end):
            event_time = base_time + timedelta(hours=index)
            parameters.append(
                {
                    "event_id": f"market-event-{index:016x}",
                    "idempotency_key": f"market-data-event:{index:064x}",
                    "window_id": f"market-window-{index:016x}",
                    "event_time": event_time,
                    "observed_at": event_time + timedelta(seconds=30),
                    "payload": payload,
                }
            )
        started_at = time.perf_counter()
        with engine.begin() as connection:
            pool_samples.append(_pool_utilization(engine))
            connection.execute(statement, parameters)
        batch_latencies.append(_milliseconds_since(started_at))
    return batch_latencies, pool_samples


def _measure_queries(
    engine: Engine,
    schema: str,
    event_count: int,
    query_samples: int,
) -> tuple[dict[str, Decimal], list[Decimal]]:
    table = _qualified(schema, "market_events")
    base_time = datetime(2020, 1, 1, tzinfo=UTC)
    lookup_latencies: list[float] = []
    window_latencies: list[float] = []
    range_latencies: list[float] = []
    pool_samples: list[Decimal] = []

    with engine.connect() as connection:
        for sample in range(query_samples):
            index = (sample * 997) % event_count
            pool_samples.append(_pool_utilization(engine))

            started_at = time.perf_counter()
            connection.execute(
                text(f"SELECT event_id FROM {table} WHERE idempotency_key = :key"),
                {"key": f"market-data-event:{index:064x}"},
            ).one()
            lookup_latencies.append(_milliseconds_since(started_at))

            started_at = time.perf_counter()
            connection.execute(
                text(
                    f"SELECT event_id, payload FROM {table} "
                    "WHERE window_id = :window ORDER BY event_time DESC LIMIT 1"
                ),
                {"window": f"market-window-{index:016x}"},
            ).one()
            window_latencies.append(_milliseconds_since(started_at))

            range_start = base_time + timedelta(hours=max(0, index - 24))
            started_at = time.perf_counter()
            connection.execute(
                text(
                    f"SELECT event_id, event_time FROM {table} "
                    "WHERE event_time >= :start AND event_time < :end ORDER BY event_time"
                ),
                {"start": range_start, "end": range_start + timedelta(hours=24)},
            ).all()
            range_latencies.append(_milliseconds_since(started_at))

    return (
        {
            "inbox_lookup_latency_p50_ms": _percentile(lookup_latencies, 0.50),
            "inbox_lookup_latency_p95_ms": _percentile(lookup_latencies, 0.95),
            "current_window_latency_p50_ms": _percentile(window_latencies, 0.50),
            "current_window_latency_p95_ms": _percentile(window_latencies, 0.95),
            "time_range_latency_p50_ms": _percentile(range_latencies, 0.50),
            "time_range_latency_p95_ms": _percentile(range_latencies, 0.95),
        },
        pool_samples,
    )


def _measure_queue(
    engine: Engine,
    schema: str,
    job_count: int,
) -> tuple[dict[str, Decimal], list[Decimal]]:
    table = _qualified(schema, "background_jobs")
    kinds = tuple(BackgroundJobKind)
    enqueue_latencies: list[float] = []
    claim_latencies: list[float] = []
    finish_latencies: list[float] = []
    queue_wait_milliseconds: list[float] = []
    lifecycle_by_kind: dict[BackgroundJobKind, list[float]] = {kind: [] for kind in kinds}
    pool_samples: list[Decimal] = []
    benchmark_started_at = time.perf_counter()

    for index in range(job_count):
        kind = kinds[index % len(kinds)]
        started_at = time.perf_counter()
        with engine.begin() as connection:
            pool_samples.append(_pool_utilization(engine))
            connection.execute(
                text(
                    f"INSERT INTO {table} "
                    "(job_id, kind, status, run_after, payload) "
                    "VALUES (:job_id, :kind, 'queued', clock_timestamp(), "
                    "CAST(:payload AS jsonb))"
                ),
                {
                    "job_id": f"benchmark-job-{index:016x}",
                    "kind": kind.value,
                    "payload": json.dumps({"fixture": "bounded-noop-v1"}),
                },
            )
        enqueue_latencies.append(_milliseconds_since(started_at))

    claim_statement = text(
        f"""
        WITH candidate AS (
            SELECT job_id
            FROM {table}
            WHERE status = 'queued' AND run_after <= clock_timestamp()
            ORDER BY run_after, created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        UPDATE {table} AS jobs
        SET status = 'running', started_at = clock_timestamp()
        FROM candidate
        WHERE jobs.job_id = candidate.job_id
        RETURNING jobs.job_id, jobs.kind,
            EXTRACT(EPOCH FROM (jobs.started_at - jobs.created_at)) * 1000 AS wait_ms
        """
    )
    finish_statement = text(
        f"UPDATE {table} SET status = 'succeeded', finished_at = clock_timestamp() "
        "WHERE job_id = :job_id"
    )
    for _ in range(job_count):
        lifecycle_started_at = time.perf_counter()
        started_at = time.perf_counter()
        with engine.begin() as connection:
            pool_samples.append(_pool_utilization(engine))
            row = connection.execute(claim_statement).one()
        claim_latencies.append(_milliseconds_since(started_at))
        queue_wait_milliseconds.append(float(row.wait_ms))

        started_at = time.perf_counter()
        with engine.begin() as connection:
            connection.execute(finish_statement, {"job_id": row.job_id})
        finish_latencies.append(_milliseconds_since(started_at))
        kind = BackgroundJobKind(str(row.kind))
        lifecycle_by_kind[kind].append(_milliseconds_since(lifecycle_started_at))

    elapsed_seconds = time.perf_counter() - benchmark_started_at
    metrics = {
        "enqueue_latency_p95_ms": _percentile(enqueue_latencies, 0.95),
        "claim_latency_p95_ms": _percentile(claim_latencies, 0.95),
        "terminal_write_latency_p95_ms": _percentile(finish_latencies, 0.95),
        "queue_wait_p50_ms": _percentile(queue_wait_milliseconds, 0.50),
        "queue_wait_p95_ms": _percentile(queue_wait_milliseconds, 0.95),
        "synthetic_job_throughput_per_second": Decimal(
            str(round(job_count / elapsed_seconds, 6))
        ),
    }
    for kind, values in lifecycle_by_kind.items():
        metrics[f"{kind.value}.bounded_noop_lifecycle_p95_ms"] = _percentile(values, 0.95)
    return metrics, pool_samples


def _storage_metrics(engine: Engine, schema: str, wal_bytes: int) -> dict[str, Decimal]:
    events = _qualified(schema, "market_events")
    jobs = _qualified(schema, "background_jobs")
    query = text(
        """
        SELECT
            pg_relation_size(CAST(:relation AS regclass)) AS table_bytes,
            pg_indexes_size(CAST(:relation AS regclass)) AS index_bytes,
            pg_total_relation_size(CAST(:relation AS regclass)) AS total_bytes,
            CASE
                WHEN reltoastrelid = 0 THEN 0
                ELSE pg_total_relation_size(reltoastrelid)
            END AS toast_bytes
        FROM pg_class
        WHERE oid = CAST(:relation AS regclass)
        """
    )
    metrics: dict[str, Decimal] = {"wal_bytes_approximate": Decimal(wal_bytes)}
    with engine.connect() as connection:
        for label, relation in (("events", events), ("jobs", jobs)):
            row = connection.execute(query, {"relation": relation}).one()
            metrics[f"{label}_table_bytes"] = Decimal(int(row.table_bytes))
            metrics[f"{label}_index_bytes"] = Decimal(int(row.index_bytes))
            metrics[f"{label}_total_bytes"] = Decimal(int(row.total_bytes))
            metrics[f"{label}_toast_bytes"] = Decimal(int(row.toast_bytes))
    return metrics


def run_postgresql_benchmark(
    *,
    database_url: str,
    event_count: int,
    job_count: int,
    query_samples: int,
    environment_label: str,
    commit_sha: str,
) -> CapacityBenchmarkReport:
    if not 1_000 <= event_count <= 1_000_000:
        raise ValueError("event count must be between 1,000 and 1,000,000")
    if not 10 <= job_count <= 10_000:
        raise ValueError("job count must be between 10 and 10,000")
    if not 10 <= query_samples <= 10_000:
        raise ValueError("query samples must be between 10 and 10,000")

    engine = create_engine(
        validate_benchmark_database_url(database_url),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=0,
        pool_timeout=5,
    )
    schema = f"p0_04_bench_{uuid4().hex[:12]}"
    created = False
    try:
        _create_schema(engine, schema)
        created = True
        start_lsn = _wal_lsn(engine)
        insert_latencies, insert_pool = _insert_events(engine, schema, event_count)
        query_metrics, query_pool = _measure_queries(
            engine,
            schema,
            event_count,
            query_samples,
        )
        queue_metrics, queue_pool = _measure_queue(engine, schema, job_count)
        end_lsn = _wal_lsn(engine)
        wal_bytes = _wal_bytes(engine, start_lsn, end_lsn)
        storage_metrics = _storage_metrics(engine, schema, wal_bytes)
        pool_samples = insert_pool + query_pool + queue_pool
        database_complete = (
            event_count >= _MIN_REFERENCE_EVENTS
            and query_samples >= _MIN_REFERENCE_QUERY_SAMPLES
        )
        database_metrics = {
            **query_metrics,
            "event_insert_batch_p95_ms": _percentile(insert_latencies, 0.95),
            "pool_utilization_p95_fraction": _percentile(
                [float(value) for value in pool_samples],
                0.95,
            ),
            "event_count": Decimal(event_count),
            "query_samples": Decimal(query_samples),
        }
        database_limitation = None
        if not database_complete:
            database_limitation = (
                "Reference completeness requires at least 100,000 events and 100 query samples."
            )
        evidence = (
            CapacityEvidence(
                scope=CapacityEvidenceScope.DATABASE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=database_complete,
                observed_count=query_samples,
                metrics=database_metrics,
                limitation=database_limitation,
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.BACKGROUND_JOBS,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=False,
                observed_count=job_count,
                metrics=queue_metrics,
                limitation=(
                    "Queue lifecycle uses bounded no-op payloads. Complete evidence still "
                    "requires versioned real fixtures for every job kind."
                ),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.STORAGE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=event_count >= _MIN_REFERENCE_EVENTS,
                observed_count=event_count,
                metrics=storage_metrics,
                limitation=(
                    "WAL delta can include concurrent activity on the same PostgreSQL cluster."
                    if event_count >= _MIN_REFERENCE_EVENTS
                    else (
                        "Reference storage evidence requires at least 100,000 events; "
                        "WAL delta can include concurrent cluster activity."
                    )
                ),
            ),
        )
        return CapacityBenchmarkReport(
            environment_label=environment_label,
            commit_sha=commit_sha,
            generated_at=datetime.now(UTC),
            python_version=platform.python_version(),
            platform=platform.platform(),
            evidence=evidence,
        )
    finally:
        if created:
            _drop_schema(engine, schema)
        engine.dispose()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    environment_label = args.environment_label.strip()
    if not 1 <= len(environment_label) <= 64:
        parser.error("--environment-label must contain between 1 and 64 characters")
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    try:
        report = run_postgresql_benchmark(
            database_url=validate_benchmark_database_url(args.database_url),
            event_count=args.event_count,
            job_count=args.job_count,
            query_samples=args.query_samples,
            environment_label=environment_label,
            commit_sha=_commit_sha(args.commit_sha),
        )
    except SQLAlchemyError:
        parser.error("PostgreSQL benchmark failed; inspect the local database logs")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_capacity_benchmark_report(report) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote sanitized PostgreSQL capacity report to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
