"""Create local-only configuration; never overwrite an existing environment."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    root_env = ROOT / ".env"
    backend_env = ROOT / "backend" / ".env"
    if root_env.exists() or backend_env.exists():
        raise SystemExit("已有 .env；为避免覆盖本地配置，请按 .env.example 手动核对。")
    password = secrets.token_hex(24)
    root_password = secrets.token_hex(24)
    root_env.write_text(
        f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={root_password}\nMYSQL_PORT=3307\n",
        encoding="utf-8",
    )
    backend_env.write_text(
        f"SOLOOPS_DATABASE_URL=mysql+pymysql://soloops:{password}"
        "@127.0.0.1:3307/soloops?charset=utf8mb4\n"
        "SOLOOPS_COOKIE_SECURE=false\n",
        encoding="utf-8",
    )
    local_dir = ROOT / ".local"
    local_dir.mkdir(exist_ok=True)
    (local_dir / "test.env").write_text(
        f"SOLOOPS_TEST_DATABASE_URL=mysql+pymysql://soloops:{password}"
        "@127.0.0.1:3308/soloops_test?charset=utf8mb4\n",
        encoding="utf-8",
    )
    print("已生成本地 .env 和独立测试库配置，均由 .gitignore 排除。")


if __name__ == "__main__":
    main()
