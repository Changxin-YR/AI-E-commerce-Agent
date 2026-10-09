from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.identity import User
from app.models.imports import ImportBatch, ImportRow
from app.models.product_edits import ProductEdit, ProductEditSource
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.product_edits import EditCreate, EditDecision
from app.services.product_edits import ProductEditService
from tests.test_analytics import imported
from tests.test_imports import PRODUCTS, commit, create_shop, preview
from tests.test_product_quality import check, save

HEADER = "sku,name,facts,price,currency,unit_cost,cost_currency\n"
TWO = HEADER + "A,Cup,Steel,12.3456,USD,0,USD\nB,Plate,Round,,,,\n"


def root(shop: int) -> str:
    return f"/api/shops/{shop}/product-edits"


def body(client: TestClient, shop: int, suffix: str = " revised") -> dict[str, Any]:
    return {
        "data_identity": "synthetic",
        "channel": "generic",
        "reason": "核对合成商品规格",
        "request_id": str(uuid4()),
        "changes": [
            {
                "product_id": p["product_id"],
                "expected_source_row_id": p["source"]["row_id"],
                "name": p["name"] + suffix,
                "facts": p["facts"] + "\nColor: Red",
            }
            for p in check(client, shop)["products"]
        ],
    }


def draft(client: TestClient, shop: int, **extra: Any) -> dict[str, Any]:
    response = client.post(root(shop), json=body(client, shop) | extra)
    assert response.status_code == 201, response.text
    return response.json()


def decision(edit: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": edit["version"],
        "confirm": True,
        "expected_preview_hash": edit["preview_hash"],
    }


def approve(client: TestClient, shop: int, edit: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"{root(shop)}/{edit['id']}/approve", json=decision(edit))
    assert response.status_code == 200, response.text
    return response.json()


