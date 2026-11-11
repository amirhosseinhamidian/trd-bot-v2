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
    path = ROOT / "scripts/verify_v0_3_1_export_jobs.py"
    spec = importlib.util.spec_from_file_location("verify_v0_3_1_export_jobs", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load export-job verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_verifier()


class V031ExportJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract = VERIFIER.load_json(VERIFIER.CONTRACT_PATH)
        self.schema = VERIFIER.load_json(VERIFIER.SCHEMA_PATH)
        self.manifest = VERIFIER.load_json(VERIFIER.MANIFEST_PATH)

    def test_repository_candidate_is_valid(self) -> None:
        VERIFIER.verify()

    def test_partial_manifest_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["partial_manifest_allowed"] = True
        with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, "partial manifest"):
            VERIFIER.validate_contract(changed)

    def test_checksum_and_lineage_cannot_be_removed(self) -> None:
        for key, message in (
            ("file_checksums_required", "checksums"),
            ("source_lineage_required", "lineage"),
        ):
            changed = copy.deepcopy(self.contract)
            cast(dict[str, Any], changed["protocol"])[key] = False
            with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, message):
                VERIFIER.validate_contract(changed)

    def test_secret_export_cannot_be_enabled(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["protocol"])["secret_fields_allowed"] = True
        with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, "secret"):
            VERIFIER.validate_contract(changed)

    def test_provider_compatibility_cannot_be_claimed(self) -> None:
        changed = copy.deepcopy(self.contract)
        cast(dict[str, Any], changed["safety"])["provider_compatibility_claimed"] = True
        with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, "unsafe capability"):
            VERIFIER.validate_contract(changed)

    def test_stage_07_same_sha_evidence_is_required(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["prerequisite"])["mode"] = "legacy_freeze"
        with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, "artifact"):
            VERIFIER.validate_manifest(changed)

    def test_separate_freeze_cannot_return(self) -> None:
        changed = copy.deepcopy(self.manifest)
        cast(dict[str, Any], changed["transition"])["separate_freeze_task_required"] = True
        with self.assertRaisesRegex(VERIFIER.V031ExportJobsError, "Freeze"):
            VERIFIER.validate_manifest(changed)


if __name__ == "__main__":
    unittest.main()
