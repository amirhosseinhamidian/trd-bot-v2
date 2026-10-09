#!/usr/bin/env python3
import argparse
import json
import math
import platform
import subprocess
import time
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean

from trd_bot.domain.market_data import OHLCVCandle, Timeframe, TradingPair
from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    MarketDataEvent,
    MarketDataWatermark,
    MarketDataWindowSnapshot,
    decide_market_data_event,
    default_market_data_service_level_policy,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Benchmark the local market-event contract and emit a sanitized P0-04 "
            "capacity evidence report. Provider, PostgreSQL, and worker evidence remain "
            "explicitly unavailable until their dedicated reference runs are attached."
        )
    )
    parser.add_argument("--iterations", type=int, default=5_000)
    parser.add_argument("--warmup-iterations", type=int, default=250)
    parser.add_argument("--pair-count", type=int, default=1)
    parser.add_argument("--environment-label", default="local-development")
    parser.add_argument("--commit-sha", default=None)
    parser.add_argument("--output", type=Path)
    return parser


def _percentile(values: list[float], fraction: float) -> float:
    if not values:
        raise ValueError("percentile requires at least one observation")
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def _milliseconds(value: float) -> Decimal:
    return Decimal(str(round(value * 1_000, 6)))


def _decimal(value: float) -> Decimal:
    return Decimal(str(round(value, 6)))


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


def _create_candle(index: int) -> OHLCVCandle:
    start = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=index)
    return OHLCVCandle(
        source="capacity-benchmark",
        pair=TradingPair(base_asset="BTC", quote_asset="USDT"),
        timeframe=Timeframe.HOUR_1,
        open_time=start,
        close_time=start + timedelta(hours=1),
        received_at=start + timedelta(hours=1, seconds=30),
        open_price=Decimal("100"),
        high_price=Decimal("110"),
        low_price=Decimal("95"),
        close_price=Decimal("105"),
        volume=Decimal("1250.5"),
        is_closed=True,
    )


def _exercise_contract(index: int) -> tuple[float, int]:
    started_at = time.perf_counter()
    event = MarketDataEvent.from_candle(_create_candle(index))
    watermark = MarketDataWatermark.build(
        source=event.source,
        pair=event.pair,
        timeframe=event.timeframe,
        high_water_event_time=event.event_time,
        allowed_lateness_seconds=300,
        calculated_at=event.observed_at,
    )
    decision = decide_market_data_event(
        event,
        watermark=watermark,
        existing_window=None,
        decided_at=event.observed_at,
    )
    snapshot = MarketDataWindowSnapshot.from_event(
        event,
        version=decision.proposed_window_version or 1,
        created_at=event.observed_at,
    )
    duplicate = decide_market_data_event(
        event,
        watermark=watermark,
        existing_window=snapshot,
        decided_at=event.observed_at,
    )
    serialized = event.model_dump_json()
    if decision.proposed_window_version != 1 or duplicate.proposed_window_version is not None:
        raise RuntimeError("benchmark contract produced an inconsistent decision")
    return time.perf_counter() - started_at, len(serialized.encode("utf-8"))


