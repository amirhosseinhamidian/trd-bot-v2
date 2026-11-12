from __future__ import annotations

import copy
import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]


def load_verifier() -> ModuleType:
    path = ROOT / "scripts/verify_v0_3_1_final_release.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_final_release", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load final release verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031FinalReleaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)
        self.basis = VERIFIER.load_json(VERIFIER.BASIS_PATH)

    def test_repository_release_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_failed_stage_10_run_cannot_be_a_release_prerequisite(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["prerequisite"])["workflow_conclusion"] = "failure"
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "not successful"):
            VERIFIER.validate_contract(changed)

    def test_tag_cannot_bypass_same_sha_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["release"])[
            "tag_creation_requires_successful_same_sha_acceptance"
        ] = False
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "same-SHA"):
            VERIFIER.validate_contract(changed)

    def test_release_tag_automation_cannot_be_disabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["release"])["tag_creation_automated_in_final_workflow"] = False
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "automation"):
            VERIFIER.validate_contract(changed)

    def test_real_provider_smoke_cannot_be_replaced_with_fixtures(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["acceptance"])[
            "same_run_real_local_provider_smoke_required"
        ] = False
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "real_local"):
            VERIFIER.validate_contract(changed)

    def test_nex_p3_03_is_not_opened_by_this_release(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["compatibility"])["nexora_p3_03_opened_by_this_release"] = True
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "opened"):
            VERIFIER.validate_contract(changed)

    def test_live_execution_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["safety"])["live_execution"] = True
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "live_execution"):
            VERIFIER.validate_contract(changed)

    def test_committed_basis_cannot_pre_accept_current_ci(self) -> None:
        changed = copy.deepcopy(self.basis)
        changed["accepted"] = True
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "pre-accept"):
            VERIFIER.validate_basis(changed)

    def test_release_has_no_following_stage_or_freeze_task(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["next_stage"] = "TRD-V031-12"
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "next stage"):
            VERIFIER.validate_manifest(changed)
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031FinalReleaseError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
