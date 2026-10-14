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
from app.services.agent_model import DeepSeekChatModel
from tests.test_agent import act
from tests.test_listing_model import PRODUCTS, begin, candidate, save
from tests.test_listings import setup
from tests.test_support import policy
from tests.test_support import root as support_root
from tests.test_support import setup as setup_support
from tests.test_support_model import FAQ
from tests.test_support_model import candidate as support_candidate
from tests.test_support_model import save as save_support

PRIVATE_TOKEN = "synthetic-private-deepseek-token"


def configuration() -> Settings:
    return Settings(
        _env_file=None,
        database_url="mysql+pymysql://synthetic@localhost/unused_test",
        model_provider="deepseek_chat",
        model_enabled=True,
        model_name="deepseek-flash",
        model_api_key=SecretStr(PRIVATE_TOKEN),
        model_input_usd_per_million=Decimal("0.30"),
        model_output_usd_per_million=Decimal("1.20"),
        model_cost_note="Peak cache-miss input and output rates",
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
    "name": "fact_selection",
    "instructions": "Choose identifiers only",
    "payload": {"facts": {"one": "容量 500 ml"}},
    "schema": {
        "type": "object",
        "properties": {"intent": {"type": "string", "enum": ["daily"]}},
        "required": ["intent"],
        "additionalProperties": False,
    },
}


