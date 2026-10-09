import json
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.core.time import utc_now
from app.models.support import ReplyDraft
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import ModelStatus
from app.schemas.support import SupportPreparation
from app.services.agent_model import DashScopeChatModel, GenerationReply, OpenAIResponsesModel
from app.services.support_composition import support_request
from tests.test_agent import act, root, start
from tests.test_analytics import SCOPE, imported
from tests.test_dashscope_model import completion, configuration
from tests.test_imports import ORDERS, create_shop
from tests.test_support import generation, policy, setup, withdraw
from tests.test_support import root as support_root

FAQ = "message_id,sent_at,body,language,order_id\nFAQ,2026-10-08T01:00:00Z,How to clean?,en,\n"


class SupportDouble:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.content: dict[str, Any] | None = None
        self.unknown = False

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        self.requests.append(request)
        assert request["name"] == "support_composition"
        payload = request["payload"]
        return GenerationReply(
            self.content
            if self.content is not None
            else {
                "intent_ids": payload["local_intents"],
                "fact_ids": list(payload["facts"])[::-1],
                "policy_ids": list(payload["policies"]),
                "next_action": "offer_draft",
            },
            None if self.unknown else Decimal("0.001"),
            100,
            30,
            "test_double",
        )


@pytest.fixture()
def model() -> Iterator[SupportDouble]:
    fake = SupportDouble()
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


def begin(
    client: TestClient,
    shop: int,
    message: int,
    policies: list[int] | None = None,
    verified: bool = False,
    **changes: Any,
) -> dict[str, Any]:
    return start(
        client,
        shop,
        **(
            {
                "template": "support_model",
                "message_id": message,
                "support_context": generation(client, shop, message, verified, policies),
                "allow_model": True,
                "allow_support_data": True,
                "budget": {"max_cost_usd": "0.03"},
            }
            | changes
        ),
    )


def candidate(client: TestClient, shop: int, message: int, **kwargs: Any) -> dict[str, Any]:
    return act(client, act(client, begin(client, shop, message, **kwargs)))


