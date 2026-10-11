from typing import Any
from uuid import uuid4

from fastapi.testclient import TestClient

from tests.test_analytics import imported
from tests.test_imports import ORDER_HEADER, create_shop
from tests.test_order_reconciliation import BASIS, order, sale
from tests.test_statements import SCOPE, file, withdraw


def root(shop: int) -> str:
    return f"/api/shops/{shop}/order-statement-reviews"


def draft(**changes: Any) -> dict[str, Any]:
    return {
        "scope": SCOPE | BASIS,
        "review_id": None,
        "version": 0,
        "conclusion": {"outcome": "pending", "note": "Synthetic order review"},
        **changes,
    }


def write(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    preview = client.post(root(shop) + "/preview", json=data)
    assert preview.status_code == 200, preview.text
    body = data | {
        "preview_hash": preview.json()["preview_hash"],
        "request_id": str(uuid4()),
        "confirm": True,
    }
    response = client.post(root(shop), json=body)
    assert response.status_code == 200, response.text
    assert client.post(root(shop), json=body).json() == response.json()
    return response.json()


def setup(client: TestClient) -> tuple[int, dict[str, Any]]:
    shop = create_shop(client)
    batch = imported(client, shop, ORDER_HEADER + order(), "orders")
    imported(client, shop, file(sale()), "statements")
    return shop, batch


def test_order_review_versions_domain_isolation_and_clear(logged_in: TestClient) -> None:
    shop, _ = setup(logged_in)
    item = write(logged_in, shop, draft())
    assert item["snapshot"]["result"]["orders"][0]["order_id"] == "O1"
    assert item["snapshot"]["result"]["comparisons"][0]["difference"] == "0.0000"
    assert logged_in.get(f"/api/shops/{shop}/statement-reviews/{item['id']}").status_code == 404
    fee_page = logged_in.get(
        f"/api/shops/{shop}/statement-reviews",
        params={"data_identity": "synthetic", "channel": "generic"},
    )
    assert not fee_page.json()["items"]
    updated = write(logged_in, shop, draft(review_id=item["id"], version=item["version"]))
    assert updated["version"] == 2
    history = logged_in.get(f"{root(shop)}/{item['id']}", params={"version": 1}).json()
    assert history["snapshot"] == item["snapshot"]
    response = logged_in.post(
        f"{root(shop)}/{item['id']}/clear",
        json={"version": updated["version"], "confirm": True, "request_id": str(uuid4())},
    )
    assert response.status_code == 200
    cleared = logged_in.get(f"{root(shop)}/{item['id']}", params={"version": 1}).json()
    assert cleared["snapshot"] is None
    assert all(h["conclusion"] is None for h in cleared["history"])


def test_order_review_source_changes_invalidate_preview_and_saved(logged_in: TestClient) -> None:
    shop, batch = setup(logged_in)
    data = draft()
    preview = logged_in.post(root(shop) + "/preview", json=data).json()
    item = write(logged_in, shop, data)
    withdraw(logged_in, batch, "revoke")
    response = logged_in.post(
        root(shop),
        json=data
        | {"preview_hash": preview["preview_hash"], "request_id": str(uuid4()), "confirm": True},
    )
    assert response.status_code == 409
    saved = logged_in.get(f"{root(shop)}/{item['id']}").json()
    assert saved["status"] == "stale"
    current = logged_in.get(f"{root(shop)}/{item['id']}/current")
    assert current.status_code == 200
    assert current.json()["preview"]["snapshot"]["blockers"]


def test_order_review_refund_pending_blocks_consistent(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in, shop, ORDER_HEADER + order(refund="3", status="partially_refunded"), "orders"
    )
    imported(logged_in, shop, file(sale()), "statements")
    response = logged_in.post(
        root(shop) + "/preview",
        json=draft(conclusion={"outcome": "consistent", "note": "Synthetic review"}),
    )
    assert response.status_code == 422
    pending = write(logged_in, shop, draft())
    assert pending["snapshot"]["blockers"]


def test_order_review_migration_refuses_loss(logged_in: TestClient, settings) -> None:
    import os
    from unittest.mock import patch

    import pytest
    from alembic import command
    from alembic.config import Config

    shop, _ = setup(logged_in)
    item = write(logged_in, shop, draft())
    with patch.dict(os.environ, {"SOLOOPS_DATABASE_URL": settings.database_url.get_secret_value()}):
        config = Config("alembic.ini")
        try:
            with pytest.raises(RuntimeError, match="Order review records"):
                command.downgrade(config, "a31e72d405bf")
        finally:
            command.upgrade(config, "head")
        command.check(config)
    assert logged_in.get(f"{root(shop)}/{item['id']}").json()["snapshot"] == item["snapshot"]
