#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

from trd_bot.release_hardening import build_release_hardening_report

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "contracts/trd-bot-v0.3.1-final-release.json"
MANIFEST_PATH = ROOT / "contracts/v0.3.1/stage-acceptance/trd-v031-11.json"
BASIS_PATH = ROOT / "artifacts/v0.3.1/trd-v031-11-release-basis.json"
PROFILE_PATH = ROOT / "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json"
POLICY_PATH = ROOT / "contracts/trd-bot-v0.3.1-stage-acceptance-policy.json"
ROADMAP_PATH = ROOT / "contracts/trd-bot-v0.3.1-nexora-integration-roadmap.json"
WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-final-release.yml"
REUSABLE_WORKFLOW_PATH = ROOT / ".github/workflows/v0-3-1-stage-acceptance.yml"
README_PATH = ROOT / "README.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"

RELEASE_VERSION = "0.3.1"
RELEASE_TAG = "v0.3.1"
ACCEPTED_STAGE_10_COMMIT = "9d2bbf2caa8fa1281efaf053d33c73c5e495d3ef"
ACCEPTED_STAGE_10_TREE = "f2392c9cca0d9e3e58db350d8ba8d7cc3aafa7dd"
ACCEPTED_STAGE_10_RUN_ID = 43088041255
PINNED_NEXORA_COMMIT = "1e114b58b1a9cfc4ef91280c6506aa58bb2f53e8"
PINNED_NEXORA_TREE = "6c5756f177c2f0025faeb776515e99c077630177"
PROFILE_SHA256 = "2d21e80db378c2dc2c1b3a6fbb1f44bcbbad0c34d89f4d073b25e179a55fbcc8"
RELEASE_INVENTORY_CHECKSUM = "7c97e85703da7c312d24deabec9c3f9b7a3d1be19694a69a1c003f458996df68"


class V031FinalReleaseError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise V031FinalReleaseError(message)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(payload, dict), f"{path.name} must contain an object")
    return cast(dict[str, Any], payload)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(contract: Mapping[str, Any]) -> None:
    require(contract.get("schema_version") == "trd-bot-v031-final-release-v1", "schema drift")
    require(contract.get("decision_id") == "TRD-V031-11", "stage ID drift")
    require(contract.get("status") == "candidate", "release is not a candidate")

    prerequisite = contract.get("prerequisite")
    require(isinstance(prerequisite, dict), "Stage 10 prerequisite missing")
    require(prerequisite.get("stage_id") == "TRD-V031-10", "prerequisite stage drift")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_10_COMMIT,
        "Stage 10 commit drift",
    )
    require(
        prerequisite.get("accepted_tree_sha") == ACCEPTED_STAGE_10_TREE,
        "Stage 10 tree drift",
    )
    require(prerequisite.get("workflow_run_id") == ACCEPTED_STAGE_10_RUN_ID, "run ID drift")
    require(prerequisite.get("workflow_run_attempt") == 1, "run attempt drift")
    require(prerequisite.get("workflow_conclusion") == "success", "Stage 10 was not successful")
    for key in ("smoke_artifact", "acceptance_artifact"):
        artifact = prerequisite.get(key)
        require(isinstance(artifact, dict), f"{key} missing")
        digest = artifact.get("digest")
        require(
            isinstance(digest, str) and digest.startswith("sha256:") and len(digest) == 71,
            f"{key} digest invalid",
        )

    release = contract.get("release")
    require(isinstance(release, dict), "release declaration missing")
    require(release.get("version") == RELEASE_VERSION, "release version drift")
    require(release.get("tag") == RELEASE_TAG, "release tag drift")
    require(release.get("tag_must_target_stage_11_accepted_commit") is True, "tag target weakened")
    require(
        release.get("tag_creation_requires_successful_same_sha_acceptance") is True,
        "tag can bypass same-SHA acceptance",
    )
    require(
        release.get("tag_creation_automated_in_final_workflow") is True,
        "release tag automation missing",
    )
    require(release.get("separate_freeze_commit_required") is False, "separate Freeze restored")
    require(
        release.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "release inventory drift",
    )

    acceptance = contract.get("acceptance")
    require(isinstance(acceptance, dict), "acceptance declaration missing")
    for key in (
        "same_sha_ci_acceptance_required",
        "same_run_real_local_provider_smoke_required",
        "fresh_install_migration_required",
        "upgrade_path_migration_required",
        "alembic_check_required",
    ):
        require(acceptance.get(key) is True, f"required acceptance removed: {key}")
    require(acceptance.get("required_smoke_scenarios") == 12, "smoke coverage drift")
    require(
        acceptance.get("required_gates")
        == ["prerequisite", "stage_contract", "backend", "postgresql", "frontend", "security"],
        "required gate inventory drift",
    )
    require(acceptance.get("artifact_retention_days") == 90, "retention drift")

    compatibility = contract.get("compatibility")
    require(isinstance(compatibility, dict), "compatibility declaration missing")
    require(
        compatibility.get("provider_release_range") == ">=0.3.1,<0.4.0",
        "provider range drift",
    )
    require(
        compatibility.get("pinned_nexora_commit_sha") == PINNED_NEXORA_COMMIT,
        "Nexora commit drift",
    )
    require(
        compatibility.get("pinned_nexora_tree_sha") == PINNED_NEXORA_TREE,
        "Nexora tree drift",
    )
    require(compatibility.get("provider_profile_sha256") == PROFILE_SHA256, "profile drift")
    require(
        compatibility.get("trd_provider_compatibility_requires_stage_11_acceptance_and_tag")
        is True,
        "compatibility can be claimed before acceptance and tag",
    )
    require(
        compatibility.get("nexora_p3_03_owned_by_nexora_repository") is True,
        "NEX-P3-03 ownership drift",
    )
    require(
        compatibility.get("nexora_p3_03_opened_by_this_release") is False,
        "NEX-P3-03 opened by TRD BOT",
    )

    safety = contract.get("safety")
    require(isinstance(safety, dict), "safety declaration missing")
    for key in (
        "live_execution",
        "real_money_order_execution",
        "external_order_submission",
        "exchange_credentials",
        "wallet_or_fund_transfer",
        "shared_database_with_nexora",
        "secrets_in_evidence",
        "production_deployment_claimed",
    ):
        require(safety.get(key) is False, f"unsafe capability enabled: {key}")


