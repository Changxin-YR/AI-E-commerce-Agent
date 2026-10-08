from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.time import utc_now
from app.models.identity import User
from app.models.operations import (
    OperationRun,
    OperationTask,
    OperationTaskEvent,
    OperationTaskSource,
)
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.operations import RunInput, TaskInput
from app.services.auth import AuthService
from app.services.operations import OperationsService
from app.services.profit_calculation import utc_text
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import SCOPE, imported
from tests.test_imports import PRODUCTS, commit, create_shop, preview, upload
from tests.test_inventory import csv
from tests.test_support import MESSAGES, withdraw

ORDERS = (
    "order_id,line_id,sku,quantity,unit_price,currency,ordered_at,status,discount,refund,fulfillment_status\n"
    "O1,1,001,2,8,USD,2026-10-07T01:00:00Z,paid,0,0,unfulfilled\n"
)


def root(shop: int) -> str:
    return f"/api/shops/{shop}/operations"


def run(client: TestClient, shop: int, **scope: Any) -> dict[str, Any]:
    response = client.post(
        root(shop) + "/runs", json={"request_id": str(uuid4()), "scope": {**SCOPE, **scope}}
    )
    assert response.status_code == 200, response.text
    return response.json()


def tasks(client: TestClient, shop: int, **query: Any) -> list[dict[str, Any]]:
    response = client.get(root(shop) + "/tasks", params={"data_identity": "synthetic", **query})
    assert response.status_code == 200, response.text
    return response.json()["items"]


