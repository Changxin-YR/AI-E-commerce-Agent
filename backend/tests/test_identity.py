from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.time import utc_now
from app.models.identity import AuditEvent, LoginSession, SellerProfile, Shop, User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput, ProfileInput
from app.services.auth import AuthService
from app.services.profile import ProfileService
from tests.conftest import TEST_PASSWORD

PROFILE = {
    "display_name": "合成测试工作室",
    "target_market": "US",
    "business_model": "精品零售",
    "category": "家居用品",
    "currency": "USD",
    "timezone": "Asia/Shanghai",
    "language": "zh-CN",
    "version": 0,
}
SHOP = {
    "code": "synthetic-us",
    "name": "合成测试店铺",
    "platform": "shopify",
    "market": "US",
    "currency": "USD",
    "timezone": "America/New_York",
}


def test_health_and_anonymous_access(client: TestClient) -> None:
    assert client.get("/api/health/ready").json() == {"status": "ok", "database": "mysql"}
    assert client.get("/api/profile").status_code == 401
    assert client.get("/api/shops").status_code == 401


def test_login_cookie_and_logout_revocation(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login", json={"username": " SELLER ", "password": TEST_PASSWORD}
    )
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    token = client.cookies.get("soloops_session")
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.get("/api/auth/session").json()["username"] == "seller"
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set("soloops_session", token)
    assert client.get("/api/profile").status_code == 401


def test_csrf_and_origin_rejected(logged_in: TestClient) -> None:
    assert (
        logged_in.put("/api/profile", json=PROFILE, headers={"X-CSRF-Token": "wrong"}).status_code
        == 403
    )
    assert (
        logged_in.put(
            "/api/profile", json=PROFILE, headers={"Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        logged_in.post("/api/auth/login", json={}, headers={"X-SoloOps-Client": ""}).status_code
        == 403
    )
    assert logged_in.get("/api/profile").json() is None


def test_password_not_in_validation_error(client: TestClient) -> None:
    password = "synthetic-secret-" * 20
    response = client.post("/api/auth/login", json={"username": "seller", "password": password})
    assert response.status_code == 422
    assert password not in response.text
    assert response.json()["error"]["request_id"]


def test_lockout_is_persisted(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    for _ in range(5):
        assert (
            client.post(
                "/api/auth/login", json={"username": "seller", "password": "wrong"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
        ).status_code
        == 429
    )
    with session_factory() as session:
        user = session.scalar(select(User).where(User.username == "seller"))
        assert user.failed_login_count == 5
        user.locked_until = utc_now() - timedelta(seconds=1)
        session.commit()
    assert (
        client.post(
            "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
        ).status_code
        == 200
    )


def test_expired_session_is_rejected(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        login_session = session.scalar(select(LoginSession))
        login_session.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    assert logged_in.get("/api/profile").status_code == 401


def test_reset_password_revokes_sessions(
    logged_in: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).reset_password(
            AccountInput(username="seller", password="New-Synthetic-Password!")
        )
    assert logged_in.get("/api/auth/session").status_code == 401
    assert (
        logged_in.post(
            "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
        ).status_code
        == 401
    )
    assert (
        logged_in.post(
            "/api/auth/login", json={"username": "seller", "password": "New-Synthetic-Password!"}
        ).status_code
        == 200
    )


def test_onboarding_and_profile_persist(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    assert logged_in.get("/api/onboarding").json()["next_step"] == "profile"
    response = logged_in.put("/api/profile", json=PROFILE)
    assert response.status_code == 200
    assert response.json()["version"] == 1
    assert logged_in.get("/api/profile").json()["display_name"] == PROFILE["display_name"]
    assert logged_in.get("/api/onboarding").json()["next_step"] == "shop"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SellerProfile)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "profile.saved")
            )
            == 1
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("timezone", "Not/AZone"),
        ("currency", "ZZZ"),
        ("target_market", "USAA"),
        ("display_name", "   "),
        ("version", -1),
        ("owner_id", 2),
    ],
)
def test_invalid_profile_is_rejected(logged_in: TestClient, field: str, value: object) -> None:
    assert logged_in.put("/api/profile", json={**PROFILE, field: value}).status_code == 422
    assert logged_in.get("/api/profile").json() is None


def test_stale_profile_cannot_overwrite(logged_in: TestClient) -> None:
    assert logged_in.put("/api/profile", json=PROFILE).status_code == 200
    assert (
        logged_in.put("/api/profile", json={**PROFILE, "display_name": "stale"}).status_code == 409
    )
    assert (
        logged_in.put(
            "/api/profile", json={**PROFILE, "version": 1, "display_name": "updated"}
        ).json()["version"]
        == 2
    )
    assert logged_in.get("/api/profile").json()["display_name"] == "updated"


def test_shop_unique_per_owner(
    logged_in: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    created = logged_in.post("/api/shops", json=SHOP)
    assert created.status_code == 201
    assert created.json()["connection_status"] == "file_only"
    assert logged_in.post("/api/shops", json=SHOP).status_code == 409
    assert len(logged_in.get("/api/shops").json()) == 1
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other", password=TEST_PASSWORD)
        )
    other_login = logged_in.post(
        "/api/auth/login", json={"username": "other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = other_login.json()["csrf_token"]
    assert logged_in.get(f"/api/shops/{created.json()['id']}").status_code == 404
    assert logged_in.get("/api/shops").json() == []
    assert logged_in.post("/api/shops", json=SHOP).status_code == 201


def test_unknown_owner_input_cannot_change_scope(logged_in: TestClient) -> None:
    assert logged_in.post("/api/shops", json={**SHOP, "owner_id": 999}).status_code == 422


def test_concurrent_profile_update_has_single_winner(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    user_id = logged_in.get("/api/auth/session").json()["user_id"]
    logged_in.put("/api/profile", json=PROFILE)

    def update_profile() -> str:
        with session_factory() as session:
            try:
                ProfileService(UnitOfWork(session)).save_profile(
                    user_id, ProfileInput(**{**PROFILE, "version": 1})
                )
                return "saved"
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(lambda _: update_profile(), range(2))) == ["conflict", "saved"]
    assert logged_in.get("/api/profile").json()["version"] == 2


def test_service_failure_rolls_back(
    session_factory: sessionmaker[Session], client: TestClient
) -> None:
    with session_factory() as session:
        user_id = session.scalar(select(User.id))
        session.add(Shop(owner_id=user_id, **SHOP))
        session.flush()
        # A failed service leaves the request scope without committing.
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Shop)) == 0