def save(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    return act(client, act(client, act(client, run, "approve")))


def test_faq_approval_readback_manual_edit_dedupe_and_policy_clear(
    logged_in: TestClient,
    model: SupportDouble,
) -> None:
    shop, _, message = setup(logged_in, FAQ)
    p = policy(logged_in, shop, code="faq", topic="faq", text="Hand wash only.")
    run = candidate(logged_in, shop, message, policies=[p["id"]])
    assert run["status"] == "waiting_approval" and run["reason"] == "support_candidate_ready"
    assert "Hand wash only." in run["result"]["candidate"]["reply"]
    assert logged_in.get(support_root(shop) + "/drafts").json() == []
    payload = model.requests[0]["payload"]
    assert set(payload) == {
        "goal",
        "message",
        "language",
        "facts",
        "policies",
        "local_intents",
        "review_reasons",
    }
    assert not any(
        key in json.dumps(payload) for key in ["filename", "source_row_id", "order_id", "sku"]
    )
    done = save(logged_in, run)
    assert done["status"] == "succeeded" and done["result"]["status"] == "draft"
    draft_id = done["result"]["record_id"]
    edited = logged_in.post(
        support_root(shop) + f"/drafts/{draft_id}/edit",
        json={"expected_version": 1, "reply": "Human-reviewed response."},
    )
    assert edited.status_code == 200
    repeated = save(logged_in, candidate(logged_in, shop, message, policies=[p["id"]]))
    assert repeated["result"]["record_id"] == draft_id
    assert (
        logged_in.get(support_root(shop) + f"/drafts/{draft_id}").json()["snapshot"]["reply"]
        == "Human-reviewed response."
    )
    assert (
        logged_in.post(support_root(shop) + f"/policies/{p['id']}/clear", json={}).status_code
        == 200
    )
    erased = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert erased["input"] is None and erased["result"] is None
    assert all(s["input"] is None and s["output"] is None for s in erased["steps"])
    assert logged_in.get(support_root(shop) + f"/drafts/{draft_id}").json()["snapshot"] is None


def test_mixed_intents_cannot_downgrade_handoff_or_infer_identity(
    logged_in: TestClient,
    model: SupportDouble,
) -> None:
    shop, _, message = setup(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    p = policy(logged_in, shop)
    model.content = {
        "intent_ids": ["faq"],
        "fact_ids": ["identity", "tracking", "permissions"],
        "policy_ids": [],
        "next_action": "offer_draft",
    }
    run = candidate(logged_in, shop, message, policies=[p["id"]])
    snapshot = run["result"]["candidate"]
    assert run["reason"] == "support_handoff"
    assert snapshot["intents"] == ["shipping", "refund", "faq"]
    assert not snapshot["order_verified"] and snapshot["orders"] == []
    assert "no refund has been confirmed" in snapshot["reply"]
    assert "cannot verify the current tracking" in snapshot["reply"]
    assert save(logged_in, run)["result"]["status"] == "human_review"


@pytest.mark.parametrize(
    "change",
    [
        {"allow_model": False},
        {"allow_support_data": False},
        {"support_context": None},
        {"support_context": {"expected_source_row_id": 999999}},
        {"scope": SCOPE | {"data_identity": "user_import"}},
        {"scope": SCOPE | {"channel": "amazon"}},
    ],
)
def test_consent_source_and_scope_before_network(
    logged_in: TestClient, model: SupportDouble, change: dict[str, Any]
) -> None:
    shop, _, message = setup(logged_in)
    run = act(logged_in, act(logged_in, begin(logged_in, shop, message, **change)))
    assert run["status"] in {"blocked", "waiting_configuration"}
    assert model.requests == []


@pytest.mark.parametrize(
    "change",
    [
        {"intent_ids": ["refund", "refund"]},
        {"intent_ids": ["identity_verified"]},
        {"fact_ids": ["identity", "identity", "permissions"]},
        {"fact_ids": ["identity", "tracking", "invented"]},
        {"policy_ids": ["policy_999"]},
        {"next_action": "send"},
        {"reply": "Refund issued."},
    ],
)
def test_untrusted_selection_blocked_with_known_cost(
    logged_in: TestClient, model: SupportDouble, change: dict[str, Any]
) -> None:
    shop, _, message = setup(logged_in)
    model.content = {
        "intent_ids": ["refund"],
        "fact_ids": ["identity", "tracking", "permissions"],
        "policy_ids": [],
        "next_action": "handoff",
    } | change
    run = candidate(logged_in, shop, message)
    assert run["reason"] == "invalid_model_output" and run["spent_usd"] == "0.001000"
    assert logged_in.get(support_root(shop) + "/drafts").json() == []


@pytest.mark.parametrize("event", ["cancel", "pause", "clear", "policy"])
def test_inflight_changes_discard_candidate(
    logged_in: TestClient, model: SupportDouble, event: str
) -> None:
    shop, batch, message = setup(logged_in)
    p = policy(logged_in, shop)
    run = act(logged_in, begin(logged_in, shop, message, [p["id"]]))

    def interrupted(request: dict[str, Any], timeout: float) -> GenerationReply:
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        if event in {"cancel", "pause"}:
            act(logged_in, current, event)
        elif event == "clear":
            withdraw(logged_in, batch, "clear")
        else:
            policy(logged_in, shop, p["id"], text="Changed policy.")
        return model.generate(request, timeout)

    with patch.object(OpenAIResponsesModel, "generate", side_effect=interrupted):
        result = act(logged_in, run)
    assert result["status"] in {"cancelled", "paused", "blocked"}
    assert result["spent_usd"] == "0.001000" and result["reserved_usd"] == "0.000000"
    assert not result["result"] or "candidate" not in result["result"]
    if event == "clear":
        assert all(s["output"] is None and s["input"] is None for s in result["steps"])


def test_verified_orders_remain_local_and_source_change_blocks(
    logged_in: TestClient, model: SupportDouble
) -> None:
    shop, _, message = setup(logged_in)
    order_batch = imported(logged_in, shop, ORDERS, "orders")
    run = candidate(logged_in, shop, message, verified=True)
    assert run["result"]["candidate"]["order_verified"]
    assert len(run["result"]["candidate"]["orders"]) == 2
    assert "人工核验" in model.requests[0]["payload"]["facts"]["identity"]
    assert "O1" not in json.dumps(model.requests[0]["payload"])
    withdraw(logged_in, order_batch, "clear")
    assert logged_in.get(root(shop) + f"/{run['id']}").json()["result"] is None


def test_policy_conflicts_cannot_be_hidden_by_selection(
    logged_in: TestClient, model: SupportDouble
) -> None:
    shop, _, message = setup(logged_in, FAQ)
    p = policy(logged_in, shop, code="faq1", topic="faq")
    policy(logged_in, shop, code="faq2", topic="faq")
    run = candidate(logged_in, shop, message, policies=[p["id"]])
    assert run["reason"] == "support_handoff"
    assert "FAQ states" not in run["result"]["candidate"]["reply"]


def test_unknown_cost_stops_repeat_and_budget_can_resume(
    logged_in: TestClient, model: SupportDouble
) -> None:
    shop, _, message = setup(logged_in)
    run = act(
        logged_in, act(logged_in, begin(logged_in, shop, message, budget={"max_cost_usd": "0"}))
    )
    assert run["reason"] == "cost_budget" and model.requests == []
    run = act(logged_in, run, "resume", budget={"max_cost_usd": "0.03"})
    model.unknown = True
    result = act(logged_in, run)
    assert result["status"] == "result_unknown" and result["reserved_usd"] == "0.010000"
    assert act(logged_in, result)["status"] == "result_unknown" and len(model.requests) == 1


def test_cross_shop_message_cannot_enter_model(logged_in: TestClient, model: SupportDouble) -> None:
    shop, _, message = setup(logged_in)
    other = create_shop(logged_in, "other-model-shop")
    run = begin(logged_in, shop, message)
    stolen = start(logged_in, other, **{k: v for k, v in run["input"].items() if k != "request_id"})
    assert act(logged_in, stolen)["status"] == "blocked" and model.requests == []


def test_save_and_audit_are_atomic(
    logged_in: TestClient, model: SupportDouble, session_factory: sessionmaker[Session]
) -> None:
    shop, _, message = setup(logged_in)
    approved = act(logged_in, candidate(logged_in, shop, message), "approve")
    original = UnitOfWork.record_event

    def fail(self: UnitOfWork, *args: Any, **kwargs: Any) -> None:
        if args[1] == "support.model_candidate_saved":
            raise BusinessError("synthetic_audit_failure", "synthetic")
        original(self, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", new=fail):
        result = act(logged_in, approved)
    assert result["status"] == "blocked"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReplyDraft)) == 0


@pytest.mark.parametrize("when", ["before_model", "before_approval", "after_approval"])
def test_policy_expiration_rechecked_at_each_gate(
    logged_in: TestClient, model: SupportDouble, when: str
) -> None:
    shop, _, message = setup(logged_in, FAQ)
    boundary = utc_now() + timedelta(minutes=5)
    p = policy(logged_in, shop, topic="faq", valid_until=boundary.isoformat() + "Z")
    run = act(logged_in, begin(logged_in, shop, message, [p["id"]]))
    if when != "before_model":
        run = act(logged_in, run)
    if when == "after_approval":
        run = act(logged_in, run, "approve")
    with (
        patch("app.services.agent.utc_now", return_value=boundary),
        patch("app.services.support.utc_now", return_value=boundary),
    ):
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        assert current["source_status"] == "stale"
        if when == "before_approval":
            response = logged_in.post(
                root(shop) + f"/{run['id']}",
                json={"version": current["version"], "action": "approve"},
            )
            assert response.status_code == 409
        else:
            assert act(logged_in, current)["status"] == "blocked"
    assert len(model.requests) == (0 if when == "before_model" else 1)
    assert logged_in.get(support_root(shop) + "/drafts").json() == []


@pytest.mark.parametrize("body,language", [("如何清洗？", "zh"), ("Nettoyage?", "und")])
def test_language_and_model_handoff(
    logged_in: TestClient, model: SupportDouble, body: str, language: str
) -> None:
    shop, _, message = setup(
        logged_in, FAQ.replace("How to clean?", body).replace(",en,", f",{language},")
    )
    run = candidate(logged_in, shop, message)
    snapshot = run["result"]["candidate"]
    assert run["reason"] == "support_handoff"
    assert ("感谢您的来信" in snapshot["reply"]) if language == "zh" else snapshot["reply"] == ""


def test_model_can_add_semantic_intent_but_cannot_grant_tools(
    logged_in: TestClient, model: SupportDouble
) -> None:
    shop, _, message = setup(logged_in, FAQ)
    p = policy(logged_in, shop, topic="faq", code="faq", text="Wash by hand.")
    model.content = {
        "intent_ids": ["faq", "refund"],
        "fact_ids": ["identity", "tracking", "permissions"],
        "policy_ids": ["policy_1"],
        "next_action": "offer_draft",
    }
    run = candidate(logged_in, shop, message, policies=[p["id"]])
    assert run["reason"] == "support_handoff"
    assert "no refund has been confirmed" in run["result"]["candidate"]["reply"]
    assert run["external_status"] == "not_submitted"


@pytest.mark.parametrize("adapter_class", [OpenAIResponsesModel, DashScopeChatModel])
def test_support_protocol_uses_only_authorized_payload(
    logged_in: TestClient, adapter_class: type[OpenAIResponsesModel]
) -> None:
    shop, _, message = setup(logged_in)
    prepared = act(logged_in, begin(logged_in, shop, message))["result"]
    request = support_request("Review all intents", SupportPreparation.model_validate(prepared))
    adapter = adapter_class(
        configuration().model_copy(update={"model_api_key": SecretStr("synthetic")})
    )
    selected = {
        "intent_ids": ["shipping", "refund"],
        "fact_ids": ["identity", "tracking", "permissions"],
        "policy_ids": [],
        "next_action": "handoff",
    }
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
    body = json.loads(calls[0].content)
    assert reply.content == selected and reply.cost is not None
    assert "tools" not in body and len(calls) == 1
    if adapter_class is DashScopeChatModel:
        assert body["response_format"]["json_schema"]["strict"]
        payload = json.loads(body["messages"][1]["content"])
    else:
        assert body["text"]["format"]["strict"] and not body["store"]
        payload = json.loads(body["input"])
    assert payload == request["payload"]
