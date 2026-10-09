"""Start an isolated, reproducible API for browser acceptance tests."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import uvicorn  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from dotenv import dotenv_values  # noqa: E402
from sqlalchemy import delete  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.base import Base  # noqa: E402
from app.repositories.database import create_database_engine, create_session_factory  # noqa: E402
from app.repositories.unit_of_work import UnitOfWork  # noqa: E402
from app.schemas.identity import AccountInput  # noqa: E402
from app.services.auth import AuthService  # noqa: E402
from scripts.e2e_analysis import configure as configure_analysis  # noqa: E402
from scripts.e2e_mail import configure as configure_mail  # noqa: E402


def main() -> None:
    local = dotenv_values(ROOT.parent / ".local" / "test.env")
    url = os.getenv("SOLOOPS_TEST_DATABASE_URL") or local.get("SOLOOPS_TEST_DATABASE_URL")
    if not url or not (make_url(url).database or "").endswith("_test"):
        raise SystemExit("Browser tests require an isolated database ending in _test")
    os.environ["SOLOOPS_DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    settings = Settings(
        _env_file=None,
        database_url=url,
        model_enabled=False,
        scheduler_enabled=False,
        model_provider="openai_responses",
        model_api_key=None,
        model_name="",
        model_input_usd_per_million=None,
        model_output_usd_per_million=None,
        outbound_enabled=False,
        trusted_origins=["http://127.0.0.1:5174"],
    )
    engine = create_database_engine(settings)
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    with create_session_factory(engine)() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="e2e_seller", password="Synthetic-E2E-Password-2026!")
        )
    application = create_app(settings)
    configure_mail(application, settings, create_session_factory(engine))
    configure_analysis(application, settings)
    engine.dispose()
    uvicorn.run(application, host="127.0.0.1", port=8001, access_log=False)


if __name__ == "__main__":
    main()
