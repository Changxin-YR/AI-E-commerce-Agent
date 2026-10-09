import json
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.core.time import utc_now
from app.models.operations import OperationTask
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import ModelStatus
from app.schemas.operations import CheckPreview, OperationScope
from app.services.agent_model import DashScopeChatModel, GenerationReply, OpenAIResponsesModel
from app.services.operation_explanation import operation_request
from tests.test_agent import act, root, start
from tests.test_analytics import SCOPE, imported
from tests.test_dashscope_model import completion, configuration
from tests.test_imports import PRODUCTS, create_shop
from tests.test_inventory import csv
from tests.test_operations import ORDERS, change, tasks
from tests.test_operations import root as operations_root
from tests.test_support import MESSAGES, withdraw


class OperationsDouble:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.content: dict[str, Any] = {"branch_ids": ["branch_2"], "check_ids": []}
        self.unknown = False

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        self.requests.append(request)
        assert request["name"] == "operation_evidence"
        return GenerationReply(
            self.content, None if self.unknown else Decimal("0.001"), 100, 30, "test_double"
        )


@pytest.fixture()
def model() -> Iterator[OperationsDouble]:
    fake = OperationsDouble()
    with (
        patch.object(
            OpenAIResponsesModel,
            "status",
            return_value=ModelStatus(
                status="configured", provider="test_double", model="synthetic", reason=""
            ),
        ),
        patch.object(OpenAIResponsesModel, "reserve_generation", return_value=Decimal("0.01")),
        patch.object(OpenAIResponsesModel, "generate", side_effect=fake.generate),
    ):
        yield fake


def setup(client: TestClient) -> tuple[int, dict[str, Any]]:
    shop = create_shop(client)
    imported(client, shop, PRODUCTS, "products")
    batch = imported(client, shop, ORDERS, "orders")
    imported(client, shop, MESSAGES, "messages")
    imported(client, shop, csv(), "inventory")
    return shop, batch


def begin(client: TestClient, shop: int, **changes: Any) -> dict[str, Any]:
    preview = client.post(operations_root(shop) + "/preview", json=changes.get("scope", SCOPE))
    assert preview.status_code == 200, preview.text
    return start(
        client,
        shop,
        **(
            {
                "template": "daily_model",
                "allow_model": True,
                "allow_operation_data": True,
                "expected_operation_hash": preview.json()["preview_hash"],
                "budget": {"max_cost_usd": "0.03"},
            }
            | changes
        ),
    )


def candidate(client: TestClient, shop: int, **kwargs: Any) -> dict[str, Any]:
    return act(client, act(client, begin(client, shop, **kwargs)))


