#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from v0_3_1_stage_acceptance import load_manifest, load_policy, validate_manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the focused gate for one v0.3.1 stage.")
    parser.add_argument("--stage-id", required=True)
    return parser.parse_args()


def run_stage_gate(stage_id: str) -> None:
    policy = load_policy()
    manifest = load_manifest(stage_id)
    validate_manifest(policy, manifest, require_candidate=True)
    verification = cast(dict[str, Any], manifest["verification"])
    verifier = cast(str, verification["verifier_path"])
    unittest_path = cast(str, verification["unittest_path"])
    focused = cast(list[str], verification["focused_pytest_paths"])
    for path in [verifier, unittest_path, *focused]:
        if not Path(path).is_file():
            raise RuntimeError(f"stage verification path missing: {path}")

    commands = (
        [sys.executable, verifier],
        [sys.executable, "-m", "unittest", unittest_path, "-v"],
        [sys.executable, "-m", "pytest", *focused, "-v"],
    )
    for command in commands:
        subprocess.run(command, check=True)


def main() -> int:
    args = parse_args()
    run_stage_gate(args.stage_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
