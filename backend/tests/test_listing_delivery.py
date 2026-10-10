import csv
import io
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.imports import Product
from app.models.listings import ListingVersion
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from app.services.manual_delivery import delivery_csv
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import PRODUCTS, create_shop
from tests.test_listings import decide, generate, revise, root, setup


def deliver(client: TestClient, shop: int, item: dict[str, Any]) -> Any:
    return client.get(
        f"{root(shop)}/versions/{item['id']}/delivery",
        params={"expected_version": item["version"]},
    )


def test_approved_delivery_roundtrip_and_metadata(logged_in: TestClient) -> None:
    text = 'sku,name,facts\nCN-01,合成杯 Cup,"材质: Steel\n说明: 双引号 ""原文"", English"\n'
    shop, batch, product = setup(logged_in, text)
    draft = generate(logged_in, shop, product)
    edited = revise(logged_in, shop, draft, draft["snapshot"]["proposed"])
    approved = decide(logged_in, shop, edited).json()
    response = deliver(logged_in, shop, approved)
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["content"] == approved["snapshot"]["proposed"]
    assert result["shop_id"] == shop and result["market"] == "US"
    assert result["sku"] == "CN-01" and result["number"] == 2
    assert result["source"] == product["source"]
    assert result["source_batch_ids"] == [batch["id"]]
    assert "GTIN、认证" in result["missing"][-1]
    assert result["csv_text"].startswith("\ufeff")
    rows = list(csv.reader(io.StringIO(result["csv_text"].lstrip("\ufeff"))))
    assert len(rows) == 2 and len(rows[0]) == len(rows[1])
    cells = dict(zip(rows[0], (cell[1:] for cell in rows[1]), strict=True))
    assert cells["标题"] == result["content"]["title"]
    assert cells["说明"] == result["content"]["description"]
    assert result["content"]["description"] in result["plain_text"]
    assert result["filename"] == f"listing-{approved['id']}-v2.csv"
    reread = logged_in.get(f"{root(shop)}/versions/{approved['id']}").json()
    assert reread == approved and reread["external_status"] == "not_submitted"


@pytest.mark.parametrize(
    "payload",
    [
        "=1+1",
        "+cmd",
        "-1",
        "@SUM(1)",
        "\t=1",
        "\r=1",
        "\n=1",
        "＝1",
        "＋1",
        "－1",
        "＠SUM(1)",
        '",=1\nnext,"',
    ],
)
def test_every_csv_cell_remains_literal(payload: str) -> None:
    rows = list(csv.reader(io.StringIO(delivery_csv([("title", payload)])[1:])))
    assert rows == [["title"], ["'" + payload]]


def test_unapproved_old_version_and_replaced_approval_blocked(logged_in: TestClient) -> None:
    shop, _, product = setup(logged_in)
    draft = generate(logged_in, shop, product)
    assert deliver(logged_in, shop, draft).status_code == 409
    approved = decide(logged_in, shop, draft).json()
    assert deliver(logged_in, shop, draft).status_code == 409
    newer = revise(logged_in, shop, approved, approved["snapshot"]["proposed"], approved["id"])
    assert decide(logged_in, shop, newer).status_code == 200
    assert deliver(logged_in, shop, approved).status_code == 409
    refreshed = logged_in.get(f"{root(shop)}/versions/{approved['id']}").json()
    assert deliver(logged_in, shop, refreshed).status_code == 409


@pytest.mark.parametrize("change", ["update", "revoke", "clear", "facts", "active"])
def test_delivery_rechecks_current_source_and_active(
    logged_in: TestClient, session_factory: sessionmaker[Session], change: str
) -> None:
    shop, batch, product = setup(logged_in)
    approved = decide(logged_in, shop, generate(logged_in, shop, product)).json()
    if change == "update":
        imported(logged_in, shop, PRODUCTS.replace("Steel", "Wood"), "products")
    elif change in {"revoke", "clear"}:
        revoked = logged_in.post(
            f"/api/imports/{batch['id']}/revoke", json={"version": batch["version"]}
        ).json()
        if change == "clear":
            assert (
                logged_in.post(
                    f"/api/imports/{batch['id']}/clear", json={"version": revoked["version"]}
                ).status_code
                == 200
            )
    else:
        with session_factory() as session:
            if change == "facts":
                row = session.get(Product, product["product_id"])
                assert row
                row.facts = "Changed outside snapshot"
            else:
                row_version = session.get(ListingVersion, approved["id"])
                assert row_version
                row_version.product_key = "unmatched"
            session.commit()
    response = deliver(logged_in, shop, approved)
    # A changed key cannot be represented as the same product's current approval.
    if change == "active":
        assert response.status_code == 409
    else:
        assert response.status_code in {404, 409}
    assert "plain_text" not in response.json()


def test_delivery_scope_isolation(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop, _, product = setup(logged_in)
    approved = decide(logged_in, shop, generate(logged_in, shop, product)).json()
    other = create_shop(logged_in, "other")
    assert deliver(logged_in, other, approved).status_code == 404
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other", password=TEST_PASSWORD)
        )
    logged_in.post("/api/auth/login", json={"username": "other", "password": TEST_PASSWORD})
    response = deliver(logged_in, shop, approved)
    assert response.status_code == 404
    assert "Test Cup" not in response.text