def validate_manifest(manifest: Mapping[str, Any]) -> None:
    require(manifest.get("stage_id") == "TRD-V031-11", "manifest stage drift")
    require(manifest.get("status") == "candidate", "manifest is not a candidate")
    prerequisite = manifest.get("prerequisite")
    require(isinstance(prerequisite, dict), "manifest prerequisite missing")
    require(prerequisite.get("mode") == "ci_artifact", "Stage 10 artifact not required")
    require(
        prerequisite.get("accepted_commit_sha") == ACCEPTED_STAGE_10_COMMIT,
        "manifest prerequisite drift",
    )
    migration = manifest.get("migration")
    require(isinstance(migration, dict) and migration.get("expected") is False, "migration drift")
    transition = manifest.get("transition")
    require(isinstance(transition, dict), "manifest transition missing")
    require(transition.get("next_stage") is None, "unexpected next stage")
    require(transition.get("separate_freeze_task_required") is False, "separate Freeze restored")


def validate_basis(basis: Mapping[str, Any]) -> None:
    require(
        basis.get("schema_version") == "trd-bot-v031-release-milestone-basis-v1",
        "release basis schema drift",
    )
    require(basis.get("stage_id") == "TRD-V031-11", "release basis stage drift")
    require(basis.get("release_version") == RELEASE_VERSION, "release basis version drift")
    require(basis.get("release_tag") == RELEASE_TAG, "release basis tag drift")
    require(
        basis.get("status") == "candidate_pending_same_sha_ci_acceptance",
        "release basis must remain fail-closed before CI",
    )
    require(basis.get("accepted") is False, "committed basis cannot pre-accept the current CI run")
    prerequisite = basis.get("prerequisite_evidence")
    require(isinstance(prerequisite, dict), "basis prerequisite missing")
    require(prerequisite.get("commit_sha") == ACCEPTED_STAGE_10_COMMIT, "basis commit drift")
    require(prerequisite.get("tree_sha") == ACCEPTED_STAGE_10_TREE, "basis tree drift")
    require(prerequisite.get("workflow_conclusion") == "success", "basis prerequisite failed")

    expected_checksums = {
        "contracts/integration/nexora/v1/trd-bot-v0.3.1-provider-profile.json": sha256_file(
            PROFILE_PATH
        ),
        "contracts/trd-bot-v0.3.1-final-release.json": sha256_file(CONTRACT_PATH),
        "contracts/trd-bot-v0.3.1-nexora-integration-roadmap.json": sha256_file(ROADMAP_PATH),
        "contracts/trd-bot-v0.3.1-stage-acceptance-policy.json": sha256_file(POLICY_PATH),
    }
    require(basis.get("committed_checksums") == expected_checksums, "committed checksum drift")
    require(
        basis.get("release_inventory_checksum") == RELEASE_INVENTORY_CHECKSUM,
        "basis inventory drift",
    )
    handoff = basis.get("same_sha_handoff")
    require(isinstance(handoff, dict), "same-SHA handoff missing")
    require(
        handoff.get("separate_freeze_commit_required") is False,
        "release handoff restored a Freeze commit",
    )


