"""HDC transport failures must stop UI actions, even with exit status zero."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import ohos_ui  # noqa: E402


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_hdc_zero_exit_failure_stops_before_layout_read(stream):
    output = {"stdout": "", "stderr": ""}
    output[stream] = "[Fail]Not match target founded, check connect-key please"
    result = subprocess.CompletedProcess([], 0, **output)
    with patch("ohos_ui.subprocess.run", return_value=result) as run:
        with pytest.raises(RuntimeError, match="HDC.*connect-key"):
            ohos_ui.hdc("shell", "uitest", "dumpLayout")
        assert run.call_count == 1


def test_hdc_preserves_successful_output():
    result = subprocess.CompletedProcess([], 0, stdout='{"children": []}', stderr="")
    with patch("ohos_ui.subprocess.run", return_value=result):
        assert ohos_ui.hdc("shell", "cat", ohos_ui.REMOTE) == result.stdout
