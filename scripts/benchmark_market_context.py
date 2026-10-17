#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path

from trd_bot.market_context import (
    MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
    run_market_context_golden_benchmark,
    serialize_market_context_golden_benchmark_report,
)

_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the synthetic P3-09 golden market-context pipeline benchmark and "
            "write sanitized same-SHA acceptance evidence."
        )
    )
    parser.add_argument(
        "--samples-per-scenario",
        type=int,
        default=MARKET_CONTEXT_GOLDEN_MINIMUM_SAMPLES,
    )
    parser.add_argument("--warmup-iterations", type=int, default=2)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def _repository_commit_sha() -> str:
    status = subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        check=True,
        capture_output=True,
        cwd=_REPOSITORY_ROOT,
        text=True,
    )
    if status.stdout.strip():
        raise ValueError("market-context benchmark requires a clean worktree")
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"),
        check=True,
        capture_output=True,
        cwd=_REPOSITORY_ROOT,
        text=True,
    )
    return result.stdout.strip().lower()


def validate_commit_sha(value: str, *, repository_commit_sha: str) -> str:
    normalized = value.strip().lower()
    if not re.fullmatch(r"[a-f0-9]{40}", normalized):
        raise ValueError("commit SHA must contain exactly 40 lowercase hexadecimal characters")
    if normalized != repository_commit_sha:
        raise ValueError("benchmark commit SHA does not match the checked-out commit")
    return normalized


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output file already exists: {args.output}")
    try:
        commit_sha = validate_commit_sha(
            args.commit_sha,
            repository_commit_sha=_repository_commit_sha(),
        )
        report = run_market_context_golden_benchmark(
            commit_sha=commit_sha,
            environment_label=args.environment_label,
            samples_per_scenario=args.samples_per_scenario,
            warmup_iterations=args.warmup_iterations,
        )
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        parser.error(str(exc))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.output.open("x", encoding="utf-8") as output_file:
            output_file.write(serialize_market_context_golden_benchmark_report(report) + "\n")
    except FileExistsError:
        parser.error(f"output file already exists: {args.output}")
    print(f"Wrote sanitized market-context golden benchmark report to {args.output}")
    return 0 if report.ready_for_phase_three_acceptance else 2


if __name__ == "__main__":
    raise SystemExit(main())