def validate_version_sources() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package = json.loads((ROOT / "frontend/package.json").read_text(encoding="utf-8"))
    package_lock = json.loads((ROOT / "frontend/package-lock.json").read_text(encoding="utf-8"))
    environment = dict(
        line.split("=", maxsplit=1)
        for line in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    )
    runtime = (ROOT / "src/trd_bot/__init__.py").read_text(encoding="utf-8")
    values = {
        pyproject["project"]["version"],
        package["version"],
        package_lock["version"],
        package_lock["packages"][""]["version"],
        environment["TRD_BOT_APP_VERSION"],
    }
    require(values == {RELEASE_VERSION}, "release version sources are inconsistent")
    require(f'__version__ = "{RELEASE_VERSION}"' in runtime, "runtime version drift")


def validate_implementation(workflow: str, reusable: str, readme: str, changelog: str) -> None:
    require(
        "uses: ./.github/workflows/v0-3-1-stage-acceptance.yml" in workflow,
        "reusable acceptance not called",
    )
    require("stage_id: TRD-V031-11" in workflow, "workflow stage drift")
    for marker in (
        "contents: write",
        "needs: acceptance",
        "Create same-SHA release tag",
        'git tag "$RELEASE_TAG" "$GITHUB_SHA"',
        'git push origin "refs/tags/${RELEASE_TAG}"',
        "already targets ${existing}, not ${GITHUB_SHA}",
    ):
        require(marker in workflow, f"fail-closed release tag automation missing: {marker}")
    for marker in (
        "inputs.stage_id == 'TRD-V031-10' || inputs.stage_id == 'TRD-V031-11'",
        "run_v0_3_1_cross_repository_smoke.py",
        "${{ inputs.stage_id }}-smoke-${{ github.sha }}",
        "${{ inputs.stage_id }}-acceptance-${{ github.sha }}",
        "retention-days: 90",
    ):
        require(marker in reusable, f"same-SHA release evidence missing: {marker}")
    require("Current release: **v0.3.1**" in readme, "README release version drift")
    require("## 0.3.1 - 2026-11-12" in changelog, "release notes missing")
    require("NEX-P3-03" in readme and "NEX-P3-03" in changelog, "NEX-P3-03 boundary missing")


def validate_release_inventory() -> None:
    report = build_release_hardening_report(ROOT)
    require(report.passed, f"release inventory failed: {report.failure_reasons}")
    require(report.inventory.product_version == RELEASE_VERSION, "inventory version drift")
    require(
        report.inventory.definition_checksum == RELEASE_INVENTORY_CHECKSUM,
        "release inventory checksum drift",
    )


def verify() -> None:
    validate_contract(load_json(CONTRACT_PATH))
    validate_manifest(load_json(MANIFEST_PATH))
    validate_basis(load_json(BASIS_PATH))
    validate_version_sources()
    validate_implementation(
        WORKFLOW_PATH.read_text(encoding="utf-8"),
        REUSABLE_WORKFLOW_PATH.read_text(encoding="utf-8"),
        README_PATH.read_text(encoding="utf-8"),
        CHANGELOG_PATH.read_text(encoding="utf-8"),
    )
    validate_release_inventory()


def main() -> int:
    verify()
    for marker in (
        "TRD_V031_11_RELEASE_VERSION=0.3.1",
        "TRD_V031_11_STAGE_10_PREREQUISITE=PASS",
        "TRD_V031_11_REAL_LOCAL_PROVIDER_SMOKE=REQUIRED_IN_CI",
        "TRD_V031_11_SAME_SHA_ACCEPTANCE=REQUIRED_BEFORE_TAG",
        "TRD_V031_11_RELEASE_TAG=v0.3.1",
        "TRD_V031_11_SEPARATE_FREEZE_COMMIT=NOT_REQUIRED",
        "TRD_BOT_LIVE_EXECUTION=DISABLED",
        "NEX_P3_03_GATE=OWNED_BY_NEXORA_AND_NOT_OPENED_HERE",
        "NEXT_ALLOWED_STAGE=NONE_RELEASE_CUT",
    ):
        print(marker)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