def save(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    return act(client, act(client, act(client, run, "approve")))


def test_all_branches_approval_readback_dedupe_and_clear(
    logged_in: TestClient,
    model: OperationsDouble,
) -> None:
    shop, batch = setup(logged_in)
    run = candidate(logged_in, shop)
    assert run["status"] == "waiting_approval"
    explanation = run["result"]["explanation"]
    assert len(explanation["branches"]) == 9
    assert explanation["branches"][0]["id"] == "branch_2"
    assert all(item["count"] > 0 for item in explanation["candidate_counts"])
    assert len(explanation["checks"]) == 5
    assert tasks(logged_in, shop) == []
    payload = model.requests[0]["payload"]
    assert set(payload) == {
        "goal",
        "scope",
        "branches",
        "candidate_counts",
        "checks",
        "limitations",
    }
    assert all(set(b) == {"name", "status", "count"} for b in payload["branches"].values())
    assert not any(
        key in json.dumps(payload) for key in ["filename", "row_id", "sku", "O1", "body"]
    )
    done = save(logged_in, run)
    assert done["status"] == "succeeded"
    ids = done["result"]["task_ids"]
    assert len(ids) == len(run["result"]["check"]["findings"])
    task = tasks(logged_in, shop)[0]
    completed = change(logged_in, shop, change(logged_in, shop, task, "approve"), "complete")
    repeated = save(logged_in, candidate(logged_in, shop))
    assert repeated["result"]["task_ids"] == ids
    assert (
        next(t for t in tasks(logged_in, shop) if t["id"] == completed["id"])["status"]
        == "completed"
    )
    history = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert any(
        s["output"] and s["output"].get("explanation") == explanation for s in history["steps"]
    )
    withdraw(logged_in, batch, "clear")
    erased = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert erased["result"] is None and erased["input"] is None
    assert all(s["output"] is None and s["input"] is None for s in erased["steps"])


def test_empty_check_preserves_unknowns_without_write(
    logged_in: TestClient, model: OperationsDouble
) -> None:
    shop = create_shop(logged_in)
    run = candidate(logged_in, shop)
    assert run["status"] == "succeeded" and run["reason"] == "no_findings"
    assert all(b["status"] == "not_checked" for b in run["result"]["explanation"]["branches"])
    assert tasks(logged_in, shop) == []
    assert len(model.requests) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"allow_model": False},
        {"allow_operation_data": False},
        {"expected_operation_hash": None},
        {"expected_operation_hash": "0" * 64},
    ],
)
def test_both_consents_and_snapshot_binding_before_network(
    logged_in: TestClient,
    model: OperationsDouble,
    changes: dict[str, Any],
) -> None:
    shop, _ = setup(logged_in)
    run = candidate(logged_in, shop, **changes)
    assert run["status"] in {"waiting_configuration", "blocked"}
    assert not model.requests


@pytest.mark.parametrize(
    "content",
    [
        {"branch_ids": ["branch_2", "branch_2"], "check_ids": []},
        {"branch_ids": ["unknown"], "check_ids": []},
        {"branch_ids": [], "check_ids": ["coverage", "coverage"]},
        {"branch_ids": [], "check_ids": ["refund"]},
        {"branch_ids": [], "check_ids": [], "next_action": "send"},
        {"branch_ids": [], "check_ids": [], "text": "All healthy"},
    ],
)
def test_invalid_selection_rejected_but_usage_charged(
    logged_in: TestClient,
    model: OperationsDouble,
    content: dict[str, Any],
) -> None:
    shop, _ = setup(logged_in)
    model.content = content
    run = candidate(logged_in, shop)
    assert run["status"] == "blocked" and run["reason"] == "invalid_model_output"
    assert run["spent_usd"] == "0.001000"
    assert tasks(logged_in, shop) == []


@pytest.mark.parametrize("event", ["pause", "cancel", "clear", "replace"])
def test_inflight_changes_discard_body_and_preserve_known_cost(
    logged_in: TestClient,
    model: OperationsDouble,
    event: str,
) -> None:
    shop, batch = setup(logged_in)
    run = act(logged_in, begin(logged_in, shop))

    def interrupted(request: dict[str, Any], timeout: float) -> GenerationReply:
        if event in {"pause", "cancel"}:
            act(logged_in, logged_in.get(root(shop) + f"/{run['id']}").json(), event)
        elif event == "clear":
            withdraw(logged_in, batch, "clear")
        else:
            imported(logged_in, shop, ORDERS.replace("unfulfilled", "fulfilled"), "orders")
        return model.generate(request, timeout)

    with patch.object(OpenAIResponsesModel, "generate", side_effect=interrupted):
        result = act(logged_in, run)
    assert result["status"] in {"paused", "cancelled", "blocked"}
    assert result["spent_usd"] == "0.001000" and result["reserved_usd"] == "0.000000"
    assert not result["result"] or "explanation" not in result["result"]
    if event == "clear":
        assert all(s["input"] is None and s["output"] is None for s in result["steps"])
    assert tasks(logged_in, shop) == []


