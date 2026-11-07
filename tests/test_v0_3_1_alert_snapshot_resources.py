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
    path = ROOT / "scripts/verify_v0_3_1_alert_snapshot_resources.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_alert_snapshot_resources", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load alert snapshot verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031AlertSnapshotResourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_resource_allowlist_cannot_expand(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["resources"])["allowlist"].append("event")
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "allowlist"):
            VERIFIER.validate_contract(changed)

    def test_mutable_inbox_state_cannot_be_exposed(self) -> None:
        changed = copy.deepcopy(self.schema)
        definitions = cast(dict[str, Any], changed["$defs"])
        alert = cast(dict[str, Any], definitions["alert"])
        cast(dict[str, Any], alert["properties"])["acknowledged_at"] = {"type": "string"}
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "mutable inbox"):
            VERIFIER.validate_schema(changed)

    def test_external_order_submission_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["safety"])["external_order_submission_allowed"] = True
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "unsafe capability"):
            VERIFIER.validate_contract(changed)

    def test_nexora_gate_cannot_open_early(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["scope"])["nexora_p3_03_opened"] = True
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "scope safety gate"):
            VERIFIER.validate_contract(changed)

    def test_transition_requires_same_sha_ci_acceptance(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["transition"])["next_allowed_stage"] = "TRD-V031-06"
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "bypasses CI"):
            VERIFIER.validate_contract(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031AlertSnapshotError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