def control(client: TestClient, shop: int, edit: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"{root(shop)}/{edit['id']}/{action}", json={"version": edit["version"], "confirm": True}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_draft_diff_approve_provenance_money_and_replay(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    original = imported(logged_in, shop, TWO, "products")
    initial = check(logged_in, shop)
    data = body(logged_in, shop)
    created = logged_in.post(root(shop), json=data).json()
    assert created["status"] == "draft" and created["output_batch_id"] is None
    assert check(logged_in, shop)["products"] == initial["products"]
    applied = approve(logged_in, shop, created)
    assert applied["status"] == "applied" and applied["current_count"] == 2
    assert applied == approve(logged_in, shop, created)
    assert logged_in.post(root(shop), json=data).json() == applied
    current = check(logged_in, shop)["products"]
    assert current[0]["price"] == "12.3456" and current[0]["unit_cost"] == "0.0000"
    assert current[1]["price"] is None
    assert all(p["source"]["batch_id"] == applied["output_batch_id"] for p in current)
    assert current[0]["source"]["row_id"] != initial["products"][0]["source"]["row_id"]
    assert current[0]["source"]["filename"] == f"人工商品修订 #{created['id']}"
    row = logged_in.get(
        f"/api/shops/{shop}/analytics/sources/{current[0]['source']['row_id']}"
    ).json()
    assert row["raw"]["依据批次"] == str(original["id"])
    assert row["raw"]["修订理由"] == data["reason"]
    assert (
        logged_in.get(f"/api/imports/{original['id']}").json()["rows"][0]["normalized"]["name"]
        == "Cup"
    )


@pytest.mark.parametrize("change", [{"confirm": False}, {"version": 0}, {"extra": "injected"}])
def test_confirmation_schema(logged_in: TestClient, change: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    response = logged_in.post(f"{root(shop)}/{edit['id']}/approve", json=decision(edit) | change)
    assert response.status_code == 422
    assert check(logged_in, shop)["products"][0]["name"] == "Test Cup"


def test_invalid_change_scope_hash_and_request_binding(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    data = body(logged_in, shop)
    change = data["changes"][0]
    for changes in [
        [],
        [change] * 51,
        [change] * 2,
        [change | {"name": " "}],
        [change | {"price": "1"}],
        [change | {"facts": "x" * 2001}],
    ]:
        assert logged_in.post(root(shop), json=data | {"changes": changes}).status_code == 422
    for extra in [
        {"channel": "amazon"},
        {"data_identity": "user_import"},
        {"changes": [change | {"expected_source_row_id": 999999}]},
    ]:
        assert logged_in.post(root(shop), json=data | extra).status_code == 409
    edit = logged_in.post(root(shop), json=data).json()
    assert logged_in.post(root(shop), json=data | {"reason": "changed"}).status_code == 409
    assert (
        logged_in.post(
            f"{root(shop)}/{edit['id']}/approve",
            json=decision(edit) | {"expected_preview_hash": "0" * 64},
        ).status_code
        == 409
    )


def test_atomic_conflict_records_per_item_and_new_draft_can_retry(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, TWO, "products")
    edit = draft(logged_in, shop)
    imported(logged_in, shop, HEADER + "A,New Cup,New material,13,USD,1,USD\n", "products")
    failed = approve(logged_in, shop, edit)
    assert failed["status"] == "failed" and failed["output_batch_id"] is None
    assert [i["result"] for i in failed["snapshot"]["items"]] == ["conflict", "blocked"]
    assert [p["name"] for p in check(logged_in, shop)["products"]] == ["New Cup", "Plate"]
    assert logged_in.get(f"{root(shop)}/{edit['id']}").json() == failed
    assert approve(logged_in, shop, draft(logged_in, shop))["current_count"] == 2


def test_store_revision_change_blocks_old_approval(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    imported(logged_in, shop, HEADER + "Z,Other,Wood,,,,\n", "products")
    result = approve(logged_in, shop, edit)
    assert result["status"] == "failed"
    assert result["snapshot"]["items"][0]["result"] == "blocked"


def test_withdraw_restores_active_source_without_reviving_rejected_ancestor(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    origin = imported(logged_in, shop, PRODUCTS, "products")
    first = approve(logged_in, shop, draft(logged_in, shop))
    second = approve(logged_in, shop, draft(logged_in, shop))
    revoked = control(logged_in, shop, second, "withdraw")
    assert revoked["status"] == "revoked" and revoked["current_count"] == 0
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == first["output_batch_id"]
    control(logged_in, shop, first, "withdraw")
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == origin["id"]


def test_source_revoke_cascades_all_descendants_and_pending_drafts(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    origin = imported(logged_in, shop, TWO, "products")
    first = approve(logged_in, shop, draft(logged_in, shop))
    second = approve(logged_in, shop, draft(logged_in, shop))
    pending = draft(logged_in, shop)
    response = logged_in.post(
        f"/api/imports/{origin['id']}/revoke", json={"version": origin["version"]}
    )
    assert response.status_code == 200, response.text
    assert check(logged_in, shop)["products"] == []
    for edit in [first, second]:
        assert logged_in.get(f"{root(shop)}/{edit['id']}").json()["status"] == "revoked"
    assert logged_in.get(f"{root(shop)}/{pending['id']}").json()["status"] == "stale"
    assert (
        logged_in.post(f"{root(shop)}/{pending['id']}/approve", json=decision(pending)).status_code
        == 409
    )


def test_purge_full_chain_reports_and_replay_preserves_independent(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    origin = imported(logged_in, shop, PRODUCTS, "products")
    data = body(logged_in, shop)
    first = approve(logged_in, shop, logged_in.post(root(shop), json=data).json())
    second = approve(logged_in, shop, draft(logged_in, shop))
    pending = draft(logged_in, shop)
    report = save(logged_in, shop, check(logged_in, shop))
    independent_batch = imported(
        logged_in, shop, HEADER + "001,Independent,Blue,2,USD,1,USD\n", "products"
    )
    independent = draft(logged_in, shop)
    response = logged_in.post(
        f"/api/imports/{origin['id']}/clear", json={"version": origin["version"]}
    )
    assert response.status_code == 200, response.text
    for edit in [first, second, pending]:
        cleared = logged_in.get(f"{root(shop)}/{edit['id']}").json()
        assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert logged_in.post(root(shop), json=data).json()["snapshot"] is None
    assert (
        logged_in.get(f"/api/shops/{shop}/product-quality/reports/{report['id']}").json()[
            "snapshot"
        ]
        is None
    )
    assert logged_in.get(f"{root(shop)}/{independent['id']}").json()["status"] == "draft"
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == independent_batch["id"]
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ImportRow)
                .where(
                    ImportRow.batch_id.in_(
                        [origin["id"], first["output_batch_id"], second["output_batch_id"]]
                    )
                )
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ProductEditSource)
                .where(ProductEditSource.edit_id.in_([first["id"], second["id"], pending["id"]]))
            )
            == 0
        )


def test_direct_manual_batch_clear_and_later_file_revoke_do_not_revive(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    original = imported(logged_in, shop, PRODUCTS, "products")
    edit = approve(logged_in, shop, draft(logged_in, shop))
    later = imported(logged_in, shop, PRODUCTS.replace("Test Cup", "Newest"), "products")
    batch = logged_in.get(f"/api/imports/{edit['output_batch_id']}").json()
    assert (
        logged_in.post(
            f"/api/imports/{batch['id']}/clear", json={"version": batch["version"]}
        ).status_code
        == 200
    )
    assert logged_in.get(f"{root(shop)}/{edit['id']}").json()["snapshot"] is None
    assert (
        logged_in.post(
            f"/api/imports/{later['id']}/revoke", json={"version": later["version"]}
        ).status_code
        == 200
    )
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == original["id"]


def test_reject_clear_and_controls_version(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    assert (
        logged_in.post(
            f"{root(shop)}/{edit['id']}/clear", json={"confirm": True, "version": 999}
        ).status_code
        == 409
    )
    rejected = control(logged_in, shop, edit, "reject")
    assert rejected["status"] == "rejected"
    assert control(logged_in, shop, edit, "reject") == rejected
    assert (
        logged_in.post(f"{root(shop)}/{edit['id']}/approve", json=decision(edit)).status_code == 409
    )
    cleared = control(logged_in, shop, rejected, "clear")
    assert cleared["snapshot"] is None and cleared["status"] == "cleared"


def test_approval_audit_failure_rolls_back_all_business_rows(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    original = imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    record = UnitOfWork.record_event

    def fail(self: UnitOfWork, actor: int, action: str, *args: Any, **kwargs: Any) -> None:
        if action == "product_edit.applied":
            raise RuntimeError("synthetic audit failure")
        record(self, actor, action, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", fail), pytest.raises(RuntimeError):
        approve(logged_in, shop, edit)
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == original["id"]
    assert logged_in.get(f"{root(shop)}/{edit['id']}").json()["status"] == "draft"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 1
    assert approve(logged_in, shop, edit)["status"] == "applied"


def test_two_sessions_create_and_approve_once(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    data = EditCreate.model_validate(body(logged_in, shop))
    with session_factory() as session:
        owner = session.scalar(select(User.id))
        assert owner is not None
    barrier = Barrier(2)

    def run() -> int:
        with session_factory() as session:
            barrier.wait()
            service = ProductEditService(UnitOfWork(session))
            edit = service.create(owner, shop, data)
            result = service.approve(
                owner,
                shop,
                edit.id,
                EditDecision(version=1, expected_preview_hash=edit.preview_hash, confirm=True),
            )
            assert result.output_batch_id
            return result.output_batch_id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ProductEdit)) == 1
        assert session.scalar(select(func.count()).select_from(ImportBatch)) == 2


def test_import_preview_compares_against_manual_source_and_supersedes(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = approve(logged_in, shop, draft(logged_in, shop))
    uploaded = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic.csv",
            "kind": "products",
            "data_identity": "synthetic",
            "timezone": "Asia/Shanghai",
        },
        content=PRODUCTS.encode(),
    ).json()
    result = preview(logged_in, uploaded)
    assert result["rows"][0]["previous"]["name"] == "Test Cup revised"
    commit(logged_in, result, allow_updates=True)
    assert logged_in.get(f"{root(shop)}/{edit['id']}").json()["current_count"] == 0


def test_foreign_shop_object_and_csrf_denied(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    other = create_shop(logged_in, "other")
    assert logged_in.get(f"{root(other)}/{edit['id']}").status_code == 404
    assert logged_in.post(root(other), json=body(logged_in, shop)).status_code == 409
    assert logged_in.get(root(999999)).status_code == 404
    logged_in.headers.pop("X-CSRF-Token")
    assert (
        logged_in.post(f"{root(shop)}/{edit['id']}/approve", json=decision(edit)).status_code == 403
    )


def test_restored_source_never_reactivates_an_old_approval(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    original = imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    newer = imported(logged_in, shop, PRODUCTS.replace("Test Cup", "Later Cup"), "products")
    assert (
        logged_in.post(
            f"/api/imports/{newer['id']}/revoke", json={"version": newer["version"]}
        ).status_code
        == 200
    )
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == original["id"]
    assert approve(logged_in, shop, edit)["status"] == "failed"


def test_competing_drafts_do_not_overwrite_new_approval(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    first = draft(logged_in, shop)
    second = draft(logged_in, shop)
    applied = approve(logged_in, shop, first)
    assert approve(logged_in, shop, second)["status"] == "failed"
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == applied["output_batch_id"]


def test_fifty_products_and_ancestry_limit(logged_in: TestClient) -> None:
    from app.repositories.product_edits import ProductEditRepository

    shop = create_shop(logged_in)
    imported(
        logged_in, shop, HEADER + "".join(f"{i},Cup,Steel,,,,\n" for i in range(50)), "products"
    )
    data = body(logged_in, shop)
    with patch.object(ProductEditRepository, "ancestors", return_value=set(range(1001))):
        assert logged_in.post(root(shop), json=data).status_code == 422
    edit = draft(logged_in, shop)
    assert approve(logged_in, shop, edit)["current_count"] == 50


def test_cascade_purge_audit_failure_rolls_back_source_and_all_children(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    origin = imported(logged_in, shop, PRODUCTS, "products")
    first = approve(logged_in, shop, draft(logged_in, shop))
    second = approve(logged_in, shop, draft(logged_in, shop))
    record = UnitOfWork.record_event

    def fail(
        self: UnitOfWork, actor: int, action: str, kind: str, resource: int, *args: Any
    ) -> None:
        if action == "import.cleared" and resource == origin["id"]:
            raise RuntimeError("synthetic final audit failure")
        record(self, actor, action, kind, resource, *args)

    with patch.object(UnitOfWork, "record_event", fail), pytest.raises(RuntimeError):
        logged_in.post(f"/api/imports/{origin['id']}/clear", json={"version": origin["version"]})
    for edit in [first, second]:
        actual = logged_in.get(f"{root(shop)}/{edit['id']}").json()
        assert actual["status"] == "applied" and actual["snapshot"]
    assert check(logged_in, shop)["products"][0]["source"]["batch_id"] == second["output_batch_id"]


def test_foreign_owner_cannot_read_modify_or_purge_edits(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Any
) -> None:
    from app.schemas.identity import AccountInput
    from app.services.auth import AuthService
    from tests.conftest import TEST_PASSWORD

    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    edit = draft(logged_in, shop)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="outsider", password=TEST_PASSWORD)
        )
    logged_in.post("/api/auth/logout")
    login = logged_in.post(
        "/api/auth/login", json={"username": "outsider", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert logged_in.get(root(shop)).status_code == 404
    assert logged_in.get(f"{root(shop)}/{edit['id']}").status_code == 404
    assert (
        logged_in.post(f"{root(shop)}/{edit['id']}/approve", json=decision(edit)).status_code == 404
    )
    assert (
        logged_in.post(
            f"{root(shop)}/{edit['id']}/clear", json={"confirm": True, "version": 1}
        ).status_code
        == 404
    )
