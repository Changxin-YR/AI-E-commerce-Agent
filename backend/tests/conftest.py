import os
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from dotenv import dotenv_values
from fastapi.testclient import TestClient
from sqlalchemy import Engine, delete
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.main import create_app
from app.models.base import Base
from app.repositories.database import create_database_engine, create_session_factory
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService

TEST_PASSWORD = "Synthetic-Test-Password-2026!"


@pytest.fixture(scope="session")
def settings() -> Settings:
    local = dotenv_values(Path(__file__).resolve().parents[2] / ".local" / "test.env")
    url = os.getenv("SOLOOPS_TEST_DATABASE_URL") or local.get("SOLOOPS_TEST_DATABASE_URL")
    if not url:
        pytest.fail("Set SOLOOPS_TEST_DATABASE_URL to an isolated MySQL database ending in _test")
    database = make_url(url).database or ""
    if not database.endswith("_test"):
        pytest.fail("Refusing to modify a database whose name does not end in _test")
    with patch.dict(os.environ, {"SOLOOPS_DATABASE_URL": url}):
        command.upgrade(Config("alembic.ini"), "head")
    return Settings(
        database_url=url,
        trusted_hosts=["testserver"],
        trusted_origins=["http://testserver"],
    )


@pytest.fixture(scope="session")
def engine(settings: Settings) -> Iterator[Engine]:
    database_engine = create_database_engine(settings)
    yield database_engine
    database_engine.dispose()


@pytest.fixture()
def session_factory(engine: Engine) -> sessionmaker[Session]:
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(delete(table))
    return create_session_factory(engine)


@pytest.fixture()
def client(settings: Settings, session_factory: sessionmaker[Session]) -> Iterator[TestClient]:
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="seller", password=TEST_PASSWORD)
        )
    with TestClient(create_app(settings)) as test_client:
        test_client.headers.update({"X-SoloOps-Client": "web", "Origin": "http://testserver"})
        yield test_client


@pytest.fixture()
def logged_in(client: TestClient) -> TestClient:
    response = client.post(
        "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client
