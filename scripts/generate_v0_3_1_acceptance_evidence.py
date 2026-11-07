#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from v0_3_1_stage_acceptance import (
    build_evidence,
    evidence_path_checksums,
    load_manifest,
    load_policy,
)


def parse_gate(value: str) -> tuple[str, str]:
    name, separator, conclusion = value.partition("=")
    if not separator or not name or not conclusion:
        raise argparse.ArgumentTypeError("gate must use NAME=CONCLUSION")
    return name, conclusion


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate same-SHA CI acceptance evidence.")
    parser.add_argument("--stage-id", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit-sha", required=True)
    parser.add_argument("--tree-sha", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--run-id", required=True, type=int)
    parser.add_argument("--run-attempt", required=True, type=int)
    parser.add_argument("--event", required=True)
    parser.add_argument("--gate", action="append", type=parse_gate, default=[])
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = load_policy()
    manifest = load_manifest(args.stage_id)
    gates = dict(args.gate)
    if len(gates) != len(args.gate):
        raise ValueError("duplicate gate result")
    evidence = build_evidence(
        policy,
        manifest,
        repository=args.repository,
        commit_sha=args.commit_sha,
        tree_sha=args.tree_sha,
        ref=args.ref,
        run_id=args.run_id,
        run_attempt=args.run_attempt,
        event=args.event,
        gates=gates,
        artifact_checksums=evidence_path_checksums(policy, manifest),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"STAGE_ACCEPTANCE_RESULT={evidence['overall_result']}")
    print(f"STAGE_ACCEPTANCE_EVIDENCE={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
