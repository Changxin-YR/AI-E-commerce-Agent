"""Prevent stale or disconnected OHOS evidence from being certified as installed."""

import importlib.util
import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "export_evidence", ROOT / "scripts/mobile/export_evidence.py"
)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)
sys.modules["export_evidence"] = export
spec = importlib.util.spec_from_file_location(
    "export_ohos_closure", ROOT / "scripts/mobile/export_ohos_closure.py"
)
closure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(closure)


class OHOSClosureEvidenceTests(unittest.TestCase):
    def test_empty_install_output_is_not_success(self):
        self.assertFalse(closure.installed_successfully(""))
        self.assertFalse(closure.installed_successfully("[Fail] Device not connected"))
        self.assertTrue(closure.installed_successfully("[Info] msg:install bundle successfully."))

    def test_conflicting_install_failure_is_not_success(self):
        self.assertFalse(
            closure.installed_successfully("install bundle successfully\n[Fail] transport")
        )

    def test_snapshot_must_postdate_installation(self):
        installed = datetime(2026, 10, 11, 8, tzinfo=UTC)
        record = {"at": "2026-10-11T07:59:59+00:00", "hap_sha256": "current"}
        with self.assertRaisesRegex(ValueError, "predates"):
            closure.validate_snapshot(record, installed, "current")

    def test_snapshot_must_match_built_artifact(self):
        installed = datetime(2026, 10, 11, 8, tzinfo=UTC)
        record = {"at": "2026-10-11T08:00:01+00:00", "hap_sha256": "old"}
        with self.assertRaisesRegex(ValueError, "different HAP"):
            closure.validate_snapshot(record, installed, "current")
        record["hap_sha256"] = "current"
        closure.validate_snapshot(record, installed, "current")
