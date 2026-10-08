from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.time import utc_now
from app.models.imports import InventorySnapshot
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from app.services.profit_calculation import utc_text
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import PRODUCTS, commit, create_shop, preview, upload
from tests.test_support import withdraw

HEADER = "sku,available,snapshot_at,safety_threshold\n"


def csv(available: str = "3", threshold: str = "5", age: int = 1, sku: str = "001") -> str:
    return HEADER + f"{sku},{available},{utc_text(utc_now() - timedelta(hours=age))},{threshold}\n"


def listing(client: TestClient, shop: int, **scope: Any) -> dict[str, Any]:
    response = client.get(
        f"/api/shops/{shop}/inventory", params={"data_identity": "synthetic", **scope}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_optional_inventory_empty_and_source_evidence(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    assert listing(logged_in, shop)["items"] == []
    batch = imported(logged_in, shop, csv(), "inventory")
    result = listing(logged_in, shop)
    item = result["items"][0]
    assert item["status"] == "low" and item["available"] == 3
    assert item["source"]["batch_id"] == batch["id"]
    row = logged_in.get(f"/api/shops/{shop}/analytics/sources/{item['source']['row_id']}").json()
    assert row["raw"]["available"] == "3"
    assert row["normalized"]["safety_threshold"] == 5
    assert result["scope"]["max_age_hours"] == 24
    assert listing(logged_in, shop, data_identity="user_import")["items"] == []
    assert listing(logged_in, create_shop(logged_in, "second"))["items"] == []


def test_freshness_boundary_threshold_and_zero(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv("0", "0"), "inventory")
    item = listing(logged_in, shop)["items"][0]
    assert item["status"] == "above_threshold"  # Strictly below, not <=.
    expiry = datetime.fromisoformat(item["valid_until"]).replace(tzinfo=None)
    with patch("app.services.inventory.utc_now", return_value=expiry):
        expired = listing(logged_in, shop)["items"][0]
    assert expired["status"] == "unknown" and expired["available"] == 0
    with patch("app.services.inventory.utc_now", return_value=expiry - timedelta(microseconds=1)):
        assert listing(logged_in, shop)["items"][0]["status"] == "above_threshold"
    imported(logged_in, shop, csv("1", "2", age=30), "inventory")
    assert listing(logged_in, shop)["items"][0]["status"] == "unknown"
    assert listing(logged_in, shop, max_age_hours=48)["items"][0]["status"] == "low"


@pytest.mark.parametrize(
    ("available", "threshold", "age"),
    [
        ("-1", "5", 1),
        ("1.2", "5", 1),
        ("", "5", 1),
        ("2", "", 1),
        ("2", "-1", 1),
        ("1000000001", "5", 1),
        ("2", "5", -24),
    ],
)
def test_invalid_inventory_never_writes(
    logged_in: TestClient, available: str, threshold: str, age: int
) -> None:
    shop = create_shop(logged_in)
    batch = preview(logged_in, upload(logged_in, shop, csv(available, threshold, age), "inventory"))
    assert batch["error_rows"] == 1
    assert (
        logged_in.post(
            f"/api/imports/{batch['id']}/commit", json={"version": batch["version"]}
        ).status_code
        == 409
    )
    assert not listing(logged_in, shop)["items"]


def test_updates_duplicate_revoke_and_clear(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    a = imported(logged_in, shop, csv(), "inventory")
    incoming = preview(logged_in, upload(logged_in, shop, csv("8", age=48), "inventory"))
    assert incoming["updated_rows"] == 1
    assert any("更旧" in text for text in incoming["rows"][0]["warnings"])
    assert (
        logged_in.post(
            f"/api/imports/{incoming['id']}/commit", json={"version": incoming["version"]}
        ).status_code
        == 409
    )
    b = commit(logged_in, incoming, True)
    assert commit(logged_in, b)["id"] == b["id"]
    assert listing(logged_in, shop)["items"][0]["available"] == 8
    with session_factory() as session:
        assert session.scalar(select(func.count(InventorySnapshot.id))) == 1
    withdraw(logged_in, b, "revoke")
    restored = listing(logged_in, shop)["items"][0]
    assert restored["available"] == 3 and restored["source"]["batch_id"] == a["id"]
    withdraw(logged_in, a, "clear")
    assert not listing(logged_in, shop)["items"]
    assert (
        logged_in.get(
            f"/api/shops/{shop}/analytics/sources/{restored['source']['row_id']}"
        ).status_code
        == 404
    )


def test_revoke_out_of_order_and_channel_isolation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    a = imported(logged_in, shop, csv(), "inventory")
    b = imported(logged_in, shop, csv("8"), "inventory")
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "other.csv",
            "kind": "inventory",
            "source_channel": "amazon",
            "data_identity": "synthetic",
            "timezone": "UTC",
        },
        content=csv("17"),
    )
    assert response.status_code == 201
    commit(logged_in, preview(logged_in, response.json()))
    withdraw(logged_in, a, "revoke")
    withdraw(logged_in, b, "revoke")
    assert not listing(logged_in, shop)["items"]
    assert listing(logged_in, shop, channel="amazon")["items"][0]["available"] == 17


def test_excel_correction_timezone_and_duplicate_key(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    book = Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["sku", "available", "snapshot_at", "safety_threshold"])
    sheet.append(["001", -1, "2026-01-01 08:30:00", 2])
    data = BytesIO()
    book.save(data)
    book.close()
    batch = preview(logged_in, upload(logged_in, shop, data.getvalue(), "inventory", "stock.xlsx"))
    assert batch["error_rows"] == 1
    batch = preview(logged_in, batch, corrections={"2": {"available": "1"}})
    assert batch["error_rows"] == 0
    assert (
        datetime.fromisoformat(batch["coverage_start"]).isoformat() == "2026-01-01T00:30:00+00:00"
    )
    commit(logged_in, batch)
    assert listing(logged_in, shop)["items"][0]["status"] == "unknown"
    contents = csv()
    duplicate = preview(
        logged_in, upload(logged_in, shop, contents + contents.splitlines()[1], "inventory")
    )
    assert duplicate["error_rows"] == 2


def test_bounded_search_and_query_validation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    stamp = utc_text(utc_now() - timedelta(hours=1))
    imported(
        logged_in, shop, HEADER + "".join(f"S{i:03},1,{stamp},2\n" for i in range(51)), "inventory"
    )
    first = listing(logged_in, shop)
    second = listing(logged_in, shop, offset=50)
    assert len(first["items"]) == 50 and first["has_more"]
    assert len(second["items"]) == 1 and not second["has_more"]
    assert listing(logged_in, shop, search="S050")["items"][0]["sku"] == "S050"
    assert not listing(logged_in, shop, search="%")["items"]
    for scope in (
        {"max_age_hours": 0},
        {"max_age_hours": 721},
        {"offset": -1},
        {"channel": "invalid"},
    ):
        assert logged_in.get(f"/api/shops/{shop}/inventory", params=scope).status_code == 422
    template = logged_in.get("/api/imports/templates/inventory")
    assert "safety_threshold" in template.text
    assert logged_in.get(f"/api/shops/{shop + 1000}/inventory").status_code == 404


def test_other_owner_cannot_read_inventory_or_source(
    logged_in: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv(), "inventory")
    row_id = listing(logged_in, shop)["items"][0]["source"]["row_id"]
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="outsider", password=TEST_PASSWORD)
        )
    logged_in.post("/api/auth/logout")
    auth = logged_in.post(
        "/api/auth/login", json={"username": "outsider", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = auth.json()["csrf_token"]
    assert logged_in.get(f"/api/shops/{shop}/inventory").status_code == 404
    assert logged_in.get(f"/api/shops/{shop}/analytics/sources/{row_id}").status_code == 404
