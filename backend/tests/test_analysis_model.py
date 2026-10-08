import json
from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError
from app.models.agent import AgentExecution
from app.models.analytics import AnalysisTodo, SavedAnalysis
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import ModelStatus
from app.services.agent_model import GenerationReply, OpenAIResponsesModel
from app.services.analysis_explanation import question_request
from tests.test_agent import act, root, start
from tests.test_analytics import ROWS, imported, setup_data
from tests.test_imports import create_shop
from tests.test_support import withdraw


class ModelDouble:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.intent = "low_margin"
        self.content: dict[str, Any] | None = None
        self.unknown = False

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        self.requests.append(request)
        if self.unknown:
            return GenerationReply(None, None)
        if request["name"] == "analysis_question":
            value = {"intent": self.intent}
        else:
            value = self.content or {
                "fact_ids": list(request["payload"]["facts"])[:8],
                "check_ids": ["fees", "cost_basis"],
                "next_action": "offer_todo",
            }
        return GenerationReply(value, Decimal("0.001"), 100, 30, "test_double")


@pytest.fixture()
def model() -> Iterator[ModelDouble]:
    fake = ModelDouble()
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


def question(client: TestClient, shop: int, **values: Any) -> dict[str, Any]:
    return start(
        client,
        shop,
        template="question",
        allow_model=True,
        allow_analysis_data=True,
        budget={"max_cost_usd": "0.03"},
        **values,
    )


def explanation(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    return act(client, act(client, act(client, run)))


def test_question_explains_then_approves_saves_verifies_and_deduplicates(
    logged_in: TestClient, model: ModelDouble, session_factory: sessionmaker[Session]
) -> None:
    shop, _, _ = setup_data(logged_in)
    run = explanation(logged_in, question(logged_in, shop))
    assert run["status"] == "waiting_approval" and run["next_node"] == "analysis_todo"
    assert run["spent_usd"] == "0.002000" and run["reserved_usd"] == "0.000000"
    report = run["result"]["analysis"]
    assert report["summary"]["gross_profit"] == "27.5950"
    observations = run["result"]["explanation"]["observations"]
    assert observations[0]["fact_id"] == "coverage" and observations[-1]["fact_id"] == "fees"
    assert "27.5950" in str(observations)
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []
    payload = model.requests[-1]["payload"]
    assert "sku" not in payload["facts"]["totals"] and "lines" not in payload
    assert "order_id" not in json.dumps(payload) and "filename" not in json.dumps(payload)
    done = act(logged_in, act(logged_in, act(logged_in, run, "approve")))
    assert done["status"] == "succeeded" and done["result"]["record_type"] == "analysis"
    saved_id = done["result"]["record_id"]
    saved = logged_in.get(f"/api/shops/{shop}/analytics/saved/{saved_id}").json()
    assert saved["snapshot"]["summary"] == report["summary"] and saved["todo"]["status"] == "open"
    repeat = explanation(logged_in, question(logged_in, shop))
    assert repeat["result"]["analysis"]["lines"] == report["lines"]
    repeated = act(logged_in, act(logged_in, act(logged_in, repeat, "approve")))
    assert repeated["result"]["record_id"] == saved_id
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AnalysisTodo)) == 1
    calls = len(model.requests)
    replay = logged_in.post(root(shop), json=done["input"])
    assert replay.json()["id"] == done["id"]
    assert act(logged_in, done)["status"] == "succeeded" and len(model.requests) == calls


@pytest.mark.parametrize("intent", ["sales", "summary", "unsupported"])
def test_question_routes_only_supported_intents(
    logged_in: TestClient, model: ModelDouble, intent: str
) -> None:
    shop, _, _ = setup_data(logged_in)
    model.intent = intent
    run = act(logged_in, question(logged_in, shop))
    if intent == "unsupported":
        assert run["reason"] == "unsupported_analysis" and run["status"] == "blocked"
        assert run["result"] is None and len(model.requests) == 1
    else:
        model.content = {"fact_ids": ["totals"], "check_ids": [], "next_action": "finish"}
        run = act(logged_in, act(logged_in, run))
        assert (
            run["status"] == "succeeded" and run["result"]["analysis"]["scope"]["intent"] == intent
        )


