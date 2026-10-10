from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier, Event
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError, ConflictError
from app.core.time import utc_now
from app.models.agent import AgentExecution, AgentStep
from app.models.identity import User
from app.models.operations import OperationTask
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import AgentAction, ModelDecision, ModelStatus
from app.schemas.identity import AccountInput
from app.services.agent import AgentService
from app.services.agent_model import ModelReply, OpenAIResponsesModel
from app.services.agent_skills import REGISTRY, ControlledSkills, require_skill
from app.services.auth import AuthService
from tests.test_analytics import SCOPE, imported
from tests.test_imports import PRODUCTS, create_shop
from tests.test_inventory import csv
from tests.test_operations import ORDERS
from tests.test_support import MESSAGES, withdraw


def root(shop: int) -> str:
    return f"/api/shops/{shop}/agent/runs"


def start(client: TestClient, shop: int, **fields: Any) -> dict[str, Any]:
    response = client.post(
        root(shop),
        json={
            "request_id": str(uuid4()),
            "scope": SCOPE,
            "goal": "Synthetic operations check",
            **fields,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def act(
    client: TestClient, run: dict[str, Any], action: str = "advance", **fields: Any
) -> dict[str, Any]:
    response = client.post(
        root(run["shop_id"]) + f"/{run['id']}",
        json={"version": run["version"], "action": action, **fields},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_daily_branch_approval_verification_and_dedupe(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    empty = act(logged_in, start(logged_in, shop))
    assert empty["status"] == "succeeded" and empty["reason"] == "no_findings"
    imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, start(logged_in, shop))
    assert run["status"] == "waiting_approval" and run["next_node"] == "propose_tasks"
    assert (
        logged_in.get(f"/api/shops/{shop}/operations/tasks?data_identity=synthetic").json()["items"]
        == []
    )
    run = act(logged_in, act(logged_in, run, "approve"))
    assert run["next_node"] == "verify"
    task_ids = run["result"]["snapshot"]["task_ids"]
    done = act(logged_in, run)
    assert done["status"] == "succeeded" and done["result"]["task_ids"] == task_ids
    assert [s["skill"] for s in done["steps"] if s["skill"]] == ["data_check", "propose_tasks"]
    assert done["spent_usd"] == "0.000000"
    second = act(logged_in, start(logged_in, shop))
    second = act(logged_in, act(logged_in, second, "approve"))
    assert second["result"]["snapshot"]["created_candidates"] == 0
    assert second["result"]["snapshot"]["task_ids"] == task_ids


def test_sources_stale_and_erased_with_independent_results_preserved(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, start(logged_in, shop, goal="Synthetic private task"))
    other = create_shop(logged_in, code="independent")
    independent = act(logged_in, start(logged_in, other))
    batch = withdraw(logged_in, batch, "revoke")
    old = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert old["source_status"] == "stale"
    assert (
        logged_in.post(
            root(shop) + f"/{run['id']}", json={"version": old["version"], "action": "approve"}
        ).status_code
        == 409
    )
    withdraw(logged_in, batch, "clear")
    cleared = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert (
        cleared["source_status"] == "cleared"
        and cleared["input"] is None
        and cleared["result"] is None
    )
    assert all(s["input"] is None and s["output"] is None for s in cleared["steps"])
    assert logged_in.get(root(other) + f"/{independent['id']}").json()["source_status"] == "current"


def test_budgets_pause_resume_cancel_and_reject(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, start(logged_in, shop, budget={"max_steps": 1}))
    run = act(logged_in, act(logged_in, run, "approve"))
    assert run["status"] == "paused" and run["reason"] == "step_budget"
    run = act(logged_in, run, "resume", budget={"max_steps": 4})
    run = act(logged_in, act(logged_in, run))
    assert run["status"] == "succeeded"
    paused = act(logged_in, start(logged_in, shop), "pause")
    assert act(logged_in, paused, "pause")["version"] == paused["version"]
    cancelled = act(logged_in, paused, "cancel")
    assert act(logged_in, cancelled)["status"] == "cancelled"
    rejected = act(logged_in, act(logged_in, start(logged_in, shop)), "reject")
    assert rejected["status"] == "rejected" and rejected["result"]["findings"]


def test_listing_support_and_metrics_skills(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    products = logged_in.get(f"/api/shops/{shop}/listings/products").json()
    product = products[0]
    run = act(
        logged_in, start(logged_in, shop, template="listing", product_id=product["product_id"])
    )
    if not product["facts"]:
        assert run["status"] == "waiting_input"
    else:
        run = act(logged_in, act(logged_in, act(logged_in, run, "approve")))
        assert run["status"] == "succeeded" and run["result"]["record_type"] == "listing"
    imported(logged_in, shop, MESSAGES, "messages")
    messages = logged_in.get(f"/api/shops/{shop}/support/messages").json()
    reply = act(logged_in, start(logged_in, shop, template="support", message_id=messages[0]["id"]))
    reply = act(logged_in, act(logged_in, act(logged_in, reply, "approve")))
    assert (
        reply["result"]["status"] == "human_review" and reply["external_status"] == "not_submitted"
    )
    imported(logged_in, shop, ORDERS, "orders")
    metrics = act(logged_in, start(logged_in, shop, template="analysis"))
    assert metrics["status"] == "succeeded" and metrics["result"]["lines"]


def test_request_scope_csrf_and_missing_inputs(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    run = start(logged_in, shop)
    response = logged_in.post(root(shop), json=run["input"])
    assert response.json()["id"] == run["id"]
    changed = {**run["input"], "template": "analysis"}
    assert logged_in.post(root(shop), json=changed).status_code == 409
    other = create_shop(logged_in, code="other")
    assert logged_in.get(root(other) + f"/{run['id']}").status_code == 404
    assert logged_in.post(root(shop), json={**run["input"], "tool": "refund"}).status_code == 422
    missing = act(logged_in, start(logged_in, shop, template="listing"))
    assert missing["status"] == "blocked" and missing["reason"] == "missing_object"
    logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(shop), json=run["input"]).status_code == 403


def test_registry_denies_missing_metadata_and_risk_escalation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    spec = require_skill("data_check")
    assert spec.input_schema and spec.output_schema and len(REGISTRY) == 12
    with patch.dict(REGISTRY, {"data_check": spec.model_copy(update={"risk": "R3"})}):
        run = act(logged_in, start(logged_in, shop))
    assert run["status"] == "blocked" and run["reason"] == "skill_policy_denied"
    assert len([s for s in run["steps"] if s["skill"]]) == 1
    with patch.dict(REGISTRY, {"data_check": spec.model_copy(update={"tools": []})}):
        run = act(logged_in, start(logged_in, shop))
    assert run["reason"] == "invalid_skill"


def test_transient_reads_stop_after_three_attempts(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    run = start(logged_in, shop)
    error = OperationalError("synthetic", {}, Exception(2013, "synthetic transient"))
    with patch.object(ControlledSkills, "call", side_effect=error) as call:
        for _ in range(3):
            run = act(logged_in, run)
        assert call.call_count == 3
        assert run["status"] == "circuit_open" and run["steps_used"] == 3
        assert act(logged_in, run)["status"] == "circuit_open"
        assert call.call_count == 3


def test_missing_model_and_budget_never_call_network(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    with patch.object(OpenAIResponsesModel, "decide") as call:
        run = act(
            logged_in, start(logged_in, shop, template="natural", goal="今日运营", allow_model=True)
        )
        assert run["status"] == "waiting_configuration" and run["model_status"] == "not_configured"
        assert not call.called
    with (
        patch.object(
            OpenAIResponsesModel,
            "status",
            return_value=ModelStatus(
                status="configured", provider="test_double", model="synthetic", reason=""
            ),
        ),
        patch.object(OpenAIResponsesModel, "reserve", return_value=Decimal("0.01")),
        patch.object(OpenAIResponsesModel, "decide") as call,
    ):
        run = act(logged_in, start(logged_in, shop, template="natural", allow_model=True))
        assert run["status"] == "paused" and run["reason"] == "cost_budget" and not call.called


class FakeModel:
    def __init__(self, intent: str = "daily") -> None:
        self.intent = intent
        self.calls = 0

    def status(self) -> ModelStatus:
        return ModelStatus(
            status="configured", provider="test_double", model="synthetic", reason=""
        )

    def reserve(self, goal: str) -> Decimal:
        return Decimal("0.01")

    def decide(self, goal: str, timeout: float) -> ModelReply:
        self.calls += 1
        if self.intent == "timeout":
            raise BusinessError("model_result_unknown", "synthetic timeout", 502)
        return ModelReply(
            ModelDecision.model_validate({"intent": self.intent}),
            Decimal("0.001"),
            10,
            5,
            "test_double",
        )


@pytest.mark.parametrize(
    "intent,expected", [("daily", "ready"), ("blocked", "blocked"), ("timeout", "result_unknown")]
)
def test_model_intent_hard_stop_and_unknown_cost(
    logged_in: TestClient, session_factory: sessionmaker[Session], intent: str, expected: str
) -> None:
    shop = create_shop(logged_in)
    started = start(
        logged_in, shop, template="natural", allow_model=True, budget={"max_cost_usd": "0.02"}
    )
    fake = FakeModel(intent)
    with session_factory() as session:
        run = AgentService(UnitOfWork(session), fake).act(
            int(session.scalar(select(User.id))),
            shop,
            started["id"],
            AgentAction(version=started["version"], action="advance"),
        )
    assert run.status == expected and fake.calls == 1
    assert run.reserved_usd == (Decimal("0.01") if intent == "timeout" else 0)
    if intent != "timeout":
        assert run.model_status == "test_double" and run.spent_usd == Decimal("0.001")


def test_concurrent_advance_has_one_business_write(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, act(logged_in, start(logged_in, shop)), "approve")
    barrier = Barrier(2)

    def perform() -> str:
        with session_factory() as session:
            barrier.wait()
            try:
                AgentService(UnitOfWork(session), OpenAIResponsesModel(settings)).act(
                    int(session.scalar(select(User.id))),
                    shop,
                    run["id"],
                    AgentAction(version=run["version"], action="advance"),
                )
                return "ok"
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: perform(), range(2))) == ["conflict", "ok"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OperationTask)) == 1


def test_cancel_during_model_releases_locks_discards_result(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    run = start(
        logged_in, shop, template="natural", allow_model=True, budget={"max_cost_usd": "0.02"}
    )
    entered, release = Event(), Event()
    fake = FakeModel()
    original = fake.decide

    def delayed(goal: str, timeout: float) -> ModelReply:
        entered.set()
        assert release.wait(10)
        return original(goal, timeout)

    def perform() -> Any:
        with session_factory() as session:
            return AgentService(UnitOfWork(session), fake).act(
                int(session.scalar(select(User.id))),
                shop,
                run["id"],
                AgentAction(version=run["version"], action="advance"),
            )

    with patch.object(fake, "decide", side_effect=delayed), ThreadPoolExecutor() as pool:
        future = pool.submit(perform)
        assert entered.wait(10)
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        cancelled = act(logged_in, current, "cancel")
        assert cancelled["status"] == "cancelled"
        release.set()
        final = future.result(10)
    assert final.status == "cancelled" and final.spent_usd == Decimal("0.001")
    assert final.steps[-1].status == "cancelled" or any(
        s.status == "discarded" for s in final.steps
    )


def test_atomic_step_failure_rolls_back_business_write(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    run = act(logged_in, act(logged_in, start(logged_in, shop)), "approve")
    with patch.object(
        AgentService, "_dependencies", side_effect=BusinessError("synthetic_block", "synthetic")
    ):
        failed = act(logged_in, run)
    assert failed["status"] == "blocked"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OperationTask)) == 0
        assert (
            session.scalar(
                select(func.count()).select_from(AgentStep).where(AgentStep.status == "failed")
            )
            == 1
        )


def test_expiry_and_elapsed_budget_prevent_next_write(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, csv(), "inventory")
    run = act(logged_in, start(logged_in, shop))
    expires = datetime.fromisoformat(run["result"]["valid_until"]).replace(tzinfo=None)
    with patch("app.services.agent.utc_now", return_value=expires):
        stale = logged_in.get(root(shop) + f"/{run['id']}").json()
        assert stale["source_status"] == "stale"
        assert (
            logged_in.post(
                root(shop) + f"/{run['id']}",
                json={"version": stale["version"], "action": "approve"},
            ).status_code
            == 409
        )
    with session_factory() as session:
        item = session.get(AgentExecution, run["id"])
        item.elapsed_ms = 120000
        session.commit()
    fresh = start(logged_in, shop)
    with session_factory() as session:
        item = session.get(AgentExecution, fresh["id"])
        item.elapsed_ms = 120000
        session.commit()
    exhausted = act(logged_in, fresh)
    assert exhausted["status"] == "paused" and exhausted["reason"] == "time_budget"
    assert exhausted["steps_used"] == 0


def test_crashed_model_lease_stops_replay(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    run = start(logged_in, shop, template="natural", allow_model=True)
    with session_factory() as session:
        item = session.get(AgentExecution, run["id"])
        item.status = "running"
        item.lease_token = str(uuid4())
        item.lease_until = utc_now() - timedelta(seconds=1)
        item.reserved_usd = Decimal("0.01")
        session.commit()
    recovered = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert recovered["status"] == "result_unknown" and recovered["reason"] == "model_lease_expired"
    with patch.object(OpenAIResponsesModel, "decide") as call:
        replay = act(logged_in, recovered)
    assert replay["reserved_usd"] == "0.010000" and not call.called


def test_cross_owner_and_identity_rejected(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[0]
    run = act(
        logged_in,
        start(
            logged_in,
            shop,
            template="listing",
            product_id=product["product_id"],
            scope={**SCOPE, "data_identity": "user_import"},
        ),
    )
    assert run["status"] == "blocked" and run["reason"] == "scope_mismatch"
    assert run["result"] is None and all(s["output"] is None for s in run["steps"])
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="another_seller", password="Synthetic-Another-Password!")
        )
    logged_in.post("/api/auth/logout")
    logged_in.post(
        "/api/auth/login",
        json={"username": "another_seller", "password": "Synthetic-Another-Password!"},
    )
    assert logged_in.get(root(shop) + f"/{run['id']}").status_code == 404
    assert logged_in.get(f"/api/shops/{shop}/agent/skills").status_code == 404


def test_model_result_after_source_change_is_discarded(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    run = start(
        logged_in, shop, template="natural", allow_model=True, budget={"max_cost_usd": "0.02"}
    )
    fake = FakeModel()

    def decide(goal: str, timeout: float) -> ModelReply:
        imported(logged_in, shop, PRODUCTS, "products")
        return ModelReply(ModelDecision(intent="daily"), Decimal("0.001"), 10, 5, "test_double")

    with session_factory() as session, patch.object(fake, "decide", side_effect=decide):
        result = AgentService(UnitOfWork(session), fake).act(
            int(session.scalar(select(User.id))),
            shop,
            run["id"],
            AgentAction(version=run["version"], action="advance"),
        )
    assert result.status == "blocked" and result.source_status == "stale"
    assert result.steps[-1].status == "discarded" and result.spent_usd == Decimal("0.001")


@pytest.mark.parametrize("variant", ["success", "invalid", "no_usage", "incomplete", "redirect"])
def test_provider_protocol_and_secret_safe_errors(settings: Settings, variant: str) -> None:
    configured = settings.model_copy(
        update={
            "model_enabled": True,
            "model_name": "synthetic-model",
            "model_input_usd_per_million": Decimal("1"),
            "model_output_usd_per_million": Decimal("2"),
        }
    )
    from pydantic import SecretStr

    configured.model_api_key = SecretStr("synthetic-test-key-not-real")
    adapter = OpenAIResponsesModel(configured)
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if variant == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid"})
        payload: dict[str, Any] = {
            "status": "completed",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"intent":"daily"}'}],
                }
            ],
        }
        if variant == "invalid":
            payload["output"][0]["content"][0]["text"] = (
                '{"intent":"refund","token":"synthetic-test-key-not-real"}'
            )
        if variant == "no_usage":
            del payload["usage"]
        if variant == "incomplete":
            payload["status"] = "incomplete"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(respond)
    client = httpx.Client(transport=transport)
    with patch("app.services.agent_model.httpx.Client", return_value=client):
        if variant == "success":
            result = adapter.decide("检查今日运营", 2)
            assert result.cost == Decimal("0.000020") and result.decision.intent == "daily"
            assert adapter.reserve("检查今日运营") > result.cost
        else:
            with pytest.raises(BusinessError) as caught:
                adapter.decide("检查今日运营", 2)
            assert caught.value.code == "model_result_unknown"
            assert "synthetic-test-key-not-real" not in caught.value.message
    assert len(calls) == 1 and str(calls[0].url) == "https://api.openai.com/v1/responses"
    import json

    body = json.loads(calls[0].content)
    assert body["store"] is False and "tools" not in body
