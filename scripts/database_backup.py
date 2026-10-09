"""Back up one SoloOps database and verify restore into a NEW isolated test database."""

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKUPS = ROOT / ".local" / "backups"
SOURCES = {"mysql": "soloops", "mysql-test": "soloops_test"}
MYSQL_FLAGS = [
    "--batch",
    "--skip-column-names",
    "--raw",
    "--binary-mode=1",
    "--local-infile=0",
    "--default-character-set=utf8mb4",
]
ROOT_CLIENT = (
    'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; '
    "exec mysql -uroot --batch --skip-column-names --raw --binary-mode=1 "
    "--local-infile=0 --default-character-set=utf8mb4"
)
DUMP = (
    'export MYSQL_PWD="$MYSQL_ROOT_PASSWORD"; '
    "exec mysqldump -uroot --single-transaction --no-tablespaces "
    "--set-gtid-purged=OFF --skip-add-locks --hex-blob "
    '--default-character-set=utf8mb4 "$MYSQL_DATABASE"'
)


def compose(service: str) -> list[str]:
    if service not in SOURCES:
        raise ValueError("只支持 compose 中的 mysql 或 mysql-test")
    return ["docker", "compose", "exec", "-T", service]


def root_sql(service: str, sql: str) -> str:
    result = subprocess.run(
        [*compose(service), "sh", "-c", ROOT_CLIENT],
        input=sql.encode("utf-8"),
        capture_output=True,
        cwd=ROOT,
        check=False,
    )
    if result.returncode:
        # Database/client errors may embed query text or credentials. Never echo them.
        raise RuntimeError("数据库操作失败；确认容器已启动、目标不存在及本机配置正确")
    return result.stdout.decode("utf-8")


def identifier(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_]{1,64}", value):
        raise ValueError("数据库标识无效")
    return f"`{value}`"


def target_name(value: str) -> str:
    if len(value) > 64 or not re.fullmatch(r"soloops_restore_[a-z0-9_]+_test", value):
        raise ValueError("恢复目标必须是新名称 soloops_restore_<name>_test（最多64字符）")
    return identifier(value)


def backup_directory(name: str) -> Path:
    if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", name):
        raise ValueError("备份名仅允许字母、数字、横线、下划线，长度1至80")
    directory = (BACKUPS / name).resolve()
    if directory.parent != BACKUPS.resolve():
        raise ValueError("备份必须位于本项目 .local/backups 内")
    return directory


def summary(service: str, database: str) -> dict[str, Any]:
    db = identifier(database)
    tables = root_sql(
        service,
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        f"WHERE TABLE_SCHEMA='{database}' AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME;",
    ).splitlines()
    if "alembic_version" not in tables:
        raise RuntimeError("数据库没有 SoloOps 迁移记录，拒绝作为应用备份")
    qualified = [f"{db}.{identifier(table)}" for table in tables]
    sql = f"SELECT version_num FROM {db}.alembic_version;\n"
    sql += "\n".join(f"SELECT COUNT(*) FROM {table};" for table in qualified)
    sql += "\nCHECKSUM TABLE " + ", ".join(qualified) + " EXTENDED;"
    lines = root_sql(service, sql).splitlines()
    if len(lines) != 1 + len(tables) * 2:
        raise RuntimeError("备份结构检查不完整；请检查数据库迁移状态")
    checksums = [line.split("\t")[-1] for line in lines[1 + len(tables) :]]
    if "NULL" in checksums:
        raise RuntimeError("存在无法校验的数据表；请核对存储引擎")
    return {
        "migration": lines[0],
        "tables": {
            table: {"rows": int(lines[index + 1]), "checksum": checksums[index]}
            for index, table in enumerate(tables)
        },
    }