def test_missing_cost_and_empty_data_never_get_exact_ranking(
    logged_in: TestClient, model: ModelDouble
) -> None:
    shop = create_shop(logged_in)
    for has_orders in (False, True):
        if has_orders:
            imported(logged_in, shop, ROWS, "orders")
        run = explanation(logged_in, question(logged_in, shop))
        assert not run["result"]["analysis"]["ranking_available"]
        assert run["result"]["analysis"]["summary"]["gross_profit"] is None
        assert "数据不足" in run["result"]["explanation"]["observations"][0]["text"]
        assert not any(key.startswith("item_") for key in model.requests[-1]["payload"]["facts"])


@pytest.mark.parametrize(
    "value",
    [
        {"fact_ids": ["invented"], "check_ids": ["fees"], "next_action": "offer_todo"},
        {"fact_ids": ["totals"], "check_ids": ["send_mail"], "next_action": "offer_todo"},
        {"fact_ids": ["totals", "totals"], "check_ids": [], "next_action": "finish"},
        {"fact_ids": ["totals"], "check_ids": [], "next_action": "offer_todo"},
        {"fact_ids": ["totals"], "check_ids": [], "next_action": "finish", "profit": "999"},
    ],
)
def test_fabricated_output_blocked_but_known_usage_recorded(
    logged_in: TestClient, model: ModelDouble, value: dict[str, Any]
) -> None:
    shop, _, _ = setup_data(logged_in)
    model.content = value
    run = explanation(logged_in, question(logged_in, shop))
    assert run["status"] == "blocked" and run["reason"] == "invalid_model_output"
    assert run["spent_usd"] == "0.002000" and run["reserved_usd"] == "0.000000"
    assert "explanation" not in run["steps"][-1]["output"]
    assert run["result"]["summary"]["gross_profit"] == "27.5950"


def test_consent_and_budget_gate_each_call(logged_in: TestClient, model: ModelDouble) -> None:
    shop, _, _ = setup_data(logged_in)
    denied = start(
        logged_in, shop, template="question", allow_model=True, budget={"max_cost_usd": "1"}
    )
    assert act(logged_in, denied)["reason"] == "analysis_consent_required"
    assert model.requests == []
    run = start(
        logged_in,
        shop,
        template="question",
        allow_model=True,
        allow_analysis_data=True,
        budget={"max_cost_usd": "0.010000"},
    )
    run = explanation(logged_in, run)
    assert run["status"] == "paused" and run["reason"] == "cost_budget"
    assert len(model.requests) == 1 and run["result"]["lines"]
    run = act(logged_in, run, "resume", budget={"max_cost_usd": "0.03"})
    run = act(logged_in, run)
    assert run["status"] == "waiting_approval" and len(model.requests) == 2


def test_unknown_fee_stops_replay(logged_in: TestClient, model: ModelDouble) -> None:
    shop = create_shop(logged_in)
    model.unknown = True
    run = act(logged_in, question(logged_in, shop))
    assert run["status"] == "result_unknown" and run["reserved_usd"] == "0.010000"
    assert act(logged_in, run)["status"] == "result_unknown" and len(model.requests) == 1


@pytest.mark.parametrize("change", ["pause", "cancel", "clear", "source"])
def test_inflight_change_discards_text_keeps_cost_and_never_restores_erased_data(
    logged_in: TestClient, model: ModelDouble, change: str
) -> None:
    shop, _, batch = setup_data(logged_in)
    run = act(logged_in, act(logged_in, question(logged_in, shop)))

    def generate(request: dict[str, Any], timeout: float) -> GenerationReply:
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        if change in {"pause", "cancel"}:
            act(logged_in, current, change)
        elif change == "clear":
            withdraw(logged_in, batch, "clear")
        else:
            withdraw(logged_in, batch, "revoke")
        return model.generate(request, timeout)

    with patch.object(OpenAIResponsesModel, "generate", side_effect=generate):
        result = act(logged_in, run)
    assert result["spent_usd"] == "0.002000" and result["reserved_usd"] == "0.000000"
    assert any(step["status"] == "discarded" for step in result["steps"])
    assert "explanation" not in str(result)
    if change == "clear":
        assert result["source_status"] == "cleared" and result["result"] is None
        assert all(s["input"] is None and s["output"] is None for s in result["steps"])


