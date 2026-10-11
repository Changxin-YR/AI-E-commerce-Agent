from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.mobile_auth import _login_attempts
from app.core.config import Settings
from app.core.security import token_digest
from app.core.time import utc_now
from app.models.identity import LoginSession
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from tests.conftest import TEST_PASSWORD
from tests.test_identity import PROFILE, SHOP


@pytest.fixture(autouse=True)
def clear_throttle() -> None:
    _login_attempts.clear()


def login(client: TestClient) -> dict:
    client.cookies.clear()
    client.headers.pop("Authorization", None)
    client.headers.pop("Origin", None)
    client.headers.pop("X-CSRF-Token", None)
    client.headers["X-SoloOps-Client"] = "mobile"
    response = client.post(
        "/api/mobile/auth/login",
        json={"username": "seller", "password": TEST_PASSWORD, "client_type": "ohos"},
    )
    assert response.status_code == 200, response.text
    assert "set-cookie" not in response.headers
    assert response.headers["Cache-Control"] == "no-store"
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return response.json()


def test_mobile_session_business_write_and_current_logout(
    client: TestClient, session_factory: sessionmaker[Session]
) -> None:
    session = login(client)
    assert session["token_type"] == "Bearer"
    assert session["session_id"]
    assert "csrf_token" not in session
    assert client.get("/api/mobile/auth/session").json()["session_id"] == session["session_id"]
    with session_factory() as db:
        row = db.scalar(select(LoginSession))
        assert row.token_hash == token_digest(session["access_token"])
        assert row.token_hash != session["access_token"]
        assert row.client_type == "ohos" and row.issued_at is not None
    assert client.put("/api/profile", json=PROFILE).status_code == 200
    assert client.post("/api/shops", json=SHOP).status_code == 201
    assert len(client.get("/api/shops").json()) == 1
    assert client.get("/api/auth/session").status_code == 400
    assert client.post("/api/auth/logout").status_code == 400
    assert client.post("/api/mobile/auth/logout").status_code == 204
    assert client.get("/api/shops").status_code == 401


def test_mobile_mixed_credentials_and_web_csrf_stay_rejected(client: TestClient) -> None:
    session = login(client)
    client.cookies.set("soloops_session", "synthetic-cookie")
    assert client.get("/api/shops").status_code == 400
    client.cookies.clear()
    client.headers.pop("Authorization")
    client.cookies.set("soloops_session", session["access_token"])
    assert client.get("/api/profile").status_code == 401
    client.cookies.clear()
    client.headers["X-SoloOps-Client"] = "web"
    response = client.post(
        "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    assert client.put("/api/profile", json=PROFILE).status_code == 403
    web_token = client.cookies.get("soloops_session")
    client.cookies.clear()
    client.headers["Authorization"] = "Bearer " + web_token
    assert client.get("/api/mobile/auth/session").status_code == 401


def test_mobile_logout_all_revokes_other_devices_and_web(client: TestClient) -> None:
    first = login(client)
    second = login(client)
    assert first["session_id"] != second["session_id"]
    assert client.post("/api/mobile/auth/logout-all").status_code == 204
    for session in [first, second]:
        client.headers["Authorization"] = "Bearer " + session["access_token"]
        assert client.get("/api/mobile/auth/session").status_code == 401


def test_mobile_absolute_expiry_and_password_reset(
    client: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    login(client)
    with session_factory() as db:
        row = db.scalar(select(LoginSession))
        row.expires_at = utc_now() - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/mobile/auth/session").status_code == 401
    login(client)
    with session_factory() as db:
        AuthService(UnitOfWork(db), settings).reset_password(
            AccountInput(username="seller", password="Synthetic-Reset-Password-2026!")
        )
    assert client.get("/api/mobile/auth/session").status_code == 401


def test_mobile_unknown_account_attempts_are_throttled(client: TestClient) -> None:
    client.headers["X-SoloOps-Client"] = "mobile"
    for _ in range(20):
        assert (
            client.post(
                "/api/mobile/auth/login", json={"username": "missing", "password": TEST_PASSWORD}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/mobile/auth/login", json={"username": "missing", "password": TEST_PASSWORD}
        ).status_code
        == 429
    )


def test_mobile_migration_preserves_web_session_and_revokes_device(
    client: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    import os
    from unittest.mock import patch

    from alembic import command
    from alembic.config import Config

    mobile = login(client)
    client.headers.pop("Authorization")
    client.headers["X-SoloOps-Client"] = "web"
    assert (
        client.post(
            "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
        ).status_code
        == 200
    )
    web_token = client.cookies.get("soloops_session")
    with patch.dict(os.environ, {"SOLOOPS_DATABASE_URL": settings.database_url.get_secret_value()}):
        config = Config("alembic.ini")
        try:
            command.downgrade(config, "d93f6b210ac4")
        finally:
            command.upgrade(config, "head")
        command.check(config)
    with session_factory() as db:
        sessions = list(db.scalars(select(LoginSession)))
        assert len(sessions) == 1 and sessions[0].client_type == "web"
        assert sessions[0].token_hash == token_digest(web_token)
    client.cookies.clear()
    client.headers["Authorization"] = "Bearer " + mobile["access_token"]
    assert client.get("/api/mobile/auth/session").status_code == 401
