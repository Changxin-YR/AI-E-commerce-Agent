from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.time import utc_now
from app.models.agent import AgentExecution, AgentStep
from app.models.identity import AuditEvent, Shop
from app.models.operations import OperationRun, OperationTask
from app.models.outbound import OutboundMessage
from app.models.support import SupportPolicy
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.analytics import TodoAction
from app.schemas.identity import AccountInput
from app.services.analytics import AnalyticsService
from app.services.auth import AuthService
from tests.conftest import TEST_PASSWORD
from tests.test_agent import act, start
from tests.test_analytics import SCOPE, calculate, imported
from tests.test_authorizations import create as create_grant
from tests.test_business_rules import save as save_rule
from tests.test_imports import PRODUCTS, create_shop
from tests.test_listings import generate as generate_listing
from tests.test_operations import ORDERS, change, run, tasks
from tests.test_outbound import FakeMail, approve, prepare
from tests.test_outbound import mailbox as mailbox
from tests.test_overview import run as overview_run
from tests.test_overview import saved as save_overview
from tests.test_support import MESSAGES, policy, withdraw
from tests.test_support import generate as generate_reply


def page(client: TestClient, **query: Any) -> dict[str, Any]:
    response = client.get("/api/workbench", params=query)
    assert response.status_code == 200, response.text
    return response.json()


def test_empty_and_query_validation(logged_in: TestClient) -> None:
    assert page(logged_in)["items"] == []
    assert page(logged_in)["counts"] == {}
    for query in [{"shop_id": 0}, {"kind": "script"}, {"cursor": "bad"}, {"bucket": "send"}]:
        assert logged_in.get("/api/workbench", params=query).status_code == 422
    assert logged_in.get("/api/workbench?shop_id=99999").status_code == 404


