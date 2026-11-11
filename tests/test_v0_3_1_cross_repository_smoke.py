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
    path = ROOT / "scripts/verify_v0_3_1_cross_repository_smoke.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_cross_repository_smoke", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load cross-repository smoke verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031CrossRepositorySmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.profile = VERIFIER.load_json(VERIFIER.PROFILE_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_real_provider_smoke_cannot_be_replaced_with_fixtures(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["acceptance"])["real_provider_smoke"] = False
        with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, "real_provider_smoke"):
            VERIFIER.validate_contract(changed)

    def test_partial_scenario_pass_cannot_claim_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["acceptance"])["required_scenario_count"] = 11
        with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, "scenario coverage"):
            VERIFIER.validate_contract(changed)

    def test_nexora_commit_and_tree_are_pinned(self) -> None:
        for key, message in (("commit_sha", "commit"), ("tree_sha", "tree")):
            changed = copy.deepcopy(self.contract)
            cast(dict[str, Any], changed["consumer"])[key] = "0" * 40
            with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, message):
                VERIFIER.validate_contract(changed)

    def test_provider_0_3_0_cannot_be_declared_compatible(self) -> None:
        changed = copy.deepcopy(self.profile)
        cast(dict[str, Any], changed["provider"])["release_0_3_0_compatible"] = True
        with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, "0.3.0"):
            VERIFIER.validate_profile(changed)

    def test_nex_p3_03_cannot_open_before_same_sha_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["transition"])["nex_p3_03_eligibility"] = "OPEN"
        with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, "opened early"):
            VERIFIER.validate_contract(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031CrossRepositorySmokeError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
