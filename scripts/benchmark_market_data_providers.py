#!/usr/bin/env python3
import argparse
import math
import platform
import subprocess
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from trd_bot.market_data import (
    CapacityBenchmarkReport,
    CapacityEvidence,
    CapacityEvidenceMethod,
    CapacityEvidenceScope,
    MarketDataProbeOutcome,
    MarketDataProbeResult,
    available_market_data_probe_provider_ids,
    default_market_data_service_level_policy,
    probe_market_data_provider,
    serialize_capacity_benchmark_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Collect repeated sanitized public-provider probes for the P0-04 capacity gate."
        )
    )
    parser.add_argument(
        "--provider",
        action="append",
        required=True,
        choices=available_market_data_probe_provider_ids(),
        dest="providers",
    )
    parser.add_argument("--samples-per-provider", type=int, default=30)
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
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


def _percentile(values: Sequence[int], fraction: float) -> Decimal:
    if not values:
        return Decimal(0)
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered) * fraction) - 1)
    return Decimal(ordered[index])


def _fraction(count: int, total: int) -> Decimal:
    if total == 0:
        return Decimal(0)
    return Decimal(count) / Decimal(total)


def build_provider_evidence(
    results: Sequence[MarketDataProbeResult],
    *,
    selected_provider_ids: Sequence[str],
    minimum_samples_per_provider: int,
) -> CapacityEvidence:
    if not selected_provider_ids:
        raise ValueError("provider benchmark requires at least one provider")
    if minimum_samples_per_provider < 1:
        raise ValueError("minimum provider samples must be positive")
    selected = tuple(dict.fromkeys(selected_provider_ids))
    unexpected = sorted({item.provider_id for item in results} - set(selected))
    if unexpected:
        raise ValueError("provider results contain an unselected provider")
    metrics: dict[str, Decimal] = {}
    incomplete: list[str] = []

    for provider_id in selected:
        provider_results = [item for item in results if item.provider_id == provider_id]
        sample_count = len(provider_results)
        if sample_count < minimum_samples_per_provider:
            incomplete.append(provider_id)

        successful = [
            item for item in provider_results if item.outcome is MarketDataProbeOutcome.SUCCESS
        ]
        http_latencies = [
            item.http_latency_ms
            for item in successful
            if item.http_latency_ms is not None
        ]
        dns_latencies = [
            item.dns_latency_ms
            for item in provider_results
            if item.dns_latency_ms is not None
        ]
        tls_latencies = [
            item.tls_latency_ms
            for item in provider_results
            if item.tls_latency_ms is not None
        ]
        prefix = f"{provider_id}."
        metrics[f"{prefix}samples"] = Decimal(sample_count)
        metrics[f"{prefix}success_fraction"] = _fraction(len(successful), sample_count)
        metrics[f"{prefix}failure_fraction"] = _fraction(
            sample_count - len(successful),
            sample_count,
        )
        metrics[f"{prefix}http_latency_p50_ms"] = _percentile(http_latencies, 0.50)
        metrics[f"{prefix}http_latency_p95_ms"] = _percentile(http_latencies, 0.95)
        metrics[f"{prefix}dns_latency_p95_ms"] = _percentile(dns_latencies, 0.95)
        metrics[f"{prefix}tls_latency_p95_ms"] = _percentile(tls_latencies, 0.95)
        for outcome in (
            MarketDataProbeOutcome.GEO_BLOCKED,
            MarketDataProbeOutcome.RATE_LIMITED,
            MarketDataProbeOutcome.TIMEOUT,
            MarketDataProbeOutcome.INVALID_RESPONSE,
        ):
            count = sum(item.outcome is outcome for item in provider_results)
            metrics[f"{prefix}{outcome.value}_fraction"] = _fraction(count, sample_count)

    limitation = None
    if incomplete:
        limitation = (
            "Insufficient samples for provider(s): " + ", ".join(sorted(incomplete))
        )
    return CapacityEvidence(
        scope=CapacityEvidenceScope.PROVIDER,
        method=CapacityEvidenceMethod.LIVE_PROBE,
        complete=not incomplete,
        observed_count=len(results),
        metrics=metrics,
        limitation=limitation,
    )


def run_provider_benchmark(
    provider_ids: Sequence[str],
    *,
    samples_per_provider: int,
    interval_seconds: float,
    timeout_seconds: float,
) -> tuple[MarketDataProbeResult, ...]:
    if not 1 <= samples_per_provider <= 1_000:
        raise ValueError("samples per provider must be between 1 and 1,000")
    if not 0 <= interval_seconds <= 3_600:
        raise ValueError("probe interval must be between 0 and 3,600 seconds")
    if samples_per_provider > 1 and interval_seconds < 1:
        raise ValueError("reference probe intervals must be at least one second")
    if not 1 <= timeout_seconds <= 30:
        raise ValueError("probe timeout must be between 1 and 30 seconds")

    selected = tuple(dict.fromkeys(provider_ids))
    results: list[MarketDataProbeResult] = []
    for sample_index in range(samples_per_provider):
        for provider_id in selected:
            results.append(
                probe_market_data_provider(
                    provider_id,
                    timeout_seconds=timeout_seconds,
                    observed_at=datetime.now(UTC),
                )
            )
        if sample_index + 1 < samples_per_provider:
            time.sleep(interval_seconds)
    return tuple(results)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    environment_label = args.environment_label.strip()
    if not 1 <= len(environment_label) <= 64:
        parser.error("--environment-label must contain between 1 and 64 characters")
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    try:
        results = run_provider_benchmark(
            args.providers,
            samples_per_provider=args.samples_per_provider,
            interval_seconds=args.interval_seconds,
            timeout_seconds=args.timeout_seconds,
        )
        minimum_samples = max(
            (
                budget.minimum_probe_samples
                for budget in default_market_data_service_level_policy().providers
                if budget.provider_id in args.providers
            ),
            default=30,
        )
        evidence = build_provider_evidence(
            results,
            selected_provider_ids=args.providers,
            minimum_samples_per_provider=minimum_samples,
        )
        report = CapacityBenchmarkReport(
            environment_label=environment_label,
            commit_sha=_commit_sha(args.commit_sha),
            generated_at=datetime.now(UTC),
            python_version=platform.python_version(),
            platform=platform.platform(),
            evidence=(evidence,),
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_capacity_benchmark_report(report) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote sanitized provider capacity report to {args.output}")
    return 0 if evidence.complete else 2


if __name__ == "__main__":
    raise SystemExit(main())
