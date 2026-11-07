#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from v0_3_1_stage_acceptance import (
    ROOT,
    StageAcceptanceError,
    load_evidence_schema,
    load_json,
    load_manifest,
    load_policy,
    validate_evidence,
    validate_evidence_schema,
    validate_historical_freezes,
    validate_manifest,
    validate_policy,
    validate_prerequisite,
)

WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-stage-acceptance.yml"
DOCUMENTATION_PATH = ROOT / "docs/v0.3.1/development-workflow.md"


def validate_workflow(path: Path = WORKFLOW_PATH) -> None:
    workflow = path.read_text(encoding="utf-8")
    required_fragments = (
        "workflow_call:",
        "permissions:",
        "actions: read",
        "contents: read",
        "prerequisite:",
        "stage_contract:",
        "backend:",
        "postgresql:",
        "frontend:",
        "security:",
        "evidence:",
        "always() && !cancelled()",
        "actions/upload-artifact@v4",
        "retention-days: 90",
        "generate_v0_3_1_acceptance_evidence.py",
        "fetch_v0_3_1_acceptance_evidence.py",
    )
    for fragment in required_fragments:
        if fragment not in workflow:
            raise StageAcceptanceError(f"reusable workflow missing: {fragment}")
    if "secrets: inherit" in workflow:
        raise StageAcceptanceError("stage acceptance workflow must not inherit secrets")


def validate_documentation(path: Path = DOCUMENTATION_PATH) -> None:
    documentation = path.read_text(encoding="utf-8")
    for fragment in (
        "Implementation + Acceptance",
        "Stage N → CI Acceptance PASS → Stage N+1",
        "Failed",
        "Cancelled",
        "NEX-P3-03",
        "۹۰ روز",
        "Release Candidate",
        "Final Release Cut",
    ):
        if fragment not in documentation:
            raise StageAcceptanceError(f"workflow documentation missing: {fragment}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the v0.3.1 integrated acceptance policy.")
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--expected-stage")
    parser.add_argument("--expected-commit")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = load_policy()
    validate_policy(policy)
    validate_historical_freezes(policy)
    validate_evidence_schema(load_evidence_schema())
    manifest = load_manifest("TRD-V031-05")
    validate_manifest(policy, manifest)
    validate_prerequisite(policy, manifest)
    validate_workflow()
    validate_documentation()
    if args.evidence is not None:
        validate_evidence(
            policy,
            load_json(args.evidence),
            expected_stage_id=args.expected_stage,
            expected_commit_sha=args.expected_commit,
        )

    print("TRD_V031_STAGE_ACCEPTANCE_POLICY=PASS")
    print("TRD_V031_HISTORICAL_FREEZES_00_TO_04=PRESERVED")
    print("TRD_V031_ACCEPTANCE_EVIDENCE_SCHEMA=PASS")
    print("TRD_V031_SEPARATE_STAGE_FREEZE=NOT_REQUIRED")
    print("TRD_V031_RELEASE_MILESTONE_FREEZE=PRESERVED")
    print("NEX_P3_03_GATE=PRESERVED_UNTIL_REAL_PROVIDER_SMOKE")
    print("TRD_BOT_LIVE_EXECUTION=DISABLED")
    print("NEXT_ALLOWED_STAGE=TRD-V031-05")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
