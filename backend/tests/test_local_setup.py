import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from dotenv import dotenv_values

SOURCE = Path(__file__).resolve().parents[2] / "scripts" / "setup_local.py"
CONFIGS = (".env", "backend/.env", ".local/test.env")


def run_setup(root: Path) -> subprocess.CompletedProcess[bytes]:
    (root / "backend").mkdir(exist_ok=True)
    (root / "scripts").mkdir(exist_ok=True)
    script = root / "scripts" / SOURCE.name
    shutil.copyfile(SOURCE, script)
    return subprocess.run([sys.executable, str(script)], capture_output=True, check=False)


@pytest.mark.parametrize("existing", CONFIGS)
def test_refuses_existing_config_without_writing_any_other_file(
    tmp_path: Path, existing: str
) -> None:
    path = tmp_path / existing
    path.parent.mkdir(parents=True, exist_ok=True)
    original = b"existing-local-config\n"
    path.write_bytes(original)
    assert run_setup(tmp_path).returncode != 0
    assert path.read_bytes() == original
    assert all(not (tmp_path / name).exists() for name in CONFIGS if name != existing)


def test_fresh_setup_generates_matching_separate_credentials_and_refuses_repeat(
    tmp_path: Path,
) -> None:
    assert run_setup(tmp_path).returncode == 0
    root = dotenv_values(tmp_path / ".env")
    backend = dotenv_values(tmp_path / "backend/.env")
    test = dotenv_values(tmp_path / ".local/test.env")
    password = root["MYSQL_PASSWORD"]
    assert password and len(password) == 48 and password != root["MYSQL_ROOT_PASSWORD"]
    assert backend["SOLOOPS_DATABASE_URL"] == (
        f"mysql+pymysql://soloops:{password}@127.0.0.1:3307/soloops?charset=utf8mb4"
    )
    assert test["SOLOOPS_TEST_DATABASE_URL"] == (
        f"mysql+pymysql://soloops:{password}@127.0.0.1:3308/soloops_test?charset=utf8mb4"
    )
    snapshots = {name: (tmp_path / name).read_bytes() for name in CONFIGS}
    assert run_setup(tmp_path).returncode != 0
    assert snapshots == {name: (tmp_path / name).read_bytes() for name in CONFIGS}
