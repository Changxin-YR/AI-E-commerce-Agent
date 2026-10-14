import json
from collections.abc import Iterator
from decimal import Decimal
from threading import Event
from time import monotonic
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes.agent import configured_model
from app.schemas.agent import AgentAction
from app.services.agent_model import DeepSeekChatModel
from app.services.agent_stream import _delta_visible, action_events
from app.services.model_stream import bounded_lines, delta_sink, stream_deltas
from tests.test_agent import act, root, start
from tests.test_deepseek_model import PRIVATE_TOKEN, REQUEST, configuration
from tests.test_imports import create_shop
from tests.test_listing_model import PRODUCTS, begin, save
from tests.test_listings import setup
from tests.test_support import withdraw


def frame(value: Any) -> bytes:
    return ("data: " + json.dumps(value, ensure_ascii=False) + "\r\n\r\n").encode()


def chunk(content: str | None, finish: str | None = None) -> dict[str, Any]:
    return {
        "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": finish}],
        "usage": None,
    }


def provider_events(content: str) -> list[bytes]:
    return [
        frame(chunk(content[:8])),
        frame(chunk(content[8:])),
        frame(chunk(None, "stop")),
        frame({"choices": [], "usage": {"prompt_tokens": 100, "completion_tokens": 20}}),
        b"data: [DONE]\n\n",
    ]


def test_stream_preserves_utf8_across_network_boundaries_and_enforces_deadline() -> None:
    class ProviderStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for byte in 'data: {"text":"商品容量"}\r\n\r\n'.encode():
                yield bytes([byte])

    response = httpx.Response(200, stream=ProviderStream())
    assert list(bounded_lines(response, monotonic() + 10)) == ['data: {"text":"商品容量"}', ""]
    with pytest.raises(ValueError, match="time exceeded"):
        list(bounded_lines(httpx.Response(200, stream=ProviderStream()), monotonic() - 1))


@pytest.mark.parametrize(
    "variant",
    [
        "valid",
        "no_usage",
        "no_done",
        "no_finish",
        "invalid_json",
        "bad_usage",
        "tool_calls",
        "too_large",
        "timeout",
        "http_error",
        "length",
        "bad_role",
    ],
)
def test_deepseek_stream_protocol(variant: str) -> None:
    adapter = DeepSeekChatModel(configuration())
    content = '{"intent":"daily"}' if variant != "invalid_json" else "not-json"
    events = provider_events(content)
    expected_cost = Decimal("0.000054")
    if variant == "no_usage":
        events.pop(-2)
    elif variant == "no_done":
        events.pop()
    elif variant == "no_finish":
        events.pop(2)
    elif variant == "bad_usage":
        events[-2] = frame(
            {"choices": [], "usage": {"prompt_tokens": True, "completion_tokens": 2}}
        )
    elif variant == "tool_calls":
        events[0] = frame({"choices": [{"index": 0, "delta": {"tool_calls": [{}]}}]})
    elif variant == "bad_role":
        events[0] = frame({"choices": [{"index": 0, "delta": {"role": "tool"}}]})
    elif variant == "too_large":
        events = [b"x" * 200001]
    elif variant == "length":
        events[2] = frame(chunk(None, "length"))
    deltas: list[str] = []
    calls: list[httpx.Request] = []

    class ProviderStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for index, event in enumerate(events):
                if index == 1 and variant == "valid":
                    # The first provider delta is delivered before the response finishes.
                    assert deltas == [content[:8]]
                if index == 1 and variant == "timeout":
                    raise httpx.ReadTimeout(PRIVATE_TOKEN)
                # Exercise UTF-8 / SSE frame boundaries across network chunks.
                yield event[:7]
                yield event[7:]

    def respond(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return (
            httpx.Response(401, text=PRIVATE_TOKEN)
            if variant == "http_error"
            else httpx.Response(200, stream=ProviderStream())
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    with (
        stream_deltas(deltas.append),
        patch("app.services.agent_model.httpx.Client", return_value=client),
    ):
        reply = adapter.generate(REQUEST, 2)
    body = json.loads(calls[0].content)
    assert body["stream"] is True and body["stream_options"] == {"include_usage": True}
    assert delta_sink() is None
    assert len(calls) == 1
    assert PRIVATE_TOKEN not in repr(reply) + repr(deltas)
    if variant == "valid":
        assert "".join(deltas) == content
        assert reply.content == {"intent": "daily"} and reply.cost == expected_cost
    elif variant in {"invalid_json", "length"}:
        assert reply.content is None and reply.cost == expected_cost
    else:
        assert reply.content is None and reply.cost is None


def events(response: httpx.Response) -> list[tuple[str, dict[str, Any]]]:
    assert response.status_code == 200, response.text
    result = []
    for block in response.text.strip().split("\n\n"):
        if block.startswith(":"):
            continue
        kind, data = block.split("\n", 1)
        result.append((kind.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return result


def advance_stream(client: TestClient, run: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return events(
        client.post(
            root(run["shop_id"]) + f"/{run['id']}/stream",
            json={"version": run["version"], "action": "advance"},
        )
    )


def test_stream_local_action_persists_and_enforces_scope_and_csrf(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    run = start(logged_in, shop)
    output = advance_stream(logged_in, run)
    assert output[0][0] == "status" and output[-1][0] == "result"
    result = output[-1][1]
    assert result["status"] == "succeeded"
    assert logged_in.get(root(shop) + f"/{run['id']}").json() == result
    other = create_shop(logged_in, code="other-stream-shop")
    assert (
        logged_in.post(
            root(other) + f"/{run['id']}/stream",
            json={"version": result["version"], "action": "advance"},
        ).status_code
        == 404
    )
    assert (
        logged_in.post(
            root(shop) + f"/{run['id']}/stream",
            json={"version": result["version"], "action": "advance"},
            headers={"X-CSRF-Token": "invalid"},
        ).status_code
        == 403
    )


@pytest.mark.parametrize("known", [True, False])
def test_stream_deepseek_candidate_persistence_and_unknown_cost(
    logged_in: TestClient, known: bool
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    content = json.dumps(
        {
            "title_fact_ids": ["fact_1", "fact_2"],
            "description_fact_ids": ["fact_3", "fact_2", "fact_1"],
            "next_action": "offer_draft",
        }
    )
    chunks = provider_events(content)
    if not known:
        chunks.pop(-2)
    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"".join(chunks)))
    )
    try:
        run = act(logged_in, begin(logged_in, shop, product))
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            output = advance_stream(logged_in, run)
        assert "".join(value["text"] for kind, value in output if kind == "delta") == content
        run = output[-1][1]
        if known:
            assert run["status"] == "waiting_approval" and run["spent_usd"] == "0.000054"
            done = save(logged_in, run)
            assert done["status"] == "succeeded"
            versions = logged_in.get(f"/api/shops/{shop}/listings/versions").json()
            assert versions[0]["engine"] == "deepseek_chat"
        else:
            assert run["status"] == "result_unknown" and Decimal(run["reserved_usd"]) > 0
            with patch("app.services.agent_model.httpx.Client") as factory:
                repeat = advance_stream(logged_in, run)
                assert repeat[-1][1]["status"] == "result_unknown"
                factory.assert_not_called()
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)


@pytest.mark.parametrize("change", ["pause", "cancel", "clear"])
def test_stream_inflight_change_discards_candidate_and_settles_charge(
    logged_in: TestClient, change: str
) -> None:
    shop, batch, product = setup(logged_in, PRODUCTS)
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    content = json.dumps(
        {
            "title_fact_ids": ["fact_1", "fact_2"],
            "description_fact_ids": ["fact_3", "fact_2", "fact_1"],
            "next_action": "offer_draft",
        }
    )
    run = act(logged_in, begin(logged_in, shop, product))

    class ProviderStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for index, event in enumerate(provider_events(content)):
                if index == 1:
                    if change == "clear":
                        withdraw(logged_in, batch, "clear")
                    else:
                        current = logged_in.get(root(shop) + f"/{run['id']}").json()
                        act(logged_in, current, change)
                yield event

    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=ProviderStream()))
    )
    try:
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            output = advance_stream(logged_in, run)
        result = output[-1][1]
        assert output[-1][0] == "result"
        assert result["spent_usd"] == "0.000054" and result["reserved_usd"] == "0.000000"
        assert logged_in.get(f"/api/shops/{shop}/listings/versions").json() == []
        if change == "clear":
            emitted = "".join(value["text"] for kind, value in output if kind == "delta")
            assert emitted in {"", content[:8]}
            assert result["source_status"] == "cleared"
            assert result["input"] is None and result["result"] is None
            assert all(step["input"] is None and step["output"] is None for step in result["steps"])
        else:
            assert "".join(value["text"] for kind, value in output if kind == "delta") == content
            assert result["status"] == {"pause": "paused", "cancel": "cancelled"}[change]
            assert not any(
                step["output"] and "candidate" in step["output"] for step in result["steps"]
            )
    finally:
        logged_in.app.dependency_overrides.pop(configured_model, None)


