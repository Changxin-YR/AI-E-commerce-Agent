"""Generate isolated, synthetic Android test settings without reading other .env files."""

import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / ".local" / "android"


def main() -> None:
    LOCAL.mkdir(parents=True, exist_ok=True)
    targets = [LOCAL / "mysql.env", LOCAL / "backend.env"]
    if any(path.exists() for path in targets):
        raise SystemExit("Android test settings already exist; refusing to overwrite.")
    password = secrets.token_hex(24)
    targets[0].write_text(
        f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={secrets.token_hex(24)}\n",
        encoding="utf-8",
    )
    targets[1].write_text(
        f"SOLOOPS_DATABASE_URL=mysql+pymysql://soloops_android:{password}"
        "@127.0.0.1:3311/soloops_android_test?charset=utf8mb4\n"
        "SOLOOPS_MODEL_ENABLED=false\nSOLOOPS_OUTBOUND_ENABLED=false\n"
        "SOLOOPS_SCHEDULER_ENABLED=false\nSOLOOPS_COOKIE_SECURE=false\n"
        'SOLOOPS_TRUSTED_HOSTS=["127.0.0.1","localhost","10.0.2.2"]\n'
        'SOLOOPS_TRUSTED_ORIGINS=["https://localhost","http://10.0.2.2:8011"]\n',
        encoding="utf-8",
    )
    print("Created isolated settings in .local/android (ignored by Git).")


if __name__ == "__main__":
    main()