def change(
    client: TestClient, shop: int, task: dict[str, Any], action: str, **fields: Any
) -> dict[str, Any]:
    response = client.post(
        root(shop) + f"/tasks/{task['id']}",
        json={"version": task["version"], "action": action, **fields},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_branches_and_optional_data(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    empty = run(logged_in, shop)
    assert all(b["status"] == "not_checked" for b in empty["snapshot"]["branches"])
    assert not empty["snapshot"]["task_ids"]
    imported(logged_in, shop, PRODUCTS, "products")
    imported(logged_in, shop, ORDERS, "orders")
    result = run(logged_in, shop)
    branches = {b["name"]: b for b in result["snapshot"]["branches"]}
    assert branches["已知毛利"]["status"] == "checked"
    assert branches["库存阈值"]["status"] == "not_checked"
    assert branches["消息回复核对"]["status"] == "not_checked"
    assert result["snapshot"]["model_status"] == "not_configured"
    assert {t["kind"] for t in tasks(logged_in, shop)} == {"order_review", "low_margin"}


def test_all_branches_evidence_and_approval(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    for content, kind in [
        (PRODUCTS, "products"),
        (ORDERS, "orders"),
        (csv(), "inventory"),
        (MESSAGES, "messages"),
    ]:
        imported(logged_in, shop, content, kind)
    result = run(logged_in, shop)
    items = tasks(logged_in, shop)
    assert len(items) == 4 and result["snapshot"]["created_candidates"] == 4
    assert all(t["status"] == "pending_approval" for t in items)
    assert "导出时间未知" in result["snapshot"]["data_as_of"]
    for item in items:
        for source in item["snapshot"]["sources"]:
            response = logged_in.get(f"/api/shops/{shop}/analytics/sources/{source['row_id']}")
            assert response.status_code == 200 and response.json()["raw"]
    task = change(logged_in, shop, items[0], "approve", note="已核对来源")
    assert task["status"] == "open" and task["external_status"] == "not_submitted"
    replay = change(logged_in, shop, items[0], "approve", note="已核对来源")
    assert replay == task
    assert len(task["history"]) == 2
    assert tasks(logged_in, shop)[0]["note"] == "已核对来源"


@pytest.mark.parametrize("disposition", ["ignore", "reject", "complete", "defer"])
def test_repeated_checks_preserve_disposition_and_unrelated_revision(
    logged_in: TestClient, disposition: str
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, MESSAGES, "messages")
    first = run(logged_in, shop)
    task = tasks(logged_in, shop)[0]
    if disposition in {"complete", "defer"}:
        task = change(logged_in, shop, task, "approve")
    fields = {"due_at": utc_text(utc_now() + timedelta(days=1))} if disposition == "defer" else {}
    task = change(logged_in, shop, task, disposition, **fields)
    imported(logged_in, shop, PRODUCTS, "products")
    second = run(logged_in, shop)
    assert second["source_revision"] > first["source_revision"]
    assert second["snapshot"]["created_candidates"] == 0
    assert second["snapshot"]["task_ids"] == first["snapshot"]["task_ids"]
    saved = tasks(logged_in, shop)[0]
    assert saved["status"] == task["status"] and saved["due_at"] == task["due_at"]
    reopened = change(logged_in, shop, saved, "reopen")
    assert reopened["status"] == "open"


def test_inventory_expiry_blocks_approval_and_unknown_never_creates(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv(), "inventory")
    result = run(logged_in, shop)
    task = tasks(logged_in, shop)[0]
    expires = datetime.fromisoformat(task["snapshot"]["valid_until"]).replace(tzinfo=None)
    with patch("app.services.operations.utc_now", return_value=expires):
        assert (
            logged_in.post(
                root(shop) + f"/tasks/{task['id']}",
                json={"version": task["version"], "action": "approve"},
            ).status_code
            == 409
        )
        assert tasks(logged_in, shop)[0]["source_status"] == "stale"
        assert (
            logged_in.get(root(shop) + f"/runs/{result['id']}").json()["source_status"] == "stale"
        )
        assert run(logged_in, shop)["snapshot"]["task_ids"] == []
    assert len(tasks(logged_in, shop)) == 1


def test_source_replacement_restore_and_clear_erases_history_content(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    a = imported(logged_in, shop, MESSAGES, "messages")
    inventory = imported(logged_in, shop, csv(), "inventory")
    first = run(logged_in, shop)
    original = next(t for t in tasks(logged_in, shop) if t["kind"] == "message_review")
    original = change(logged_in, shop, original, "approve", note="Private synthetic note")
    b = imported(logged_in, shop, MESSAGES.replace("Where is my order?", "New text."), "messages")
    assert logged_in.get(root(shop) + f"/tasks/{original['id']}").json()["source_status"] == "stale"
    withdraw(logged_in, b, "revoke")
    assert logged_in.get(root(shop) + f"/tasks/{original['id']}").json()["source_status"] == "stale"
    result = run(logged_in, shop)
    assert result["snapshot"]["created_candidates"] == 0
    restored = logged_in.get(root(shop) + f"/tasks/{original['id']}").json()
    assert restored["source_status"] == "current" and restored["status"] == "open"
    withdraw(logged_in, a, "clear")
    cleared = logged_in.get(root(shop) + f"/tasks/{original['id']}").json()
    assert cleared["snapshot"] is None and cleared["note"] == "" and cleared["due_at"] is None
    assert all(h["note"] is None for h in cleared["history"])
    assert logged_in.get(root(shop) + f"/runs/{first['id']}").json()["snapshot"] is None
    stock = next(t for t in tasks(logged_in, shop) if t["kind"] == "low_inventory")
    assert stock["snapshot"]["sources"][0]["batch_id"] == inventory["id"]
    with session_factory() as session:
        assert not session.scalars(
            select(OperationTaskSource).where(OperationTaskSource.task_id == original["id"])
        ).all()
        assert all(
            e.details is None
            for e in session.scalars(
                select(OperationTaskEvent).where(OperationTaskEvent.task_id == original["id"])
            )
        )


def test_old_cost_clear_purges_dependent_low_margin_only(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    product = imported(logged_in, shop, PRODUCTS, "products")
    imported(logged_in, shop, ORDERS, "orders")
    first = run(logged_in, shop)
    margin = next(t for t in tasks(logged_in, shop) if t["kind"] == "low_margin")
    imported(logged_in, shop, PRODUCTS.replace("7.125", "7.5"), "products")
    run(logged_in, shop)
    withdraw(logged_in, product, "clear")
    assert logged_in.get(root(shop) + f"/tasks/{margin['id']}").json()["snapshot"] is None
    assert logged_in.get(root(shop) + f"/runs/{first['id']}").json()["snapshot"] is None
    assert sum(t["snapshot"] is not None for t in tasks(logged_in, shop)) == 2


def test_incomplete_profit_and_cancelled_orders_do_not_claim_findings(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS.replace(",0,0,unfulfilled", ",,0,unfulfilled"), "orders")
    run(logged_in, shop)
    assert {t["kind"] for t in tasks(logged_in, shop)} == {"order_review"}
    imported(logged_in, shop, ORDERS.replace(",paid,", ",cancelled,"), "orders")
    latest = run(logged_in, shop)
    assert latest["snapshot"]["task_ids"] == []


def test_run_replay_input_allowlist_and_task_conflicts(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, MESSAGES, "messages")
    payload = {"request_id": str(uuid4()), "scope": SCOPE}
    first = logged_in.post(root(shop) + "/runs", json=payload).json()
    assert logged_in.post(root(shop) + "/runs", json=payload).json() == first
    payload["scope"] = {**SCOPE, "currency": "CNY"}
    assert logged_in.post(root(shop) + "/runs", json=payload).status_code == 409
    payload["auto_approve"] = True
    assert logged_in.post(root(shop) + "/runs", json=payload).status_code == 422
    task = tasks(logged_in, shop)[0]
    opened = change(logged_in, shop, task, "approve")
    assert (
        logged_in.post(
            root(shop) + f"/tasks/{task['id']}",
            json={"version": task["version"], "action": "edit", "note": "stale"},
        ).status_code
        == 409
    )
    assert (
        logged_in.post(
            root(shop) + f"/tasks/{task['id']}",
            json={"version": opened["version"], "action": "defer"},
        ).status_code
        == 422
    )
    assert (
        logged_in.post(
            root(shop) + f"/tasks/{task['id']}",
            json={"version": opened["version"], "action": "edit", "due_at": "2030-01-01T00:00:00"},
        ).status_code
        == 422
    )
    del logged_in.headers["X-CSRF-Token"]
    assert (
        logged_in.post(
            root(shop) + "/runs", json={"request_id": str(uuid4()), "scope": SCOPE}
        ).status_code
        == 403
    )


def test_shop_identity_channel_isolation_and_owner_permissions(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, MESSAGES, "messages")
    saved = run(logged_in, shop)
    task = tasks(logged_in, shop)[0]
    assert not run(logged_in, shop, data_identity="user_import")["snapshot"]["task_ids"]
    assert not run(logged_in, shop, channel="amazon")["snapshot"]["task_ids"]
    other = create_shop(logged_in, "other")
    assert logged_in.get(root(other) + f"/tasks/{task['id']}").status_code == 404
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="outsider", password=TEST_PASSWORD)
        )
    logged_in.post("/api/auth/logout")
    auth = logged_in.post(
        "/api/auth/login", json={"username": "outsider", "password": TEST_PASSWORD}
    ).json()
    logged_in.headers["X-CSRF-Token"] = auth["csrf_token"]
    for endpoint in ["/tasks", f"/tasks/{task['id']}", "/runs", f"/runs/{saved['id']}"]:
        assert logged_in.get(root(shop) + endpoint).status_code == 404
    assert (
        logged_in.post(
            root(shop) + "/runs", json={"request_id": str(uuid4()), "scope": SCOPE}
        ).status_code
        == 404
    )


def test_concurrent_runs_and_task_edits_use_current_reads(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, MESSAGES, "messages")
    barrier = Barrier(2)
    payload = RunInput.model_validate({"request_id": str(uuid4()), "scope": SCOPE})

    def worker() -> int:
        with session_factory() as session:
            owner = session.scalar(select(User.id).where(User.username == "seller"))
            assert owner
            barrier.wait(timeout=10)
            return OperationsService(UnitOfWork(session)).run(owner, shop, payload).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(lambda _: worker(), range(2)))
    assert result[0] == result[1]
    task = tasks(logged_in, shop)[0]

    def editor(note: str) -> int:
        with session_factory() as session:
            owner = session.scalar(select(User.id).where(User.username == "seller"))
            assert owner
            barrier.wait(timeout=10)
            try:
                OperationsService(UnitOfWork(session)).change_task(
                    owner,
                    shop,
                    task["id"],
                    TaskInput(version=task["version"], action="edit", note=note),
                )
                return 200
            except ConflictError:
                return 409

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(editor, ["one", "two"])) == [200, 409]
    with session_factory() as session:
        assert session.scalar(select(func.count(OperationTask.id))) == 1
        assert session.scalar(select(func.count(OperationRun.id))) == 1


def test_bounded_inbox_pagination_and_atomic_candidate_limit(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    content = "message_id,sent_at,body,language\n" + "".join(
        f"M{i},2026-10-07T00:00:00Z,Question,en\n" for i in range(51)
    )
    imported(logged_in, shop, content, "messages")
    run(logged_in, shop)
    assert len(tasks(logged_in, shop)) == 50 and len(tasks(logged_in, shop, offset=50)) == 1
    larger = content + "".join(f"M{i},2026-10-07T00:00:00Z,Question,en\n" for i in range(51, 501))
    imported(logged_in, shop, larger, "messages")
    response = logged_in.post(
        root(shop) + "/runs", json={"request_id": str(uuid4()), "scope": SCOPE}
    )
    assert response.status_code == 422
    assert len(tasks(logged_in, shop, offset=50)) == 1


def test_inventory_channel_and_threshold_rules(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv("5", "5"), "inventory")
    assert not run(logged_in, shop)["snapshot"]["task_ids"]
    imported(logged_in, shop, csv("1", "5", age=30), "inventory")
    assert not run(logged_in, shop)["snapshot"]["task_ids"]
    assert run(logged_in, shop, max_age_hours=48)["snapshot"]["created_candidates"] == 1
    batch = upload(logged_in, shop, MESSAGES, "messages")
    commit(logged_in, preview(logged_in, batch))
    assert len(run(logged_in, shop, channel="amazon")["snapshot"]["task_ids"]) == 0
