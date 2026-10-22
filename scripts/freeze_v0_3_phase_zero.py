#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

from trd_bot.market_data import parse_capacity_benchmark_report
from trd_bot.phase_zero_acceptance import (
    evaluate_phase_zero_acceptance,
    serialize_phase_zero_freeze_record,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the fail-closed P0-05 acceptance matrix against a complete "
            "reference-capacity report and an explicit provider order."
        )
    )
    parser.add_argument("--capacity-report", type=Path, required=True)
    parser.add_argument("--primary-provider", required=True)
    parser.add_argument(
        "--fallback-provider",
        action="append",
        dest="fallback_providers",
        required=True,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _commit_sha() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        cwd=_REPOSITORY_ROOT,
        text=True,
    )
    return result.stdout.strip().lower()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not args.capacity_report.is_file():
        parser.error("--capacity-report must be an existing file")
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")

    try:
        capacity_report = parse_capacity_benchmark_report(args.capacity_report.read_bytes())
        commit_sha = _commit_sha()
        if capacity_report.commit_sha != commit_sha:
            raise ValueError("capacity report commit does not match the checked-out commit")
        record = evaluate_phase_zero_acceptance(
            capacity_report=capacity_report,
            primary_provider=args.primary_provider.strip(),
            fallback_providers=tuple(provider.strip() for provider in args.fallback_providers),
            repository_root=_REPOSITORY_ROOT,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_phase_zero_freeze_record(record) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote Phase 0 freeze record to {args.output}")
    return 0 if record.ready_to_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