def test_stream_delta_visibility_check_fails_closed() -> None:
    factory = MagicMock()
    factory.return_value.__enter__.return_value.scalar.side_effect = SQLAlchemyError(PRIVATE_TOKEN)
    assert _delta_visible(factory, 1, 2, 3) is False


def test_stream_drops_queued_delta_after_clear_and_still_settles_usage(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, batch, product = setup(logged_in, PRODUCTS)
    owner = logged_in.get("/api/auth/session").json()["user_id"]
    adapter = DeepSeekChatModel(configuration())
    logged_in.app.dependency_overrides[configured_model] = lambda: adapter
    run = act(logged_in, begin(logged_in, shop, product))
    content = json.dumps(
        {
            "title_fact_ids": ["fact_1", "fact_2"],
            "description_fact_ids": ["fact_3", "fact_2", "fact_1"],
            "next_action": "offer_draft",
        }
    )
    queued, finish = Event(), Event()
    consumed: list[int] = []

    class ProviderStream(httpx.SyncByteStream):
        def __iter__(self) -> Iterator[bytes]:
            for index, event in enumerate(provider_events(content)):
                if index == 2:
                    # Both text fragments have already reached the queue; hold usage/DONE.
                    queued.set()
                    assert finish.wait(5)
                consumed.append(index)
                yield event

    client = httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=ProviderStream()))
    )
    iterator = action_events(
        session_factory,
        adapter,
        owner,
        shop,
        run["id"],
        AgentAction(version=run["version"], action="advance"),
    )
    try:
        with patch("app.services.agent_model.httpx.Client", return_value=client):
            assert next(iterator).startswith("event: status")
            assert next(iterator).startswith("event: delta")
            assert queued.wait(5)
            withdraw(logged_in, batch, "clear")
            finish.set()
            remaining = list(iterator)
        assert all(not item.startswith("event: delta") for item in remaining)
        result_event = next(item for item in remaining if item.startswith("event: result"))
        result = json.loads(result_event.split("\ndata: ", 1)[1])
        assert result["source_status"] == "cleared" and result["result"] is None
        assert result["spent_usd"] == "0.000054" and result["reserved_usd"] == "0.000000"
        assert consumed == [0, 1, 2, 3, 4]
    finally:
        finish.set()
        iterator.close()
        logged_in.app.dependency_overrides.pop(configured_model, None)
