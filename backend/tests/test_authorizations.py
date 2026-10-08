from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.agent import AgentExecution
from app.models.authorizations import AuthorizationUse, InternalAuthorization
from app.models.identity import User
from app.models.operations import OperationTask
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import AgentAction
from app.schemas.identity import AccountInput
from app.services.agent import AgentService
from app.services.agent_skills import ControlledSkills
from app.services.auth import AuthService
from app.services.authorizations import AuthorizationsService
from app.services.listings import digest
from tests.test_agent import FakeModel, act, root, start
from tests.test_analytics import SCOPE, imported
from tests.test_business_rules import save
from tests.test_imports import create_shop
from tests.test_inventory import csv
from tests.test_operations import ORDERS
from tests.test_support import withdraw


def grants(shop: int) -> str:
    return f"/api/shops/{shop}/authorizations"


def create(client: TestClient, run: dict[str, Any], **fields: Any) -> dict[str, Any]:
    result = client.post(
        grants(run["shop_id"]),
        json={
            "request_id": str(uuid4()),
            "execution_id": run["id"],
            "expected_version": run["version"],
            "max_uses": 2,
            "valid_hours": 24,
            "confirmed": True,
            **fields,
        },
    )
    assert result.status_code == 200, result.text
    return result.json()


def setup(client: TestClient) -> tuple[int, dict[str, Any], dict[str, Any]]:
    shop = create_shop(client)
    imported(client, shop, ORDERS, "orders")
    run = act(client, start(client, shop))
    return shop, run, create(client, run)


def test_grant_executes_counts_replay_reuses_and_reverts(logged_in: TestClient) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    run = act(logged_in, run)
    assert run["reason"] == "preauthorization_used"
    completed = act(logged_in, run)
    assert completed["status"] == "succeeded"
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["used_count"] == 1 and len(current["uses"]) == 1
    assert current["uses"][0]["changes"]
    act(logged_in, completed)
    next_run = act(logged_in, start(logged_in, shop, authorization_id=grant["id"]))
    assert next_run["status"] == "ready"
    next_run = act(logged_in, next_run)
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["used_count"] == 2 and current["status"] == "exhausted"
    assert current["uses"][1]["changes"] == [] and current["uses"][1]["reused_count"] > 0
    use = current["uses"][0]
    path = grants(shop) + f"/{grant['id']}/uses/{use['id']}/revert"
    reverted = logged_in.post(path)
    assert reverted.status_code == 200, reverted.text
    assert reverted.json()["used_count"] == 2
    assert logged_in.post(path).json()["uses"][0]["reverted_at"]
    for change in use["changes"]:
        task = logged_in.get(f"/api/shops/{shop}/operations/tasks/{change['task_id']}").json()
        assert task["status"] == "rejected"


def test_revocation_at_write_boundary_falls_back_to_explicit_approval(
    logged_in: TestClient,
) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    path = grants(shop) + f"/{grant['id']}/revoke"
    assert logged_in.post(path, json={"version": grant["version"]}).status_code == 200
    assert logged_in.post(path, json={"version": grant["version"]}).json()["status"] == "revoked"
    latest = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert latest["status"] == "waiting_approval"
    assert latest["reason"] == "authorization_unavailable"
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["used_count"] == 0
    manual = act(logged_in, act(logged_in, latest, "approve"))
    assert manual["next_node"] == "verify" and manual["authorization_id"] is None
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["uses"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("channel", "shopify"),
        ("data_identity", "user_import"),
        ("max_age_hours", 25),
        ("max_margin_percent", "21"),
    ],
)
def test_scope_mismatch_is_rejected(logged_in: TestClient, field: str, value: Any) -> None:
    shop, _, grant = setup(logged_in)
    response = logged_in.post(
        root(shop),
        json={
            "request_id": str(uuid4()),
            "authorization_id": grant["id"],
            "scope": {**SCOPE, field: value},
        },
    )
    assert response.status_code in {409, 422}


def test_source_change_and_erasure_invalidate_grant(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, start(logged_in, shop))
    grant = create(logged_in, run)
    withdraw(logged_in, batch, "clear")
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["status"] == "source_changed"
    assert "Synthetic" not in str(current)
    assert (
        logged_in.post(
            root(shop),
            json={"request_id": str(uuid4()), "scope": SCOPE, "authorization_id": grant["id"]},
        ).status_code
        == 409
    )


def test_expiry_and_atomic_failed_write(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    with patch.object(
        AuthorizationsService, "consume", side_effect=ConflictError("Synthetic failure")
    ):
        failed = act(logged_in, run)
    assert failed["status"] == "blocked"
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["used_count"] == 0
    assert (
        logged_in.get(f"/api/shops/{shop}/operations/tasks?data_identity=synthetic").json()["items"]
        == []
    )
    with session_factory() as session:
        row = session.get(InternalAuthorization, grant["id"])
        assert row
        row.expires_at = utc_now() - timedelta(seconds=1)
        session.commit()
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["status"] == "expired"


def test_changed_candidate_blocks_entire_revert(logged_in: TestClient) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, act(logged_in, run, "use_authorization", authorization_id=grant["id"]))
    grant = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    use = grant["uses"][0]
    change = use["changes"][-1]
    path = f"/api/shops/{shop}/operations/tasks/{change['task_id']}"
    assert (
        logged_in.post(path, json={"version": change["version"], "action": "approve"}).status_code
        == 200
    )
    assert (
        logged_in.post(grants(shop) + f"/{grant['id']}/uses/{use['id']}/revert").status_code == 409
    )
    assert logged_in.get(path).json()["status"] == "open"
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["uses"][0]["reverted_at"] is None