def test_approval_atomicity_and_stale_source(
    logged_in: TestClient, model: ModelDouble, session_factory: sessionmaker[Session]
) -> None:
    shop, _, batch = setup_data(logged_in)
    run = explanation(logged_in, question(logged_in, shop))
    approved = act(logged_in, run, "approve")
    original = UnitOfWork.record_event

    def reject_event(self: UnitOfWork, *args: Any, **kwargs: Any) -> None:
        if args[1] == "analysis.todo_created":
            raise BusinessError("synthetic_audit_failure", "synthetic")
        original(self, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", new=reject_event):
        failed = act(logged_in, approved)
    assert failed["status"] == "blocked"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SavedAnalysis)) == 0
        assert session.scalar(select(func.count()).select_from(AnalysisTodo)) == 0
    fresh = explanation(logged_in, question(logged_in, shop))
    withdraw(logged_in, batch, "revoke")
    stale = logged_in.get(root(shop) + f"/{fresh['id']}").json()
    assert (
        logged_in.post(
            root(shop) + f"/{fresh['id']}",
            json={"version": stale["version"], "action": "approve"},
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "variant",
    [
        "valid",
        "refusal",
        "incomplete",
        "invalid_json",
        "no_usage",
        "bool_usage",
        "timeout",
        "redirect",
        "too_large",
        "array_body",
    ],
)
def test_generation_protocol_and_charge_classification(settings: Settings, variant: str) -> None:
    configured = settings.model_copy(
        update={
            "model_enabled": True,
            "model_name": "synthetic",
            "model_api_key": SecretStr("synthetic-no-real-key"),
            "model_input_usd_per_million": Decimal(1),
            "model_output_usd_per_million": Decimal(2),
        }
    )
    adapter = OpenAIResponsesModel(configured)
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if variant == "timeout":
            raise httpx.ReadTimeout("synthetic")
        if variant == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid"})
        if variant == "too_large":
            return httpx.Response(200, content=b"x" * 200001)
        if variant == "array_body":
            return httpx.Response(200, json=[])
        payload: dict[str, Any] = {
            "status": "completed",
            "usage": {"input_tokens": 10, "output_tokens": 5},
            "output": [
                {
                    "type": "message",
                    "content": [{"type": "output_text", "text": '{"intent":"summary"}'}],
                }
            ],
        }
        if variant == "refusal":
            payload["output"][0]["content"][0] = {"type": "refusal", "refusal": "synthetic"}
        if variant == "incomplete":
            payload["status"] = "incomplete"
        if variant == "invalid_json":
            payload["output"][0]["content"][0]["text"] = "<private untrusted response>"
        if variant == "no_usage":
            del payload["usage"]
        if variant == "bool_usage":
            payload["usage"]["input_tokens"] = True
        return httpx.Response(200, json=payload)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    request = question_request("synthetic question", {})
    with patch("app.services.agent_model.httpx.Client", return_value=client) as factory:
        result = adapter.generate(request, 2)
    assert len(calls) == 1 and str(calls[0].url) == "https://api.openai.com/v1/responses"
    assert factory.call_args.kwargs["trust_env"] is False
    assert factory.call_args.kwargs["follow_redirects"] is False
    body = json.loads(calls[0].content)
    assert body["store"] is False and body["max_output_tokens"] == 768 and "tools" not in body
    assert body["text"]["format"]["strict"] is True
    known = variant in {"valid", "refusal", "incomplete", "invalid_json"}
    assert result.cost == (Decimal("0.000020") if known else None)
    assert (result.content is not None) == (variant == "valid")
    assert adapter.reserve_generation(request) > Decimal("0.000020")


def test_expired_generation_lease_does_not_send_again(
    logged_in: TestClient, model: ModelDouble, session_factory: sessionmaker[Session]
) -> None:
    from datetime import timedelta

    from app.core.time import utc_now

    run = question(logged_in, create_shop(logged_in))
    with session_factory() as session:
        row = session.get(AgentExecution, run["id"])
        row.status, row.lease_token = "running", "synthetic-lease"
        row.lease_until = utc_now() - timedelta(seconds=1)
        row.reserved_usd = Decimal("0.01")
        session.commit()
    recovered = logged_in.get(root(run["shop_id"]) + f"/{run['id']}").json()
    assert act(logged_in, recovered)["status"] == "result_unknown"
    assert not model.requests
