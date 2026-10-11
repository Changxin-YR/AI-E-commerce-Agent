"""Run the Android synthetic backend with an explicit isolated configuration."""

from pathlib import Path

import uvicorn
from app.core.config import Settings
from app.main import create_app
from dotenv import dotenv_values


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / ".local" / "android" / "backend.env")
    url = values.get("SOLOOPS_DATABASE_URL", "") or ""
    if "@127.0.0.1:3311/soloops_android_test?" not in url:
        raise SystemExit("Expected the isolated Android test database on port 3311.")
    settings = Settings(
        _env_file=None,
        database_url=url,
        model_enabled=False,
        model_api_key=None,
        outbound_enabled=False,
        outbound_api_key=None,
        outbound_smtp_authorization_code=None,
        scheduler_enabled=False,
        cookie_secure=False,
        trusted_hosts=["127.0.0.1", "localhost", "10.0.2.2"],
        trusted_origins=["https://localhost", "http://10.0.2.2:8011"],
    )
    uvicorn.run(create_app(settings), host="127.0.0.1", port=8011)


if __name__ == "__main__":
    main()
