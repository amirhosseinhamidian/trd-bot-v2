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
    path = ROOT / "scripts/verify_v0_3_1_event_feed.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_event_feed", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load event feed verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031EventFeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_exactly_once_claim_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["exactly_once_claimed"] = True
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "exactly-once"):
            VERIFIER.validate_contract(changed)

    def test_gap_detection_cannot_be_removed(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["gap_detection"] = "none"
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "gap detection"):
            VERIFIER.validate_contract(changed)

    def test_expired_cursor_cannot_silently_reset(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["expired_cursor_status"] = 200
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "expired cursor"):
            VERIFIER.validate_contract(changed)

    def test_external_orders_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["safety"])["external_order_submission_allowed"] = True
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "unsafe capability"):
            VERIFIER.validate_contract(changed)

    def test_stage_05_same_sha_evidence_is_required(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["prerequisite"])["mode"] = "legacy_freeze"
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "artifact"):
            VERIFIER.validate_manifest(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031EventFeedError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
