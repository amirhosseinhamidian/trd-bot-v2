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
    path = ROOT / "scripts/verify_v0_3_1_full_resync.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_full_resync", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load full-resync verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031FullResyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_partial_snapshot_publish_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["state_machine"])["partial_snapshot_publish_allowed"] = True
        with self.assertRaisesRegex(VERIFIER.V031FullResyncError, "partial publication"):
            VERIFIER.validate_contract(changed)

    def test_gap_and_operator_guards_cannot_be_removed(self) -> None:
        for key, message in (
            ("aggregate_versions_must_be_contiguous", "gap detection"),
            ("unresolved_gap_requires_operator_intervention", "operator escalation"),
        ):
            changed = copy.deepcopy(self.contract)
            cast(dict[str, Any], changed["state_machine"])[key] = False
            with self.assertRaisesRegex(VERIFIER.V031FullResyncError, message):
                VERIFIER.validate_contract(changed)

    def test_unfrozen_operation_cannot_be_added(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["api_boundary"])["new_operations"] = [
            "POST /api/v1/integration/nexora/resync"
        ]
        with self.assertRaisesRegex(VERIFIER.V031FullResyncError, "endpoint"):
            VERIFIER.validate_contract(changed)

    def test_provider_compatibility_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["safety"])["provider_compatibility_claimed"] = True
        with self.assertRaisesRegex(VERIFIER.V031FullResyncError, "unsafe capability"):
            VERIFIER.validate_contract(changed)

    def test_stage_08_same_sha_evidence_is_required(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["prerequisite"])["mode"] = "legacy_freeze"
        with self.assertRaisesRegex(VERIFIER.V031FullResyncError, "artifact"):
            VERIFIER.validate_manifest(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031FullResyncError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
