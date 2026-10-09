from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError
from app.models.identity import AuditEvent, User
from app.models.imports import Product
from app.models.product_quality import ProductQualityReport, ProductQualitySource
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.product_quality import QualitySave
from app.services.auth import AuthService
from app.services.product_quality import ProductQualityService
from app.services.product_quality_rules import assess
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import PRODUCTS, commit, create_shop, preview

HEADER = "sku,name,facts,price,currency,unit_cost,cost_currency\n"
ROWS = HEADER + 'A,Cup,"Color: red\nColor: blue\nColor: red",0,USD,1,EUR\na,TBD,,,,,\n'


def root(shop: int) -> str:
    return f"/api/shops/{shop}/product-quality"


def check(client: TestClient, shop: int, **extra: Any) -> dict[str, Any]:
    response = client.post(f"{root(shop)}/preview", json={"data_identity": "synthetic", **extra})
    assert response.status_code == 200, response.text
    return response.json()


def save_input(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "scope": result["scope"],
        "request_id": str(uuid4()),
        "confirm": True,
        "expected_revision": result["source_revision"],
        "expected_preview_hash": result["preview_hash"],
    }


def save(client: TestClient, shop: int, result: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"{root(shop)}/reports", json=save_input(result))
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("values", "codes"),
    [
        ({"name": " ", "facts": ""}, {"name_missing", "facts_missing"}),
        ({"facts": "N/A"}, {"facts_placeholder"}),
        ({"name": "１００％ guaranteed Cup"}, {"name_claim"}),
        ({"facts": "零风险\n永久有效"}, {"facts_claim"}),
        ({"facts": "Size: M\nＳｉｚｅ： M\nsize: L"}, {"facts_duplicate", "facts_conflict"}),
        ({"facts": "size: M\ncolor: Red", "unit_cost": Decimal(0)}, set()),
    ],
)
def test_local_rules_are_evidence_checks(values: dict[str, Any], codes: set[str]) -> None:
    product = Product(
        **(
            {
                "sku": "A",
                "name": "Cup",
                "facts": "Steel",
                "price": Decimal("12.3456"),
                "currency": "USD",
                "unit_cost": Decimal(1),
                "cost_currency": "USD",
            }
            | values
        )
    )
    assert {i.code for i in assess(product, 0)} == codes


def test_preview_issues_decimal_coverage_and_original_evidence(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, ROWS, "products")
    result = check(logged_in, shop)
    assert result["product_count"] == result["affected_products"] == 2
    assert result["missing_count"] == 3
    assert result["review_count"] == 7
    first, second = result["products"]
    assert first["similar_skus"] == ["a"] and second["similar_skus"] == ["A"]
    assert {i["code"] for i in first["issues"]} == {
        "facts_duplicate",
        "facts_conflict",
        "price_zero",
        "cost_currency_mismatch",
        "similar_sku",
    }
    ref = first["source"]
    assert ref["batch_id"] == batch["id"]
    raw = logged_in.get(f"/api/shops/{shop}/analytics/sources/{ref['row_id']}").json()
    assert raw["raw"]["facts"] == "Color: red\nColor: blue\nColor: red"
    excluded = {r["code"] for r in result["coverage"] if r["status"] == "not_checked"}
    assert excluded == {"brand_codes", "media", "category", "platform"}
    assert check(logged_in, shop)["preview_hash"] == result["preview_hash"]
    assert Decimal(first["price"]) == 0 and second["price"] is None