def test_create_replay_whitelist_isolation_and_limits(logged_in: TestClient) -> None:
    shop, run, grant = setup(logged_in)
    request_id = str(uuid4())
    same = create(logged_in, run, request_id=request_id)
    assert create(logged_in, run, request_id=request_id)["id"] == same["id"]
    other = create_shop(logged_in, code="other")
    assert logged_in.get(grants(other) + f"/{grant['id']}").status_code == 404
    for extra in [
        {"skill": "send_email"},
        {"max_uses": 0},
        {"max_uses": 21},
        {"valid_hours": 169},
        {"confirmed": False},
        {"confirmed": 1},
        {"confirmed": "true"},
        {"auto_send": True},
    ]:
        response = logged_in.post(
            grants(shop),
            json={
                "request_id": str(uuid4()),
                "execution_id": run["id"],
                "expected_version": run["version"],
                "max_uses": 2,
                "valid_hours": 1,
                "confirmed": True,
                **extra,
            },
        )
        assert response.status_code == 422, response.text


def test_two_executions_compete_for_last_use(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    first = act(logged_in, start(logged_in, shop))
    grant = create(logged_in, first, max_uses=1)
    first = act(logged_in, first, "use_authorization", authorization_id=grant["id"])
    second = act(logged_in, start(logged_in, shop, authorization_id=grant["id"]))
    barrier = Barrier(2)

    def perform(run: dict[str, Any]) -> str:
        with session_factory() as session:
            owner = int(session.scalar(select(User.id)))  # Establish an old RR snapshot first.
            barrier.wait()
            try:
                AgentService(UnitOfWork(session), FakeModel()).act(
                    owner, shop, run["id"], AgentAction(action="advance", version=run["version"])
                )
                return "ok"
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(perform, [first, second])) == ["conflict", "ok"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuthorizationUse)) == 1
        assert session.scalar(select(func.count()).select_from(OperationTask)) == 1
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["used_count"] == 1


def test_rules_change_and_paused_revocation_stop_old_node(logged_in: TestClient) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    run = act(logged_in, run, "pause")
    save(logged_in, shop, min_quantity=2)
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["status"] == "rules_changed"
    latest = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert (
        logged_in.post(
            root(shop) + f"/{run['id']}", json={"version": latest["version"], "action": "resume"}
        ).status_code
        == 409
    )
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["used_count"] == 0


def test_inventory_preview_binds_freshness_and_whole_write_rollback(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv(), "inventory")
    run = act(logged_in, start(logged_in, shop))
    grant = create(logged_in, run)
    assert grant["source_valid_until"] is not None
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    # Fail after the business save AND consumption, verifying both roll back together.
    with patch.object(
        AgentService, "_dependencies", side_effect=ConflictError("Synthetic failure")
    ):
        assert act(logged_in, run)["status"] == "blocked"
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["used_count"] == 0 and current["uses"] == []
    assert (
        logged_in.get(f"/api/shops/{shop}/operations/tasks?data_identity=synthetic").json()["items"]
        == []
    )


def test_expiry_during_business_save_rolls_back_all(logged_in: TestClient) -> None:
    shop, run, grant = setup(logged_in)
    run = act(logged_in, run, "use_authorization", authorization_id=grant["id"])
    original = ControlledSkills.call
    expired = False
    now = utc_now()

    def late_call(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal expired
        result = original(*args, **kwargs)
        expired = True
        return result

    def clock() -> Any:
        return now + timedelta(days=2) if expired else now

    with (
        patch.object(ControlledSkills, "call", side_effect=late_call, autospec=True),
        patch("app.services.authorizations.utc_now", side_effect=clock),
    ):
        assert act(logged_in, run)["status"] == "blocked"
    current = logged_in.get(grants(shop) + f"/{grant['id']}").json()
    assert current["used_count"] == 0 and current["uses"] == []
    assert (
        logged_in.get(f"/api/shops/{shop}/operations/tasks?data_identity=synthetic").json()["items"]
        == []
    )


def test_previous_unbound_request_hash_remains_replayable(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    run = start(logged_in, shop)
    with session_factory() as session:
        row = session.get(AgentExecution, run["id"])
        assert row and row.input
        old_input = {key: value for key, value in row.input.items() if key != "authorization_id"}
        row.request_hash = digest([shop, old_input])
        row.input = old_input
        session.commit()
    replay = logged_in.post(root(shop), json=run["input"])
    assert replay.status_code == 200 and replay.json()["id"] == run["id"]


def test_cross_owner_and_csrf_cannot_manage_authorization(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop, _, grant = setup(logged_in)
    with session_factory() as session:
        other = AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other-auth-seller", password="Synthetic-Other-Password-2026!")
        )
        with pytest.raises(NotFoundError):
            AuthorizationsService(UnitOfWork(session)).get(other, shop, grant["id"])
    csrf = logged_in.headers.pop("X-CSRF-Token")
    assert (
        logged_in.post(
            grants(shop) + f"/{grant['id']}/revoke", json={"version": grant["version"]}
        ).status_code
        == 403
    )
    logged_in.headers["X-CSRF-Token"] = csrf
    assert logged_in.get(grants(shop) + f"/{grant['id']}").json()["status"] == "active"


def test_other_templates_cannot_receive_internal_grant(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, run, _ = setup(logged_in)
    with session_factory() as session:
        row = session.get(AgentExecution, run["id"])
        assert row
        row.template = "natural"
        session.commit()
    response = logged_in.post(
        grants(shop),
        json={
            "request_id": str(uuid4()),
            "execution_id": run["id"],
            "expected_version": run["version"],
            "max_uses": 1,
            "valid_hours": 1,
            "confirmed": True,
        },
    )
    assert response.status_code == 409
