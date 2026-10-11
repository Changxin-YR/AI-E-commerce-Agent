"""Portable evidence must not expose local paths inside Hvigor assignments."""

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "export_evidence", ROOT / "scripts/mobile/export_evidence.py"
)
export = importlib.util.module_from_spec(spec)
spec.loader.exec_module(export)


class PortableCommandTests(unittest.TestCase):
    def test_hvigor_assignment_and_plain_path_are_portable(self):
        config = ROOT / "apps/soloops_flutter/.dart_tool/package_config.json"
        self.assertEqual(
            export.portable_command(
                [
                    "hvigorw.bat",
                    "-p",
                    f"PACKAGE_CONFIG={config}",
                    "product=default",
                    str(config),
                ]
            ),
            [
                "hvigorw.bat",
                "-p",
                "PACKAGE_CONFIG=apps/soloops_flutter/.dart_tool/package_config.json",
                "product=default",
                "apps/soloops_flutter/.dart_tool/package_config.json",
            ],
        )

    def test_external_assignment_is_rejected(self):
        external = ROOT.parent / "private-package-config.json"
        with self.assertRaises(ValueError):
            export.portable_command([f"PACKAGE_CONFIG={external}"])

    def test_known_external_executables_have_portable_names(self):
        for name in ["python", "adb", "hdc", "ruff", "node"]:
            with self.subTest(name=name):
                executable = ROOT.parent / (name + ".exe")
                self.assertEqual(export.portable_command([str(executable)]), [name])
