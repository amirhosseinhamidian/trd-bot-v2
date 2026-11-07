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
    path = ROOT / "scripts/verify_v0_3_1_decision_review_commands.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_decision_review_commands", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load decision-review verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031DecisionReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_idempotency_conflict_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["same_key_different_body_status"] = 202
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "409 conflict"):
            VERIFIER.validate_contract(changed)

    def test_source_checksum_guard_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["source_evidence_checksum_required"] = False
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "checksum guard"):
            VERIFIER.validate_contract(changed)

    def test_paper_shadow_boundary_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["portfolio_modes"] = ["paper", "shadow", "live"]
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "mode boundary"):
            VERIFIER.validate_contract(changed)

    def test_execution_side_effect_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["ownership"])["execution_authorization_created"] = True
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "unsafe review side effect"):
            VERIFIER.validate_contract(changed)

    def test_stage_06_same_sha_evidence_is_required(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["prerequisite"])["mode"] = "legacy_freeze"
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "artifact"):
            VERIFIER.validate_manifest(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031DecisionReviewError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
