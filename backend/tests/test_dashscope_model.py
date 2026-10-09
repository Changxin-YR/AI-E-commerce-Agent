import json
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.api.routes.agent import configured_model
from app.core.config import Settings
from app.core.errors import BusinessError
from app.services.agent_model import DashScopeChatModel, OpenAIResponsesModel
from tests.test_agent import act
from tests.test_listing_model import PRODUCTS, candidate, save
from tests.test_listings import setup


def configuration() -> Settings:
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://synthetic@localhost/unused_test",
        model_provider="dashscope_chat",
        model_enabled=True,
        model_name="qwen3.7-flash",
        model_api_key=SecretStr("synthetic-private-token"),
        model_input_usd_per_million=Decimal("0.24"),
        model_output_usd_per_million=Decimal("0.96"),
        model_cost_note="Synthetic budget conversion",
    )


def completion(content: str = '{"intent":"daily"}') -> dict[str, Any]:
    return {
        "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content},
            }
        ],
    }


REQUEST = {
    "name": "synthetic",
    "instructions": "Choose identifiers only",
    "payload": {"facts": {"one": "synthetic"}},
    "schema": {"type": "object", "properties": {}, "additionalProperties": False},
}


@pytest.mark.parametrize(
    "variant",
    [
        "valid",
        "refusal",
        "length",
        "invalid_json",
        "no_usage",
        "bool_usage",
        "negative_usage",
        "many_choices",
        "bad_choice",
        "bad_message",
        "tool_calls",
        "timeout",
        "redirect",
        "http_error",
        "too_large",
        "array_body",
    ],
)
def test_chat_protocol_keeps_known_usage_and_never_forwards_secret(variant: str) -> None:
    adapter = DashScopeChatModel(configuration())
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if variant == "timeout":
            raise httpx.ReadTimeout("synthetic-private-token")
        if variant == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid"})
        if variant == "http_error":
            return httpx.Response(401, text="synthetic-private-token")
        if variant == "too_large":
            return httpx.Response(200, content=b"x" * 200001)
        if variant == "array_body":
            return httpx.Response(200, json=[])
        data = completion()
        choice = data["choices"][0]
        if variant == "refusal":
            choice["message"]["refusal"] = "synthetic-private-token"
        elif variant == "length":
            choice["finish_reason"] = "length"
        elif variant == "invalid_json":
            choice["message"]["content"] = "synthetic-private-token"
        elif variant == "no_usage":
            del data["usage"]
        elif variant == "bool_usage":
            data["usage"]["prompt_tokens"] = True
        elif variant == "negative_usage":
            data["usage"]["completion_tokens"] = -1
        elif variant == "many_choices":
            data["choices"] *= 2
        elif variant == "bad_choice":
            data["choices"] = [None]
        elif variant == "bad_message":
            choice["message"] = None
        elif variant == "tool_calls":
            choice["message"]["tool_calls"] = [{"function": {"name": "send_mail"}}]
        return httpx.Response(200, json=data)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    with patch("app.services.agent_model.httpx.Client", return_value=client) as factory:
        reply = adapter.generate(REQUEST, 2)
    assert len(calls) == 1
    assert str(calls[0].url) == DashScopeChatModel.endpoint
    assert factory.call_args.kwargs["follow_redirects"] is False
    assert factory.call_args.kwargs["trust_env"] is False
    body = json.loads(calls[0].content)
    assert body["response_format"]["json_schema"]["strict"] is True
    assert body["enable_thinking"] is False and body["max_completion_tokens"] == 768
    assert "tools" not in body and "store" not in body
    assert "synthetic-private-token" not in json.dumps(body) + repr(reply)
    known = variant in {
        "valid",
        "refusal",
        "length",
        "invalid_json",
        "many_choices",
        "bad_choice",
        "bad_message",
        "tool_calls",
    }
    assert reply.cost == (Decimal("0.000044") if known else None)
    assert (reply.content is not None) == (variant == "valid")
    assert reply.engine == "dashscope_chat"
    expected = adapter._cost(len(json.dumps(body).encode()) + 4096, 778)
    assert adapter.reserve_generation(REQUEST) == expected


def test_configured_provider_and_bounds() -> None:
    settings = configuration()
    adapter = configured_model(settings)
    assert isinstance(adapter, DashScopeChatModel)
    assert adapter.status().provider == "dashscope_chat"
    assert adapter.status().cost_note == "Synthetic budget conversion"
    settings.model_provider = "openai_responses"
    assert isinstance(configured_model(settings), OpenAIResponsesModel)
    settings.model_name = "unverified-model"
    assert adapter.status().status == "not_configured"
    with patch("app.services.agent_model.httpx.Client") as client:
        with pytest.raises(BusinessError, match="模型未配置"):
            adapter.generate(REQUEST, 1)
        client.assert_not_called()
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="mysql+pymysql://x/x", model_provider="custom")
    with pytest.raises(BusinessError) as caught:
        DashScopeChatModel(configuration()).reserve_generation(
            REQUEST | {"payload": {"text": "x" * 60000}}
        )
    assert caught.value.code == "model_input_too_large"


def test_chat_routing_uses_same_guarded_intents() -> None:
    adapter = DashScopeChatModel(configuration())
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=completion()))
    )
    with patch("app.services.agent_model.httpx.Client", return_value=client):
        result = adapter.decide("检查今日运营", 2)
    assert result.engine == "dashscope_chat" and result.decision.intent == "daily"
    assert adapter.reserve("检查今日运营") > result.cost


def test_dashscope_candidate_runs_through_approval_and_readback(logged_in: TestClient) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    adapter = DashScopeChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    content = json.dumps(
        {
            "title_fact_ids": ["fact_1"],
            "description_fact_ids": ["fact_3", "fact_2", "fact_1"],
            "next_action": "offer_draft",
        }
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=completion(content)))
    )
    try:
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            run = candidate(logged_in, shop, product)
        assert run["status"] == "waiting_approval"
        assert run["result"]["engine"] == "dashscope_chat"
        assert run["spent_usd"] == "0.000044"
        done = save(logged_in, run)
        assert done["status"] == "succeeded"
        versions = logged_in.get(f"/api/shops/{shop}/listings/versions").json()
        assert versions[0]["engine"] == "dashscope_chat" and versions[0]["status"] == "draft"
        assert act(logged_in, done)["status"] == "succeeded"
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)