def test_real_runs_tasks_approval_and_identity(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    check = run(logged_in, shop)
    execution = act(logged_in, start(logged_in, shop))
    data = page(logged_in, shop_id=shop, data_identity="synthetic", channel="generic")
    assert {r["kind"] for r in data["items"]} == {"operation_task", "operation_run", "agent"}
    assert data["counts"]["approval"] == len(tasks(logged_in, shop)) + 1
    agent = next(r for r in data["items"] if r["kind"] == "agent")
    assert agent["query"] == {
        "execution": str(execution["id"]),
        "shop": str(shop),
        "identity": "synthetic",
        "channel": "generic",
    }
    assert "检查数据" in agent["detail"] and agent["bucket"] == "approval"
    saved = next(r for r in data["items"] if r["kind"] == "operation_run")
    assert saved["target_id"] == check["id"] and "导出时间未知" in saved["detail"]
    assert page(logged_in, data_identity="user_import")["items"] == []
    assert page(logged_in, channel="amazon")["items"] == []
    task = tasks(logged_in, shop)[0]
    change(logged_in, shop, task, "approve")
    pending = page(logged_in, bucket="pending")
    assert pending["items"][0]["id"] == task["id"]
    assert pending["items"][0]["status"] == "open"


def test_cursor_equal_timestamp_and_scoped_counts(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    other = create_shop(logged_in, code="other")
    for _ in range(23):
        run(logged_in, shop)
    run(logged_in, other)
    with session_factory() as session:
        session.execute(update(OperationRun).values(created_at=utc_now()))
        session.commit()
    first = page(logged_in, shop_id=shop)
    assert len(first["items"]) == 20 and first["counts"] == {"history": 23}
    second = page(logged_in, shop_id=shop, cursor=first["next_cursor"])
    assert len(second["items"]) == 3 and second["next_cursor"] is None
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
    assert (
        logged_in.get("/api/workbench", params={"cursor": first["next_cursor"]}).status_code == 422
    )


def test_expiry_unknown_and_read_has_no_side_effects(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    run(logged_in, shop)
    execution = start(logged_in, shop)
    with session_factory() as session:
        agent = session.get(AgentExecution, execution["id"])
        assert agent
        agent.status = "running"
        agent.lease_until = utc_now() - timedelta(seconds=1)
        for task in session.scalars(select(OperationTask)):
            task.valid_until = utc_now() - timedelta(microseconds=1)
        session.commit()
        audits = session.scalar(select(func.count(AuditEvent.id)))
        steps = session.scalar(select(func.count(AgentStep.id)))
    assert page(logged_in, bucket="unknown")["items"][0]["status"] == "result_unknown"
    assert all(
        r["source_status"] == "stale" for r in page(logged_in, kind="operation_task")["items"]
    )
    with session_factory() as session:
        assert session.get(AgentExecution, execution["id"]).status == "running"
        assert session.scalar(select(func.count(AgentStep.id))) == steps
        assert session.scalar(select(func.count(AuditEvent.id))) == audits


def test_purge_removes_metadata_body_and_owner_isolation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, ORDERS, "orders")
    run(logged_in, shop)
    batch = withdraw(logged_in, batch, "revoke")
    assert page(logged_in, bucket="stale")["items"]
    withdraw(logged_in, batch, "clear")
    cleared = page(logged_in)["items"]
    assert all(r["source_status"] == "cleared" and not r["label"] for r in cleared)
    assert all(r["detail"] == "正文已清除" for r in cleared)
    logged_in.post("/api/auth/logout")
    assert logged_in.get("/api/workbench").status_code == 401


def test_listing_reply_reports_and_analysis_todo(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    other = create_shop(logged_in, code="second")
    imported(logged_in, shop, PRODUCTS, "products")
    imported(logged_in, shop, MESSAGES, "messages")
    product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[0]
    listing = generate_listing(logged_in, shop, product)
    message = logged_in.get(f"/api/shops/{shop}/support/messages").json()[0]
    reply = generate_reply(logged_in, shop, message["id"])
    result = calculate(logged_in, shop)
    saved = logged_in.post(
        f"/api/shops/{shop}/analytics/saved",
        json={
            "scope": SCOPE,
            "expected_revision": result["source_revision"],
        },
    ).json()
    todo = logged_in.post(f"/api/shops/{shop}/analytics/saved/{saved['id']}/todo").json()["todo"]
    report = save_overview(logged_in, overview_run(logged_in, [shop, other]))
    records = {r["kind"]: r for r in page(logged_in, shop_id=shop)["items"]}
    assert records["listing"]["id"] == listing["id"]
    assert records["listing"]["bucket"] == "approval"
    assert records["reply"]["id"] == reply["id"] and records["reply"]["bucket"] == "pending"
    assert records["reply"]["label"] == "M1"
    assert records["analysis_todo"]["id"] == todo["id"]
    assert records["analysis_todo"]["target_id"] == saved["id"]
    assert records["overview"]["query"] == {"report": str(report["id"]), "identity": "synthetic"}
    assert len(page(logged_in, shop_id=other)["items"]) == 1
    assert {r["kind"] for r in page(logged_in, channel="generic")["items"]} == {"listing", "reply"}
    assert all(r["data_identity"] == "synthetic" for r in records.values())
    assert all("snapshot" not in r for r in records.values())


def test_rules_and_r1_projection_match_original_service(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    run(logged_in, shop)
    execution = act(logged_in, start(logged_in, shop))
    grant = create_grant(logged_in, execution)
    current = page(logged_in, kind="authorization")["items"][0]
    assert current["status"] == "active" and current["query"]["authorization"] == str(grant["id"])
    save_rule(logged_in, shop)
    changed = page(logged_in, kind="authorization")["items"][0]
    original = logged_in.get(f"/api/shops/{shop}/authorizations/{grant['id']}").json()
    assert changed["status"] == original["status"] == "rules_changed"
    assert all(r["source_status"] == "stale" for r in page(logged_in)["items"])


def test_policy_time_boundary_is_applied_without_opening_support(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, MESSAGES, "messages")
    message = logged_in.get(f"/api/shops/{shop}/support/messages").json()[0]
    p = policy(logged_in, shop)
    generate_reply(logged_in, shop, message["id"], policies=[p["id"]])
    assert page(logged_in, kind="reply")["items"][0]["source_status"] == "current"
    with session_factory() as session:
        session.execute(
            update(SupportPolicy)
            .where(SupportPolicy.id == p["id"])
            .values(
                valid_until=utc_now() - timedelta(microseconds=1),
            )
        )
        session.commit()
    assert page(logged_in, kind="reply")["items"][0]["source_status"] == "stale"


def test_r2_unknown_retains_receipt_path_and_never_submits(
    logged_in: TestClient,
    mailbox: tuple[int, FakeMail, Settings],
    session_factory: sessionmaker[Session],
) -> None:
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    assert page(logged_in, kind="outbound")["items"][0]["risk"] == "R2"
    with session_factory() as session:
        session.execute(
            update(OutboundMessage)
            .where(OutboundMessage.id == mail["id"])
            .values(
                status="sending",
                dispatch_at=utc_now() - timedelta(seconds=61),
                source_status="stale",
            )
        )
        session.commit()
    result = page(logged_in, bucket="unknown")["items"][0]
    assert result["status"] == "unknown" and result["source_status"] == "stale"
    assert result["path"] == "/outbound" and result["query"]["mail"] == str(mail["id"])
    assert len(fake.sent) == 1  # Only fixture's verification email.


def test_other_owner_cannot_list_count_or_follow_items(
    logged_in: TestClient,
    settings: Settings,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    run(logged_in, shop)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="second", password=TEST_PASSWORD),
        )
    login = logged_in.post(
        "/api/auth/login", json={"username": "second", "password": TEST_PASSWORD}
    )
    assert login.status_code == 200
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert page(logged_in)["items"] == [] and page(logged_in)["counts"] == {}
    assert page(logged_in)["recent_runs"] == []
    assert logged_in.get(f"/api/workbench?shop_id={shop}").status_code == 404
    with session_factory() as session:
        assert session.scalar(select(func.count(Shop.id))) == 1


def analysis_todo(client: TestClient) -> tuple[int, dict[str, Any], dict[str, Any]]:
    shop = create_shop(client)
    batch = imported(client, shop, ORDERS, "orders")
    result = calculate(client, shop)
    saved = client.post(
        f"/api/shops/{shop}/analytics/saved",
        json={
            "scope": SCOPE,
            "expected_revision": result["source_revision"],
        },
    ).json()
    todo = client.post(f"/api/shops/{shop}/analytics/saved/{saved['id']}/todo").json()
    return shop, batch, todo


def test_analysis_todo_complete_replay_reopen_and_old_version(logged_in: TestClient) -> None:
    shop, batch, item = analysis_todo(logged_in)
    url = f"/api/shops/{shop}/analytics/saved/{item['id']}/todo/action"
    action = {"expected_version": item["todo"]["version"], "action": "complete"}
    completed = logged_in.post(url, json=action)
    assert completed.status_code == 200
    assert completed.json()["todo"]["version"] == 2
    assert logged_in.post(url, json=action).json() == completed.json()
    assert page(logged_in, kind="analysis_todo")["items"][0]["bucket"] == "history"
    reopened = logged_in.post(url, json={"expected_version": 2, "action": "reopen"})
    assert reopened.json()["todo"]["version"] == 3
    assert logged_in.post(url, json=action).status_code == 409
    assert (
        logged_in.post(url, json={"expected_version": 3, "action": "complete"}).status_code == 200
    )
    withdraw(logged_in, batch, "revoke")
    # Completed work retains its disposition while its evidence is marked stale.
    record = page(logged_in, kind="analysis_todo")["items"][0]
    assert record["status"] == "completed" and record["source_status"] == "stale"
    assert logged_in.post(url, json={"expected_version": 4, "action": "reopen"}).status_code == 409


def test_analysis_todo_permissions_and_audit_rollback(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop, batch, item = analysis_todo(logged_in)
    other = create_shop(logged_in, code="other")
    url = f"/api/shops/{shop}/analytics/saved/{item['id']}/todo/action"
    data = {"expected_version": 1, "action": "complete"}
    assert (
        logged_in.post(url.replace(f"shops/{shop}", f"shops/{other}"), json=data).status_code == 404
    )
    token = logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(url, json=data).status_code == 403
    logged_in.headers["X-CSRF-Token"] = token
    owner = logged_in.get("/api/auth/session").json()["user_id"]
    with session_factory() as session:
        uow = UnitOfWork(session)
        with (
            patch.object(uow, "record_event", side_effect=RuntimeError("audit failed")),
            pytest.raises(RuntimeError, match="audit failed"),
        ):
            AnalyticsService(uow).change_todo(
                owner, shop, item["id"], TodoAction.model_validate(data)
            )
        session.rollback()
    fresh = logged_in.get(f"/api/shops/{shop}/analytics/saved/{item['id']}").json()
    assert fresh["todo"] == item["todo"]
    batch = withdraw(logged_in, batch, "revoke")
    withdraw(logged_in, batch, "clear")
    assert logged_in.post(url, json=data).status_code == 409
