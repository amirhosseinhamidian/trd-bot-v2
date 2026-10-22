#!/usr/bin/env python3
import argparse
import subprocess
from pathlib import Path

from trd_bot.decision_intelligence import (
    DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES,
    run_decision_pipeline_benchmark,
    serialize_decision_pipeline_benchmark_report,
)

_ROOT = Path(__file__).resolve().parents[1]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the deterministic P5 decision benchmark.")
    parser.add_argument("--samples", type=int, default=1_000)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--environment-label", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.samples < DECISION_PIPELINE_BENCHMARK_MINIMUM_SAMPLES:
        raise ValueError("decision benchmark requires at least 100 samples")
    head = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=_ROOT, check=True, capture_output=True, text=True
    ).stdout.strip()
    if args.commit_sha != head:
        raise ValueError("benchmark commit SHA does not match the checked-out commit")
    if subprocess.run(
        ("git", "status", "--porcelain=v1", "--untracked-files=all"),
        cwd=_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip():
        raise ValueError("decision benchmark requires a clean worktree")
    if args.output.exists():
        raise FileExistsError("decision benchmark output already exists")
    report = run_decision_pipeline_benchmark(
        samples=args.samples,
        commit_sha=args.commit_sha,
        environment_label=args.environment_label,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(serialize_decision_pipeline_benchmark_report(report) + "\n")
    print(f"Wrote decision benchmark report to {args.output}")
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