def run_benchmark(
    *,
    iterations: int,
    warmup_iterations: int,
    pair_count: int,
    environment_label: str,
    commit_sha: str,
) -> CapacityBenchmarkReport:
    if not 100 <= iterations <= 1_000_000:
        raise ValueError("iterations must be between 100 and 1,000,000")
    if not 0 <= warmup_iterations <= iterations:
        raise ValueError("warmup iterations must be between zero and iterations")
    if not 1 <= pair_count <= 10_000:
        raise ValueError("pair count must be between 1 and 10,000")

    for index in range(warmup_iterations):
        _exercise_contract(index)

    latencies: list[float] = []
    payload_sizes: list[int] = []
    benchmark_started_at = time.perf_counter()
    for index in range(iterations):
        latency, payload_size = _exercise_contract(index + warmup_iterations)
        latencies.append(latency)
        payload_sizes.append(payload_size)
    elapsed_seconds = time.perf_counter() - benchmark_started_at

    throughput = iterations / elapsed_seconds
    average_payload_bytes = mean(payload_sizes)
    windows_per_pair_per_day = sum(
        86_400 // int(timeframe.duration.total_seconds()) for timeframe in Timeframe
    )
    projected_events_per_30_days = windows_per_pair_per_day * pair_count * 30
    projected_event_bytes = round(projected_events_per_30_days * average_payload_bytes)

    event_metrics = {
        "contract_latency_p50_ms": _milliseconds(_percentile(latencies, 0.50)),
        "contract_latency_p95_ms": _milliseconds(_percentile(latencies, 0.95)),
        "contract_latency_p99_ms": _milliseconds(_percentile(latencies, 0.99)),
        "contract_throughput_per_second": _decimal(throughput),
        "average_serialized_event_bytes": _decimal(average_payload_bytes),
    }
    storage_metrics = {
        "pair_count": Decimal(pair_count),
        "windows_per_pair_per_day": Decimal(windows_per_pair_per_day),
        "projected_events_per_30_days": Decimal(projected_events_per_30_days),
        "projected_normalized_event_bytes_per_30_days": Decimal(projected_event_bytes),
    }

    return CapacityBenchmarkReport(
        environment_label=environment_label.strip(),
        commit_sha=commit_sha,
        generated_at=datetime.now(UTC),
        python_version=platform.python_version(),
        platform=platform.platform(),
        evidence=(
            CapacityEvidence(
                scope=CapacityEvidenceScope.PROVIDER,
                method=CapacityEvidenceMethod.UNAVAILABLE,
                complete=False,
                observed_count=0,
                limitation=(
                    "Run repeated public provider probes from the deployment network; "
                    "this local benchmark performs no external requests."
                ),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.EVENT_PROCESSING,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=True,
                observed_count=iterations,
                metrics=event_metrics,
                limitation=(
                    "Measures deterministic event validation and decision policy only; "
                    "it excludes network and persistence latency."
                ),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.DATABASE,
                method=CapacityEvidenceMethod.UNAVAILABLE,
                complete=False,
                observed_count=0,
                limitation=(
                    "Run the PostgreSQL benchmark against the reference database; "
                    "no substitute SQLite number is accepted."
                ),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.BACKGROUND_JOBS,
                method=CapacityEvidenceMethod.UNAVAILABLE,
                complete=False,
                observed_count=0,
                limitation=(
                    "Measure queue wait and runtime with the standalone worker and "
                    "reference PostgreSQL queue."
                ),
            ),
            CapacityEvidence(
                scope=CapacityEvidenceScope.STORAGE,
                method=CapacityEvidenceMethod.SYNTHETIC_BENCHMARK,
                complete=False,
                observed_count=iterations,
                metrics=storage_metrics,
                limitation=(
                    "Projection covers serialized normalized events only; PostgreSQL index, "
                    "row, WAL, raw response, and revision overhead require DB evidence."
                ),
            ),
        ),
    )


def _serialize_report(report: CapacityBenchmarkReport) -> str:
    payload = report.model_dump(mode="json")
    payload["ready_to_freeze"] = report.ready_to_freeze
    payload["missing_scopes"] = [scope.value for scope in report.missing_scopes]
    payload["policy_schema_version"] = (
        default_market_data_service_level_policy().schema_version
    )
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    environment_label = args.environment_label.strip()
    if not 1 <= len(environment_label) <= 64:
        parser.error("--environment-label must contain between 1 and 64 characters")
    if args.output is not None and args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    try:
        report = run_benchmark(
            iterations=args.iterations,
            warmup_iterations=args.warmup_iterations,
            pair_count=args.pair_count,
            environment_label=environment_label,
            commit_sha=_commit_sha(args.commit_sha),
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))
    serialized = _serialize_report(report)

    if args.output is None:
        print(serialized, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as output_file:
                output_file.write(serialized)
        except FileExistsError:
            parser.error(f"output file already exists: {args.output}")
        print(f"Wrote sanitized capacity report to {args.output}")

    return 0 if report.ready_to_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