@pytest.mark.parametrize("when", ["before_model", "before_approval", "after_approval"])
def test_expired_inventory_blocks_all_gates(
    logged_in: TestClient,
    model: OperationsDouble,
    when: str,
) -> None:
    shop, _ = setup(logged_in)
    run = act(logged_in, begin(logged_in, shop))
    if when != "before_model":
        run = act(logged_in, run)
    if when == "after_approval":
        run = act(logged_in, run, "approve")
    later = utc_now() + timedelta(hours=25)
    with (
        patch("app.services.agent.utc_now", return_value=later),
        patch("app.services.operations.utc_now", return_value=later),
    ):
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        assert current["source_status"] == "stale"
        if when == "before_approval":
            assert (
                logged_in.post(
                    root(shop) + f"/{run['id']}",
                    json={"version": current["version"], "action": "approve"},
                ).status_code
                == 409
            )
        else:
            assert act(logged_in, current)["status"] == "blocked"
    assert len(model.requests) == (0 if when == "before_model" else 1)
    assert tasks(logged_in, shop) == []


def test_budget_resume_unknown_fee_no_retry(logged_in: TestClient, model: OperationsDouble) -> None:
    shop, _ = setup(logged_in)
    run = candidate(logged_in, shop, budget={"max_cost_usd": "0"})
    assert run["reason"] == "cost_budget" and not model.requests
    run = act(logged_in, run, "resume", budget={"max_cost_usd": "0.03"})
    model.unknown = True
    result = act(logged_in, run)
    assert result["status"] == "result_unknown" and result["reserved_usd"] == "0.010000"
    assert act(logged_in, result)["status"] == "result_unknown" and len(model.requests) == 1


def test_scope_ownership_and_foreign_snapshot(
    logged_in: TestClient, model: OperationsDouble
) -> None:
    shop, _ = setup(logged_in)
    other = create_shop(logged_in, "other-operations")
    assert logged_in.post(operations_root(999999) + "/preview", json=SCOPE).status_code == 404
    run = begin(logged_in, shop)
    copied = start(logged_in, other, **{k: v for k, v in run["input"].items() if k != "request_id"})
    assert act(logged_in, copied)["status"] == "blocked" and not model.requests


def test_candidate_and_audit_atomic(
    logged_in: TestClient, model: OperationsDouble, session_factory: sessionmaker[Session]
) -> None:
    shop, _ = setup(logged_in)
    run = act(logged_in, candidate(logged_in, shop), "approve")
    original = UnitOfWork.record_event

    def fail(self: UnitOfWork, *args: Any, **kwargs: Any) -> None:
        if args[1] == "operations.proposed":
            raise BusinessError("synthetic_audit_failure", "synthetic")
        original(self, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", new=fail):
        assert act(logged_in, run)["status"] == "blocked"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OperationTask)) == 0


@pytest.mark.parametrize("adapter_class", [OpenAIResponsesModel, DashScopeChatModel])
def test_protocol_with_aggregate_payload(
    logged_in: TestClient, adapter_class: type[OpenAIResponsesModel]
) -> None:
    shop, _ = setup(logged_in)
    prepared = act(logged_in, begin(logged_in, shop))["result"]
    request = operation_request(
        "Review", OperationScope.model_validate(SCOPE), CheckPreview.model_validate(prepared)
    )
    adapter = adapter_class(configuration())
    selected = {"branch_ids": ["branch_2"], "check_ids": ["coverage"]}
    calls: list[httpx.Request] = []

    def respond(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        if adapter_class is DashScopeChatModel:
            return httpx.Response(200, json=completion(json.dumps(selected)))
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {"input_tokens": 100, "output_tokens": 20},
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": json.dumps(selected)}],
                    }
                ],
            },
        )

    with patch(
        "app.services.agent_model.httpx.Client",
        return_value=httpx.Client(transport=httpx.MockTransport(respond)),
    ):
        reply = adapter.generate(request, 2)
    assert reply.content == selected and reply.cost is not None and len(calls) == 1
    body = json.loads(calls[0].content)
    assert "tools" not in body
    if adapter_class is DashScopeChatModel:
        assert body["response_format"]["json_schema"]["strict"]
        payload = json.loads(body["messages"][1]["content"])
    else:
        assert body["text"]["format"]["strict"] and not body["store"]
        payload = json.loads(body["input"])
    assert payload == request["payload"]
