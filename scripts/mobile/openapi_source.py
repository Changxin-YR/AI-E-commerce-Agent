"""Load the existing API schema without starting lifespan or connecting to MySQL."""

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def load_openapi() -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "backend"))
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(
        _env_file=None,
        database_url="mysql+pymysql://schema_only@127.0.0.1:1/schema_only",
        scheduler_enabled=False,
        model_enabled=False,
        outbound_enabled=False,
    )
    # Engine construction is lazy. No TestClient, lifespan, session or API call is made.
    app = create_app(settings)
    return app.openapi()