@pytest.mark.parametrize(
    "variant",
    [
        "valid",
        "refusal",
        "length",
        "invalid_json",
        "non_object_content",
        "empty_content",
        "no_usage",
        "bad_usage",
        "bool_usage",
        "negative_usage",
        "float_usage",
        "large_usage",
        "many_choices",
        "bad_choice",
        "bad_message",
        "tool_calls",
        "function_call",
        "bad_role",
        "timeout",
        "redirect",
        "http_error",
        "too_large",
        "array_body",
    ],
)
def test_deepseek_protocol_json_mode_usage_and_secret_isolation(variant: str) -> None:
    adapter = DeepSeekChatModel(configuration())
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if variant == "timeout":
            raise httpx.ReadTimeout(PRIVATE_TOKEN)
        if variant == "redirect":
            return httpx.Response(302, headers={"Location": "https://example.invalid"})
        if variant == "http_error":
            return httpx.Response(401, text=PRIVATE_TOKEN)
        if variant == "too_large":
            return httpx.Response(200, content=b"x" * 200001)
        if variant == "array_body":
            return httpx.Response(200, json=[])
        data = completion()
        choice = data["choices"][0]
        if variant == "refusal":
            choice["message"]["refusal"] = PRIVATE_TOKEN
        elif variant == "length":
            choice["finish_reason"] = "length"
        elif variant == "invalid_json":
            choice["message"]["content"] = PRIVATE_TOKEN
        elif variant == "non_object_content":
            choice["message"]["content"] = "[]"
        elif variant == "empty_content":
            choice["message"]["content"] = ""
        elif variant == "no_usage":
            del data["usage"]
        elif variant == "bad_usage":
            data["usage"] = None
        elif variant == "bool_usage":
            data["usage"]["prompt_tokens"] = True
        elif variant == "negative_usage":
            data["usage"]["completion_tokens"] = -1
        elif variant == "float_usage":
            data["usage"]["prompt_tokens"] = 10.5
        elif variant == "large_usage":
            data["usage"]["completion_tokens"] = 100000001
        elif variant == "many_choices":
            data["choices"] *= 2
        elif variant == "bad_choice":
            data["choices"] = [None]
        elif variant == "bad_message":
            choice["message"] = None
        elif variant == "tool_calls":
            choice["message"]["tool_calls"] = [{"function": {"name": "send_mail"}}]
        elif variant == "function_call":
            choice["message"]["function_call"] = {"name": "send_mail"}
        elif variant == "bad_role":
            choice["message"]["role"] = "tool"
        return httpx.Response(200, json=data)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    with patch("app.services.agent_model.httpx.Client", return_value=client) as factory:
        reply = adapter.generate(REQUEST, 2)
    assert len(calls) == 1
    assert str(calls[0].url) == "https://api.deepseek.com/chat/completions"
    assert calls[0].headers["authorization"] == "Bearer " + PRIVATE_TOKEN
    assert factory.call_args.kwargs["follow_redirects"] is False
    assert factory.call_args.kwargs["trust_env"] is False
    body = json.loads(calls[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["thinking"] == {"type": "disabled"}
    assert body["max_tokens"] == 768 and body["stream"] is False
    assert "JSON" in body["messages"][0]["content"]
    assert json.dumps(REQUEST["schema"], ensure_ascii=False) in body["messages"][0]["content"]
    assert json.loads(body["messages"][1]["content"]) == REQUEST["payload"]
    assert not {"tools", "store", "enable_thinking", "max_completion_tokens"} & body.keys()
    assert PRIVATE_TOKEN not in json.dumps(body) + repr(reply)
    unknown = {
        "no_usage",
        "bad_usage",
        "bool_usage",
        "negative_usage",
        "float_usage",
        "large_usage",
        "timeout",
        "redirect",
        "http_error",
        "too_large",
        "array_body",
    }
    assert reply.cost == (None if variant in unknown else Decimal("0.000054"))
    assert (reply.content is not None) == (variant == "valid")
    assert reply.engine == "deepseek_chat"
    expected = adapter._cost(len(json.dumps(body).encode()) + 4096, 768)
    assert adapter.reserve_generation(REQUEST) == expected


@pytest.mark.parametrize("name", ["deepseek-flash", "deepseek-v4-pro", "deepseek-v4-flash"])
def test_configured_deepseek_provider_and_model_family(name: str) -> None:
    settings = configuration()
    settings.model_name = name
    adapter = configured_model(settings)
    assert isinstance(adapter, DeepSeekChatModel)
    assert adapter.status().status == "configured"
    assert adapter.status().provider == "deepseek_chat"
    assert adapter.status().cost_note == "Peak cache-miss input and output rates"


@pytest.mark.parametrize("missing", ["enabled", "key", "name", "input_rate", "output_rate"])
def test_deepseek_configuration_required_before_network(missing: str) -> None:
    settings = configuration()
    if missing == "enabled":
        settings.model_enabled = False
    elif missing == "key":
        settings.model_api_key = None
    elif missing == "name":
        settings.model_name = "unverified-model"
    elif missing == "input_rate":
        settings.model_input_usd_per_million = None
    elif missing == "output_rate":
        settings.model_output_usd_per_million = None
    adapter = DeepSeekChatModel(settings)
    assert adapter.status().status == "not_configured"
    with patch("app.services.agent_model.httpx.Client") as client:
        with pytest.raises(BusinessError, match="模型未配置"):
            adapter.generate(REQUEST, 1)
        client.assert_not_called()


def test_deepseek_input_and_provider_bounds() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, database_url="mysql+pymysql://x/x", model_provider="custom")
    with pytest.raises(BusinessError) as caught:
        DeepSeekChatModel(configuration()).reserve_generation(
            REQUEST | {"payload": {"text": "x" * 60000}}
        )
    assert caught.value.code == "model_input_too_large"


@pytest.mark.parametrize(
    "content",
    [
        '{"intent":"daily"}',
        '{"intent":"blocked"}',
        '{"intent":"refund"}',
        '{"intent":"daily","extra":1}',
    ],
)
def test_deepseek_routing_validates_guarded_intents(content: str) -> None:
    adapter = DeepSeekChatModel(configuration())
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json=completion(content))

    client = httpx.Client(transport=httpx.MockTransport(respond))
    with patch("app.services.agent_model.httpx.Client", return_value=client):
        if content in {'{"intent":"daily"}', '{"intent":"blocked"}'}:
            result = adapter.decide("检查今日运营", 2)
            assert result.engine == "deepseek_chat"
            assert result.decision.intent == json.loads(content)["intent"]
            assert adapter.reserve("检查今日运营") > result.cost
        else:
            with pytest.raises(BusinessError) as caught:
                adapter.decide("检查今日运营", 2)
            assert caught.value.code == "model_result_unknown"
            assert PRIVATE_TOKEN not in str(caught.value)
    assert len(calls) == 1
    assert json.loads(calls[0].content)["max_tokens"] == 256