def file_hash(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def backup(service: str, name: str) -> dict[str, Any]:
    directory = backup_directory(name)
    directory.mkdir(parents=True, exist_ok=False)
    before = summary(service, SOURCES[service])
    dump = directory / "backup.sql"
    with dump.open("xb") as stream:
        result = subprocess.run(
            [*compose(service), "sh", "-c", DUMP],
            stdout=stream,
            stderr=subprocess.PIPE,
            cwd=ROOT,
            check=False,
        )
    if result.returncode:
        raise RuntimeError("导出失败，目录内文件不完整；修正问题后使用新备份名重试")
    after = summary(service, SOURCES[service])
    if before != after:
        raise RuntimeError("备份期间数据发生变化；暂停业务写入与调度后使用新备份名重试")
    manifest = {
        "format": "soloops-backup-v1",
        "created_at": datetime.now(UTC).isoformat(),
        "source_service": service,
        "source_database": SOURCES[service],
        "sha256": file_hash(dump),
        **after,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "backup": str(directory),
        "migration": after["migration"],
        "tables": len(after["tables"]),
    }


def verified_backup(name: str) -> tuple[Path, dict[str, Any]]:
    directory = backup_directory(name)
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    dump = directory / "backup.sql"
    if (
        manifest.get("format") != "soloops-backup-v1"
        or not isinstance(manifest.get("tables"), dict)
        or file_hash(dump) != manifest.get("sha256")
    ):
        raise ValueError("备份格式或SHA256校验失败，未执行恢复")
    return dump, manifest


def restore(name: str, target: str) -> dict[str, Any]:
    db = target_name(target)
    dump, manifest = verified_backup(name)
    # CREATE without IF NOT EXISTS is intentional: an existing database must not be touched.
    root_sql(
        "mysql-test", f"CREATE DATABASE {db} CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_as_cs;"
    )
    user = "restore_" + secrets.token_hex(8)
    password = secrets.token_hex(32)
    grant_db = "`" + target.replace("_", "\\_") + "`"
    try:
        root_sql(
            "mysql-test",
            f"CREATE USER '{user}'@'localhost' IDENTIFIED BY '{password}'; "
            f"GRANT ALL PRIVILEGES ON {grant_db}.* TO '{user}'@'localhost';",
        )
        # The SQL file runs as a temporary target-only user, never as root. Binary mode
        # disables client commands; local file loading is off. No password in argv/logs.
        with dump.open("rb") as stream:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "exec",
                    "-T",
                    "-e",
                    "MYSQL_PWD",
                    "mysql-test",
                    "mysql",
                    f"-u{user}",
                    *MYSQL_FLAGS,
                    f"--database={target}",
                ],
                stdin=stream,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                cwd=ROOT,
                env={**os.environ, "MYSQL_PWD": password},
                check=False,
            )
        if result.returncode:
            raise RuntimeError("隔离恢复失败；原库未变，目标库保留供检查，请用新目标名重试")
        actual = summary("mysql-test", target)
        if actual != {"migration": manifest["migration"], "tables": manifest["tables"]}:
            raise RuntimeError("恢复校验不匹配；请勿将此恢复库用于业务")
        return {
            "target": target,
            "migration": actual["migration"],
            "tables": len(actual["tables"]),
            "row_counts_and_checksums": "matched",
            "isolated": True,
        }
    finally:
        root_sql("mysql-test", f"DROP USER IF EXISTS '{user}'@'localhost';")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("backup", help="暂停写入后备份，文件保存在 .local/backups")
    create.add_argument("--service", choices=list(SOURCES), default="mysql")
    create.add_argument("--name", required=True, help="必须是尚不存在的备份名")
    recover = commands.add_parser("restore", help="仅恢复到 mysql-test 的新建隔离库")
    recover.add_argument("--name", required=True)
    recover.add_argument("--target", required=True, help="soloops_restore_<name>_test")
    args = parser.parse_args()
    try:
        result = (
            backup(args.service, args.name)
            if args.command == "backup"
            else restore(args.name, args.target)
        )
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(str(error)) from None
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