def test_scope_identity_channel_prefix_and_current_projection(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in, shop, HEADER + "A%,Cup,Steel,1,USD,0,USD\nAX,Cup,Steel,1,USD,0,USD\n", "products"
    )
    assert [p["sku"] for p in check(logged_in, shop, sku_prefix="A%")["products"]] == ["A%"]
    assert check(logged_in, shop, sku_prefix="a")["product_count"] == 0
    assert check(logged_in, shop, channel="amazon")["product_count"] == 0
    empty = check(logged_in, shop, data_identity="user_import")
    assert not empty["products"] and all(c["status"] == "not_checked" for c in empty["coverage"])
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic-quality.csv",
            "kind": "products",
            "source_channel": "amazon",
            "data_identity": "user_import",
            "timezone": "Asia/Shanghai",
        },
        content=(HEADER + "AX,Updated,Steel,12.3456,USD,0,USD\n").encode(),
    )
    assert response.status_code == 201
    commit(logged_in, preview(logged_in, response.json()), allow_updates=True)
    assert check(logged_in, shop)["product_count"] == 1
    actual = check(logged_in, shop, channel="amazon", data_identity="user_import")
    assert actual["products"][0]["price"] == "12.3456"
    assert actual["products"][0]["issues"] == []


def test_save_replay_confirmation_and_preview_tampering(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    result = check(logged_in, shop)
    body = save_input(result)
    for invalid in [{"confirm": False}, {"snapshot": result}, {"expected_preview_hash": "invalid"}]:
        assert logged_in.post(f"{root(shop)}/reports", json=body | invalid).status_code == 422
    assert (
        logged_in.post(
            f"{root(shop)}/reports", json=body | {"expected_preview_hash": "0" * 64}
        ).status_code
        == 409
    )
    record = logged_in.post(f"{root(shop)}/reports", json=body).json()
    replay = logged_in.post(f"{root(shop)}/reports", json=body).json()
    assert replay == record
    assert (
        logged_in.post(f"{root(shop)}/reports", json=body | {"expected_revision": 999}).status_code
        == 409
    )
    assert logged_in.get(f"{root(shop)}/reports/{record['id']}").json() == record
    assert logged_in.get(f"{root(shop)}/reports").json()["items"][0]["snapshot"] is None


def test_import_change_rejects_old_preview_and_never_revives_history(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    initial = check(logged_in, shop)
    record = save(logged_in, shop, initial)
    replacement = imported(logged_in, shop, PRODUCTS.replace("Steel", "Glass"), "products")
    assert logged_in.post(f"{root(shop)}/reports", json=save_input(initial)).status_code == 409
    assert logged_in.get(f"{root(shop)}/reports/{record['id']}").json()["status"] == "stale"
    assert (
        logged_in.post(
            f"/api/imports/{replacement['id']}/revoke", json={"version": replacement["version"]}
        ).status_code
        == 200
    )
    assert logged_in.get(f"{root(shop)}/reports/{record['id']}").json()["status"] == "stale"
    assert check(logged_in, shop)["products"][0]["facts"] == "Steel"


def test_all_source_dependencies_purge_report_and_sku_prefix(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    first = imported(logged_in, shop, PRODUCTS, "products")
    second = imported(logged_in, shop, PRODUCTS.replace("001", "002"), "products")
    record = save(logged_in, shop, check(logged_in, shop, sku_prefix="00"))
    independent = save(logged_in, shop, check(logged_in, shop, sku_prefix="002"))
    assert (
        logged_in.post(
            f"/api/imports/{first['id']}/clear", json={"version": first["version"]}
        ).status_code
        == 200
    )
    cleared = logged_in.get(f"{root(shop)}/reports/{record['id']}").json()
    assert (
        cleared["status"] == "cleared"
        and cleared["snapshot"] is None
        and cleared["scope"]["sku_prefix"] == ""
    )
    assert logged_in.get(f"{root(shop)}/reports/{independent['id']}").json()["snapshot"] is not None
    with session_factory() as session:
        assert not session.scalars(
            select(ProductQualitySource).where(ProductQualitySource.report_id == record["id"])
        ).all()
        assert (
            session.scalar(
                select(ProductQualitySource.batch_id).where(
                    ProductQualitySource.report_id == independent["id"]
                )
            )
            == second["id"]
        )


def test_manual_clear_is_idempotent_and_replay_does_not_restore(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    body = save_input(check(logged_in, shop, sku_prefix="001"))
    record = logged_in.post(f"{root(shop)}/reports", json=body).json()
    url = f"{root(shop)}/reports/{record['id']}/clear"
    assert logged_in.post(url, json={"confirm": False}).status_code == 422
    for _ in range(2):
        assert logged_in.post(url, json={"confirm": True}).json()["snapshot"] is None
    replay = logged_in.post(f"{root(shop)}/reports", json=body).json()
    assert replay["status"] == "cleared" and replay["scope"]["sku_prefix"] == ""
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "product_quality.cleared")
            )
            == 1
        )


def test_cross_shop_cross_owner_and_csrf(
    logged_in: TestClient, settings: Settings, session_factory: sessionmaker[Session]
) -> None:
    shop, other = create_shop(logged_in), create_shop(logged_in, "other")
    record = save(logged_in, shop, check(logged_in, shop))
    assert logged_in.get(f"{root(other)}/reports/{record['id']}").status_code == 404
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert logged_in.post(f"{root(shop)}/preview", json={}).status_code == 404
    assert logged_in.get(f"{root(shop)}/reports").status_code == 404
    assert logged_in.get(f"{root(shop)}/reports/{record['id']}").status_code == 404
    assert (
        logged_in.post(
            f"{root(shop)}/reports/{record['id']}/clear", json={"confirm": True}
        ).status_code
        == 404
    )
    del logged_in.headers["X-CSRF-Token"]
    assert logged_in.post(f"{root(shop)}/preview", json={}).status_code == 403


def test_bounded_report_rejects_instead_of_truncating(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in,
        shop,
        HEADER + "".join(f"Q{i:04},Cup,Steel,1,USD,0,USD\n" for i in range(1001)),
        "products",
    )
    assert (
        logged_in.post(f"{root(shop)}/preview", json={"data_identity": "synthetic"}).status_code
        == 422
    )
    assert check(logged_in, shop, sku_prefix="Q00")["product_count"] == 100
    with patch("app.services.product_quality.MAX_REPORT_BYTES", 100):
        assert (
            logged_in.post(
                f"{root(shop)}/preview", json={"data_identity": "synthetic", "sku_prefix": "Q000"}
            ).status_code
            == 422
        )


def test_history_cursor_has_no_snapshot_and_no_overlap(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    result = check(logged_in, shop)
    for _ in range(21):
        save(logged_in, shop, result)
    first = logged_in.get(f"{root(shop)}/reports").json()
    second = logged_in.get(f"{root(shop)}/reports", params={"before": first["next_cursor"]}).json()
    assert len(first["items"]) == 20 and len(second["items"]) == 1
    assert all(item["snapshot"] is None for item in first["items"])
    assert first["items"][-1]["id"] > second["items"][0]["id"]


def test_concurrent_save_has_one_report_and_audit(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    data = QualitySave.model_validate(save_input(check(logged_in, shop)))
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
    assert owner is not None
    barrier = Barrier(2)

    def worker() -> int:
        with session_factory() as session:
            barrier.wait(timeout=10)
            return ProductQualityService(UnitOfWork(session)).save(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        first, second = pool.submit(worker), pool.submit(worker)
        assert first.result(timeout=20) == second.result(timeout=20)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductQualityReport)) == 1
        assert session.scalar(select(func.count()).select_from(ProductQualitySource)) == 1
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.action == "product_quality.saved")
            )
            == 1
        )


def test_save_audit_failure_rolls_back_report_and_sources(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    data = QualitySave.model_validate(save_input(check(logged_in, shop)))
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
        with (
            patch.object(
                UnitOfWork, "record_event", side_effect=BusinessError("test", "合成失败", 500)
            ),
            pytest.raises(BusinessError),
        ):
            ProductQualityService(UnitOfWork(session)).save(owner, shop, data)
        session.rollback()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductQualityReport)) == 0
        assert session.scalar(select(func.count()).select_from(ProductQualitySource)) == 0