@pytest.mark.parametrize("known", [True, False])
def test_deepseek_business_validator_approval_and_unknown_no_retry(
    logged_in: TestClient, known: bool
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    calls: list[httpx.Request] = []
    content = json.dumps(
        {
            "title_fact_ids": ["fact_1"],
            "description_fact_ids": ["fact_3", "fact_2", "fact_1"],
            "next_action": "offer_draft",
        }
    )

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if not known:
            raise httpx.ReadTimeout(PRIVATE_TOKEN)
        return httpx.Response(200, json=completion(content))

    client = httpx.Client(transport=httpx.MockTransport(respond))
    try:
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            run = candidate(logged_in, shop, product)
        if known:
            assert run["status"] == "waiting_approval"
            assert run["result"]["engine"] == "deepseek_chat"
            assert run["spent_usd"] == "0.000054"
            done = save(logged_in, run)
            assert done["status"] == "succeeded"
            versions = logged_in.get(f"/api/shops/{shop}/listings/versions").json()
            assert versions[0]["engine"] == "deepseek_chat"
            assert versions[0]["status"] == "draft"
        else:
            assert run["status"] == "result_unknown"
            assert Decimal(run["reserved_usd"]) > 0
            with patch("app.services.agent_model.httpx.Client") as factory:
                assert act(logged_in, run)["status"] == "result_unknown"
                factory.assert_not_called()
        assert len(calls) == 1
        assert PRIVATE_TOKEN not in json.dumps(run)
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)


def test_deepseek_zero_budget_blocks_before_network(logged_in: TestClient) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    try:
        run = act(logged_in, begin(logged_in, shop, product, budget={"max_cost_usd": "0"}))
        with patch("app.services.agent_model.httpx.Client") as factory:
            blocked = act(logged_in, run)
            assert blocked["reason"] == "cost_budget"
            factory.assert_not_called()
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)


def test_deepseek_json_mode_still_rejects_fabricated_business_facts(
    logged_in: TestClient,
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    content = json.dumps(
        {
            "title_fact_ids": ["fabricated_fact"],
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
        assert run["status"] == "blocked" and run["reason"] == "invalid_model_output"
        assert run["spent_usd"] == "0.000054"
        assert logged_in.get(f"/api/shops/{shop}/listings/versions").json() == []
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)


def test_deepseek_support_candidate_approval_and_readback(logged_in: TestClient) -> None:
    shop, _, message = setup_support(logged_in, FAQ)
    selected_policy = policy(logged_in, shop, code="faq", topic="faq", text="Hand wash only.")
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    calls: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        payload = json.loads(json.loads(request.content)["messages"][1]["content"])
        content = {
            "intent_ids": payload["local_intents"],
            "fact_ids": list(payload["facts"])[::-1],
            "policy_ids": list(payload["policies"]),
            "next_action": "offer_draft",
        }
        return httpx.Response(200, json=completion(json.dumps(content)))

    client = httpx.Client(transport=httpx.MockTransport(respond))
    try:
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            run = support_candidate(logged_in, shop, message, policies=[selected_policy["id"]])
        assert run["status"] == "waiting_approval"
        assert run["result"]["engine"] == "deepseek_chat"
        assert "Hand wash only." in run["result"]["candidate"]["reply"]
        assert run["spent_usd"] == "0.000054"
        done = save_support(logged_in, run)
        assert done["status"] == "succeeded" and done["result"]["status"] == "draft"
        draft = logged_in.get(support_root(shop) + f"/drafts/{done['result']['record_id']}").json()
        assert draft["engine"] == "deepseek_chat"
        assert "Hand wash only." in draft["snapshot"]["reply"]
        assert len(calls) == 1
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)
