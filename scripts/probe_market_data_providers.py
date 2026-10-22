#!/usr/bin/env python3
import argparse
from pathlib import Path

from trd_bot.market_data.provider_probes import (
    MarketDataProbeOutcome,
    available_market_data_probe_provider_ids,
    probe_market_data_providers,
    serialize_market_data_probe_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Probe fixed, public, read-only OHLCV endpoints without sending credentials "
            "or retaining response bodies."
        )
    )
    parser.add_argument(
        "--provider",
        action="append",
        choices=available_market_data_probe_provider_ids(),
        dest="providers",
        help="Provider to probe; repeat the option to select multiple providers (default: all).",
    )
    parser.add_argument(
        "--environment-label",
        default="iran-direct",
        help="Non-sensitive label written to the report (default: iran-direct).",
    )
    parser.add_argument(
        "--timeout-seconds",
        default=10.0,
        type=float,
        help="Per-stage timeout between 1 and 30 seconds (default: 10).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Write a new JSON report to this path; existing files are never overwritten.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    selected_provider_ids = args.providers or available_market_data_probe_provider_ids()
    provider_ids = tuple(dict.fromkeys(selected_provider_ids))
    environment_label = args.environment_label.strip()
    if not 1 <= len(environment_label) <= 64:
        parser.error("--environment-label must contain between 1 and 64 characters")
    if not 1.0 <= args.timeout_seconds <= 30.0:
        parser.error("--timeout-seconds must be between 1 and 30")
    if args.output is not None and args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    report = probe_market_data_providers(
        provider_ids,
        environment_label=environment_label,
        timeout_seconds=args.timeout_seconds,
    )
    serialized = serialize_market_data_probe_report(report) + "\n"
    if args.output is None:
        print(serialized, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        try:
            with args.output.open("x", encoding="utf-8") as output_file:
                output_file.write(serialized)
        except FileExistsError:
            parser.error(f"output file already exists: {args.output}")
        print(f"Wrote sanitized probe report to {args.output}")

    return (
        0
        if all(result.outcome is MarketDataProbeOutcome.SUCCESS for result in report.results)
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
