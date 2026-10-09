import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

import pytest


def load_backup() -> ModuleType:
    path = Path(__file__).resolve().parents[2] / "scripts" / "database_backup.py"
    spec = importlib.util.spec_from_file_location("database_backup", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    "name",
    ["soloops", "soloops_test", "../soloops", "soloops_restore_x_test;DROP DATABASE soloops"],
)
def test_restore_rejects_nonisolated_target_before_reading_backup(name: str) -> None:
    tool = load_backup()
    tool.verified_backup = Mock(side_effect=AssertionError("must not read backup"))
    with pytest.raises(ValueError, match="恢复目标"):
        tool.restore("synthetic", name)


@pytest.mark.parametrize("name", ["..", "../outside", "/absolute", "C:\\outside"])
def test_backup_directory_cannot_escape_ignored_local_storage(name: str) -> None:
    with pytest.raises(ValueError):
        load_backup().backup_directory(name)


def test_restore_refuses_modified_dump_before_creating_a_database(tmp_path: Path) -> None:
    tool = load_backup()
    tool.BACKUPS = tmp_path
    folder = tmp_path / "synthetic"
    folder.mkdir()
    (folder / "backup.sql").write_bytes(b"modified SQL")
    (folder / "manifest.json").write_text(
        json.dumps({"format": "soloops-backup-v1", "tables": {}, "sha256": "mismatch"})
    )
    tool.root_sql = Mock(side_effect=AssertionError("must not create database"))
    with pytest.raises(ValueError, match="SHA256"):
        tool.restore("synthetic", "soloops_restore_hash_test")


def test_existing_target_stops_before_user_creation_or_import(tmp_path: Path) -> None:
    tool = load_backup()
    tool.verified_backup = Mock(return_value=(tmp_path / "unused.sql", {}))
    tool.root_sql = Mock(side_effect=RuntimeError("target exists"))
    with pytest.raises(RuntimeError, match="target exists"):
        tool.restore("synthetic", "soloops_restore_existing_test")
    assert tool.root_sql.call_count == 1
    statement = tool.root_sql.call_args.args[1]
    assert statement.startswith("CREATE DATABASE `soloops_restore_existing_test`")
    assert "IF NOT EXISTS" not in statement


def test_failed_import_runs_as_target_only_user_and_removes_that_user(tmp_path: Path) -> None:
    tool = load_backup()
    dump = tmp_path / "synthetic.sql"
    dump.write_bytes(b"USE soloops_test; SELECT 1;")
    tool.verified_backup = Mock(return_value=(dump, {}))
    tool.root_sql = Mock(return_value="")
    process = Mock(returncode=1, stderr=b"private details")
    original = tool.subprocess.run
    tool.subprocess.run = Mock(return_value=process)
    try:
        with pytest.raises(RuntimeError, match="隔离恢复失败") as error:
            tool.restore("synthetic", "soloops_restore_restricted_test")
        assert "private details" not in str(error.value)
        command = tool.subprocess.run.call_args.args[0]
        assert "-uroot" not in command
        assert "--local-infile=0" in command and "--binary-mode=1" in command
        password = tool.subprocess.run.call_args.kwargs["env"]["MYSQL_PWD"]
        assert password not in " ".join(command)
        statements = [call.args[1] for call in tool.root_sql.call_args_list]
        assert "`soloops\\_restore\\_restricted\\_test`.*" in statements[1]
        assert statements[-1].startswith("DROP USER IF EXISTS 'restore_")
    finally:
        tool.subprocess.run = original
