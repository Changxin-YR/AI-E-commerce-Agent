from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError, ConflictError
from app.core.security import verify_password
from app.models.identity import Shop
from app.models.imports import ImportBatch, Product
from app.models.support import SupportPolicy
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput, ShopInput
from app.services.auth import AuthService
from app.services.demo import DEMO_PASSWORD, DEMO_USERNAME, DemoService
from app.services.profile import ProfileService
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import calculate
from tests.test_listings import decide, generate
from tests.test_operations import run, tasks
from tests.test_support import generate as generate_reply


def demo_settings(settings: Settings) -> Settings:
    return settings.model_copy(update={"demo_enabled": True})


def test_demo_requires_explicit_mode_and_keeps_regular_password_rules(
    settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with (
        session_factory() as session,
        pytest.raises(BusinessError, match="SOLOOPS_DEMO_ENABLED"),
    ):
        DemoService(
            UnitOfWork(session), settings.model_copy(update={"demo_enabled": False})
        ).setup()
    with pytest.raises(ValidationError):
        AccountInput(username=DEMO_USERNAME, password=DEMO_PASSWORD)


def test_demo_is_idempotent_and_preserves_edits(
    settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        uow = UnitOfWork(session)
        service = DemoService(uow, demo_settings(settings))
        first = service.setup()
        assert first.imported_rows == {"products": 6, "orders": 24, "inventory": 6, "messages": 3}
        product = session.scalar(select(Product).where(Product.shop_id == first.shop_id))
        assert product is not None
        product.name = "Seller edited this title"
        uow.commit()
        second = service.setup()
        assert (second.user_id, second.shop_id) == (first.user_id, first.shop_id)
        assert not second.imported_rows
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 4
        assert session.scalar(select(func.count()).select_from(SupportPolicy)) == 3
        session.refresh(product)
        assert product.name == "Seller edited this title"
        user = uow.identity.find_user(DEMO_USERNAME)
        assert user is not None and verify_password(DEMO_PASSWORD, user.password_hash)


def test_existing_admin_requires_explicit_adoption_and_preserves_its_shop(
    settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        uow = UnitOfWork(session)
        owner = AuthService(uow, settings).create_account(
            AccountInput(username=DEMO_USERNAME, password=TEST_PASSWORD)
        )
        original = ProfileService(uow).create_shop(
            owner,
            ShopInput(
                code="my-shop",
                name="已有店铺",
                platform="manual",
                market="GB",
                currency="GBP",
                timezone="Europe/London",
            ),
        )
        service = DemoService(uow, demo_settings(settings))
        with pytest.raises(ConflictError, match="admin 已存在"):
            service.setup()
        session.rollback()
        user = uow.identity.find_user(DEMO_USERNAME)
        assert user is not None and verify_password(TEST_PASSWORD, user.password_hash)
        result = service.setup(adopt_existing_admin=True)
        assert result.user_id == owner
        assert result.shop_id != original.id
        preserved = uow.identity.get_shop(owner, original.id)
        assert preserved is not None and preserved.currency == "GBP"
        assert preserved.data_revision == 0
        assert verify_password(DEMO_PASSWORD, user.password_hash)


def test_unmarked_demo_shop_is_not_modified(
    settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        uow = UnitOfWork(session)
        owner = AuthService(uow, settings).create_account(
            AccountInput(username=DEMO_USERNAME, password=TEST_PASSWORD)
        )
        ProfileService(uow).create_shop(
            owner,
            ShopInput(
                code="demo-shop",
                name="User-owned shop",
                platform="manual",
                market="US",
                currency="USD",
                timezone="Asia/Shanghai",
            ),
        )
        with pytest.raises(ConflictError, match="demo-shop 已存在"):
            DemoService(uow, demo_settings(settings)).setup(adopt_existing_admin=True)
        session.rollback()
        user = uow.identity.find_user(DEMO_USERNAME)
        assert user is not None and verify_password(TEST_PASSWORD, user.password_hash)
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 0
        assert session.scalar(select(func.count()).select_from(Shop)) == 1


def test_demo_login_and_four_real_business_workflows(
    client: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    with session_factory() as session:
        result = DemoService(UnitOfWork(session), demo_settings(settings)).setup()
    login = client.post("/api/auth/login", json={"username": "admin", "password": "qwer123"})
    assert login.status_code == 200, login.text
    client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    shop = result.shop_id
    now = datetime.now(UTC)
    scope = {
        "start_at": (now - timedelta(days=15)).isoformat(),
        "end_at": (now + timedelta(days=1)).isoformat(),
    }
    analysis = calculate(client, shop, **scope)
    assert analysis["summary"]["line_count"] == 24
    assert Decimal(analysis["summary"]["sales"]) > 0

    products = client.get(f"/api/shops/{shop}/listings/products").json()
    assert len(products) == 6
    listing = generate(client, shop, products[0])
    approved = decide(client, shop, listing)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    messages = client.get(f"/api/shops/{shop}/support/messages").json()
    faq = next(message for message in messages if message["message_id"] == "DEMO-MESSAGE-002")
    workspace = client.get(f"/api/shops/{shop}/support/messages/{faq['id']}").json()
    reply = generate_reply(
        client, shop, faq["id"], policies=[p["id"] for p in workspace["policies"]]
    )
    assert reply["snapshot"]["reply"]
    assert not reply["snapshot"]["reasons"]

    operation = run(client, shop, **scope)
    assert operation["snapshot"]["created_candidates"] > 0
    kinds = {item["kind"] for item in tasks(client, shop)}
    assert {"low_inventory", "low_margin", "order_review", "message_review"} <= kinds
