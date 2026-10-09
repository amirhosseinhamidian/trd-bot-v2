#!/usr/bin/env python3
import argparse
from datetime import UTC, datetime
from pathlib import Path

from trd_bot.market_data import (
    merge_capacity_benchmark_reports,
    parse_capacity_benchmark_report,
    serialize_capacity_benchmark_report,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Merge independent P0-04 capacity scope reports and evaluate the freeze gate."
        )
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")
    missing_inputs = [path for path in args.inputs if not path.is_file()]
    if missing_inputs:
        parser.error("every input report must be an existing file")

    try:
        reports = tuple(
            parse_capacity_benchmark_report(path.read_bytes()) for path in args.inputs
        )
        merged = merge_capacity_benchmark_reports(
            reports,
            generated_at=datetime.now(UTC),
        )
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_capacity_benchmark_report(merged) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote merged capacity report to {args.output}")
    return 0 if merged.ready_to_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
