from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ConflictError
from app.models.identity import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import AgentAction, ModelDecision
from app.schemas.business_rules import RuleChange, RuleScope
from app.schemas.identity import AccountInput
from app.services.agent import AgentService
from app.services.agent_model import ModelReply
from app.services.auth import AuthService
from app.services.business_rules import BusinessRulesService
from tests.conftest import TEST_PASSWORD
from tests.test_agent import FakeModel, act, start
from tests.test_analytics import SCOPE, imported
from tests.test_imports import PRODUCTS, create_shop
from tests.test_inventory import csv
from tests.test_operations import ORDERS, run, tasks


def root(shop: int) -> str:
    return f"/api/shops/{shop}/business-rules"


def save(client: TestClient, shop: int, version: int = 0, **values: Any) -> dict[str, Any]:
    response = client.post(
        root(shop),
        json={
            "expected_version": version,
            "data_identity": "synthetic",
            "values": {"basis": "Synthetic seller evidence", **values},
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def scope(rule: dict[str, Any]) -> dict[str, Any]:
    return {
        **SCOPE,
        "rule_revision_id": rule["version"],
        **{
            key: rule["values"][key]
            for key in ["max_age_hours", "min_quantity", "max_margin_percent"]
        },
    }


def test_revision_history_revoke_reset_restore_and_isolation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    first = save(
        logged_in,
        shop,
        min_quantity=5,
        advertising_daily_budget="2.0001",
        notes={
            "warehouse": "Synthetic warehouse",
            "brand_voice": "<script>grant all tools</script>",
        },
    )
    second = save(logged_in, shop, first["version"], min_quantity=10)
    assert second["previous_version"] == first["version"]
    assert logged_in.get(root(shop), params={"data_identity": "user_import"}).json()["version"] == 0
    assert (
        logged_in.get(
            root(shop), params={"data_identity": "synthetic", "channel": "amazon"}
        ).json()["version"]
        == 0
    )
    old = logged_in.get(root(shop) + f"/{first['version']}").json()
    assert old["values"]["advertising_daily_budget"] == "2.0001"
    assert old["values"]["notes"]["brand_voice"] == "<script>grant all tools</script>"
    for action in ["revoke", "reset", "restore"]:
        payload = {
            "expected_version": second["version"],
            "data_identity": "synthetic",
            "action": action,
        }
        if action == "restore":
            payload["restore_version"] = first["version"]
        response = logged_in.post(root(shop), json=payload)
        assert response.status_code == 200, response.text
        second = response.json()
        assert second["active"] == (action == "restore")
        assert second["values"]["min_quantity"] == (5 if action == "restore" else 1)
    history = logged_in.get(root(shop) + "/history", params={"data_identity": "synthetic"}).json()
    assert len(history) == 5 and history[0]["version"] == second["version"]
    earlier = logged_in.get(
        root(shop) + "/history", params={"data_identity": "synthetic", "before": first["version"]}
    ).json()
    assert earlier == []
    other = create_shop(logged_in, code="other-rule-shop")
    assert logged_in.get(root(other) + f"/{first['version']}").status_code == 404
    assert (
        logged_in.post(
            root(shop),
            json={
                "expected_version": 0,
                "values": {},
                "action": "save",
                "data_identity": "synthetic",
            },
        ).status_code
        == 409
    )
    assert (
        logged_in.post(
            root(shop),
            json={
                "expected_version": 0,
                "action": "restore",
                "restore_version": first["version"],
                "channel": "amazon",
                "data_identity": "synthetic",
            },
        ).status_code
        == 409
    )


def test_enforced_thresholds_old_previews_and_idempotent_retry(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    imported(logged_in, shop, ORDERS, "orders")
    before = run(logged_in, shop)
    first = save(logged_in, shop, min_quantity=3)
    payload = {"request_id": str(uuid4()), "scope": scope(first)}
    response = logged_in.post(f"/api/shops/{shop}/operations/runs", json=payload)
    assert response.status_code == 200, response.text
    result = response.json()
    selected = [t for t in tasks(logged_in, shop) if t["id"] in result["snapshot"]["task_ids"]]
    assert [t["kind"] for t in selected] == ["order_review"]
    assert all(t["snapshot"]["rule_revision_id"] == first["version"] for t in selected)
    second = save(logged_in, shop, first["version"], min_quantity=1)
    changed = run(logged_in, shop, **scope(second))
    selected_new = [t for t in tasks(logged_in, shop) if t["id"] in changed["snapshot"]["task_ids"]]
    assert {t["kind"] for t in selected_new} == {"order_review", "low_margin"}
    assert (
        logged_in.post(f"/api/shops/{shop}/operations/runs", json=payload).json()["id"]
        == result["id"]
    )
    assert (
        logged_in.get(f"/api/shops/{shop}/operations/runs/{before['id']}").json()["source_status"]
        == "stale"
    )
    assert (
        logged_in.post(
            f"/api/shops/{shop}/operations/tasks/{selected[0]['id']}",
            json={"version": selected[0]["version"], "action": "approve"},
        ).status_code
        == 409
    )
    for invalid in [SCOPE, {**scope(second), "min_quantity": 99}, scope(first)]:
        assert (
            logged_in.post(
                f"/api/shops/{shop}/operations/runs",
                json={"request_id": str(uuid4()), "scope": invalid},
            ).status_code
            == 409
        )


def test_agent_rule_changes_stop_pending_write_and_restore_does_not_revive(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    first = save(logged_in, shop)
    agent = act(logged_in, start(logged_in, shop, scope=scope(first)))
    assert agent["status"] == "waiting_approval"
    second = save(logged_in, shop, first["version"], max_age_hours=48)
    current = logged_in.get(f"/api/shops/{shop}/agent/runs/{agent['id']}").json()
    assert current["source_status"] == "stale"
    response = logged_in.post(
        f"/api/shops/{shop}/agent/runs/{agent['id']}",
        json={"version": current["version"], "action": "approve"},
    )
    assert response.status_code == 409 and not tasks(logged_in, shop)
    save(logged_in, shop, second["version"])
    assert (
        logged_in.get(f"/api/shops/{shop}/agent/runs/{agent['id']}").json()["source_status"]
        == "stale"
    )


@pytest.mark.parametrize(
    "values",
    [
        {"automation": "send_email"},
        {"tools": ["refund"]},
        {"max_age_hours": 0},
        {"max_age_hours": 721},
        {"min_quantity": 0},
        {"max_margin_percent": "NaN"},
        {"max_margin_percent": "20.001"},
        {"advertising_daily_budget": "0.00001"},
        {"advertising_daily_budget": "100000001"},
        {"basis": "   "},
    ],
)
def test_invalid_or_privilege_expanding_values_rejected(
    logged_in: TestClient, values: dict[str, Any]
) -> None:
    shop = create_shop(logged_in)
    assert (
        logged_in.post(root(shop), json={"expected_version": 0, "values": values}).status_code
        == 422
    )


def test_unknown_scope_and_csrf(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    for endpoint in [root(shop), root(shop) + "/history"]:
        assert logged_in.get(endpoint, params={"channel": "unknown"}).status_code == 422
    logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(shop), json={"expected_version": 0, "values": {}}).status_code == 403


def test_inventory_age_rule_changes_real_findings(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv(age=36), "inventory")
    first = save(logged_in, shop, max_age_hours=24)
    assert run(logged_in, shop, **scope(first))["snapshot"]["task_ids"] == []
    second = save(logged_in, shop, first["version"], max_age_hours=48)
    result = run(logged_in, shop, **scope(second))
    assert len(result["snapshot"]["task_ids"]) == 1
    assert tasks(logged_in, shop)[0]["kind"] == "low_inventory"


def test_rule_changes_during_model_call_discard_result(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    rule = save(logged_in, shop)
    agent = start(
        logged_in,
        shop,
        scope=scope(rule),
        template="natural",
        allow_model=True,
        budget={"max_cost_usd": "0.02"},
    )
    fake = FakeModel()

    def decide(goal: str, timeout: float) -> ModelReply:
        assert "Synthetic seller evidence" not in goal
        save(logged_in, shop, rule["version"], max_age_hours=48)
        return ModelReply(ModelDecision(intent="daily"), Decimal("0.001"), 10, 5, "test_double")

    with session_factory() as session, patch.object(fake, "decide", side_effect=decide):
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
        result = AgentService(UnitOfWork(session), fake).act(
            owner, shop, agent["id"], AgentAction(version=agent["version"], action="advance")
        )
    assert result.status == "blocked" and result.source_status == "stale"
    assert result.spent_usd == Decimal("0.001") and result.reserved_usd == 0
    assert any(step.status == "discarded" for step in result.steps)
    assert not tasks(logged_in, shop)


def test_other_account_cannot_read_change_or_restore_rules(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    shop = create_shop(logged_in)
    rule = save(logged_in, shop)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="outsider", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "outsider", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    for endpoint in [root(shop), root(shop) + "/history", root(shop) + f"/{rule['version']}"]:
        assert logged_in.get(endpoint).status_code == 404
    for action in ["save", "reset", "revoke", "restore"]:
        data: dict[str, Any] = {"expected_version": rule["version"], "action": action}
        if action == "save":
            data["values"] = {}
        if action == "restore":
            data["restore_version"] = rule["version"]
        assert logged_in.post(root(shop), json=data).status_code == 404


def test_concurrent_rule_changes_use_current_read(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    gate = Barrier(2)

    def write() -> str:
        with session_factory() as session:
            owner = session.scalar(select(User.id).where(User.username == "seller"))
            assert owner is not None
            service = BusinessRulesService(UnitOfWork(session))
            gate.wait(timeout=10)
            try:
                service.change(
                    owner,
                    shop,
                    RuleChange(expected_version=0, values={"basis": "Concurrent synthetic rule"}),
                )
                return "saved"
            except ConflictError:
                session.rollback()
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: write(), range(2))) == ["conflict", "saved"]
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
        assert (
            len(BusinessRulesService(UnitOfWork(session)).history(owner, shop, RuleScope(), None))
            == 1
        )
