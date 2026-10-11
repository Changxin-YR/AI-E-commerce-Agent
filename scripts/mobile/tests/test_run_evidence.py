"""A timed-out launcher must not leave its child running or report success."""

import json
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


class EvidenceTimeoutTests(unittest.TestCase):
    def test_timeout_stops_descendant_and_preserves_output(self):
        name = "timeout-test-" + uuid.uuid4().hex
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "late-write.txt"
            child = (
                "import pathlib,sys,time; time.sleep(3); "
                "pathlib.Path(sys.argv[1]).write_text('still running')"
            )
            parent = (
                "import subprocess,sys,time; "
                f"subprocess.Popen([sys.executable, '-c', {child!r}, sys.argv[1]]); "
                "print('child started', flush=True); time.sleep(30)"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/mobile/run_evidence.py"),
                    "--name",
                    name,
                    "--timeout",
                    "1",
                    "--",
                    sys.executable,
                    "-c",
                    parent,
                    str(marker),
                ],
                cwd=ROOT,
                capture_output=True,
                timeout=15,
                check=False,
            )
            self.assertEqual(result.returncode, 124, result.stdout)
            evidence = next((ROOT / ".local/mobile-m0a").glob(f"*-{name}.json"))
            record = json.loads(evidence.read_text(encoding="utf-8"))
            self.assertTrue(record["timed_out"])
            self.assertEqual(record["exit_code"], 124)
            log = Path(record["log"]).read_text(encoding="utf-8", errors="replace")
            self.assertIn("child started", log)
            self.assertIn("TIMEOUT", log)
            time.sleep(3.5)
            self.assertFalse(marker.exists(), "Timed-out command left a child process alive")


if __name__ == "__main__":
    unittest.main()
