"""Create local-only configuration; never overwrite an existing environment."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def initialize(root: Path) -> None:
    root_env = root / ".env"
    backend_env = root / "backend" / ".env"
    test_env = root / ".local" / "test.env"
    if any(path.exists() or path.is_symlink() for path in (root_env, backend_env, test_env)):
        raise SystemExit("已有本地配置；为避免覆盖，请按 .env.example 手动核对。")
    password = secrets.token_hex(24)
    root_password = secrets.token_hex(24)
    write_new(
        root_env,
        f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={root_password}\nMYSQL_PORT=3307\n",
    )
    write_new(
        backend_env,
        f"SOLOOPS_DATABASE_URL=mysql+pymysql://soloops:{password}"
        "@127.0.0.1:3307/soloops?charset=utf8mb4\n"
        "SOLOOPS_COOKIE_SECURE=false\n",
    )
    local_dir = root / ".local"
    local_dir.mkdir(exist_ok=True)
    write_new(
        test_env,
        f"SOLOOPS_TEST_DATABASE_URL=mysql+pymysql://soloops:{password}"
        "@127.0.0.1:3308/soloops_test?charset=utf8mb4\n",
    )
    print("已生成本地 .env 和独立测试库配置，均由 .gitignore 排除。")


def write_new(path: Path, content: str) -> None:
    with path.open("x", encoding="utf-8") as file:
        file.write(content)


def main() -> None:
    initialize(ROOT)


if __name__ == "__main__":
    main()
