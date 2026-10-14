from collections.abc import Iterator
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.schemas.agent import ModelStatus
from app.services.agent_model import GenerationReply, OpenAIResponsesModel
from app.services.concise_answer import answer_request, validate_answer
from tests import test_listing_model as listing_tests
from tests import test_operations_model as operation_tests
from tests import test_support_model as support_tests
from tests.test_agent import act, root
from tests.test_analysis_model import ModelDouble, explanation, question
from tests.test_analytics import setup_data
from tests.test_support import withdraw


class ChatModel(ModelDouble):
    answer = "Known merchandise gross profit is 27.5950. Net profit remains unknown."

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        delegates = {
            "listing_composition": listing_tests.ListingDouble,
            "operation_evidence": operation_tests.OperationsDouble,
            "support_composition": support_tests.SupportDouble,
        }
        if request["name"] in delegates:
            self.requests.append(request)
            return delegates[request["name"]]().generate(request, timeout)
        if request["name"] != "concise_answer":
            return super().generate(request, timeout)
        self.requests.append(request)
        return GenerationReply({"answer": self.answer}, Decimal("0.001"), 100, 30, "test_double")


@pytest.fixture()
def chat_model() -> Iterator[ChatModel]:
    fake = ChatModel()
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


def test_chat_read_completes_without_approval_then_write_requires_confirmation(
    logged_in: TestClient, chat_model: ChatModel
) -> None:
    shop, _, _ = setup_data(logged_in)
    run = explanation(
        logged_in,
        question(
            logged_in,
            shop,
            response_mode="chat",
            response_language="English",
            goal="请用英语回答销售表现",
        ),
    )
    assert run["status"] == "ready" and run["next_node"] == "answer"
    assert not any(step["next_node"] == "analysis_todo" for step in run["steps"])
    run = act(logged_in, run)
    assert run["status"] == "succeeded" and run["reason"] == "chat_answered"
    assert run["result"]["chat_answer"] == chat_model.answer
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []
    assert (
        logged_in.post(
            root(shop) + f"/{run['id']}", json={"version": run["version"], "action": "approve"}
        ).status_code
        == 409
    )
    request = chat_model.requests[-1]
    assert request["payload"]["language_preference"] == "English"
    assert "explicitly requested in the question first" in request["instructions"]
    assert "order_id" not in str(request["payload"])
    assert "filename" not in str(request["payload"])
    assert act(logged_in, run)["status"] == "succeeded"
    assert len(chat_model.requests) == 3
    pending = act(logged_in, run, "request_save")
    assert pending["status"] == "waiting_approval"
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []
    done = act(logged_in, act(logged_in, act(logged_in, pending, "approve")))
    assert done["status"] == "succeeded" and done["result"]["record_type"] == "analysis"
    assert len(logged_in.get(f"/api/shops/{shop}/analytics/saved").json()) == 1


def test_chat_rejects_invented_numbers_and_settles_cost(
    logged_in: TestClient, chat_model: ChatModel
) -> None:
    shop, _, _ = setup_data(logged_in)
    chat_model.answer = "Your profit is 999999999."
    run = act(logged_in, explanation(logged_in, question(logged_in, shop, response_mode="chat")))
    assert run["status"] == "blocked" and run["reason"] == "invalid_model_output"
    assert run["spent_usd"] == "0.003000"
    assert "chat_answer" not in run["result"]
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []


def test_stale_chat_cannot_be_saved_and_cleared_answer_is_removed(
    logged_in: TestClient, chat_model: ChatModel
) -> None:
    shop, batch, _ = setup_data(logged_in)
    run = act(logged_in, explanation(logged_in, question(logged_in, shop, response_mode="chat")))
    batch = withdraw(logged_in, batch, "revoke")
    run = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert (
        logged_in.post(
            root(shop) + f"/{run['id']}", json={"version": run["version"], "action": "request_save"}
        ).status_code
        == 409
    )
    withdraw(logged_in, batch, "clear")
    cleared = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert cleared["result"] is None and chat_model.answer not in str(cleared)


@pytest.mark.parametrize(
    "language, text",
    [
        ("中文", "已知商品毛利为 27.5950，净利润仍未知。"),
        ("English", "Known gross profit is 27.5950. Net profit is unknown."),
        ("日本語", "商品の粗利益は 27.5950 です。純利益は不明です。"),
    ],
)
def test_localized_answer_is_preserved(language: str, text: str) -> None:
    request = answer_request("销售怎么样", language, "question", {"gross": "27.5950"})
    assert validate_answer({"answer": text}, request["payload"]) == text
    assert request["payload"]["language_preference"] == language


def test_answer_cannot_add_action_fields_or_unknown_references() -> None:
    payload = {"evidence": {"facts": {"item_1": {"gross": "27.5950"}}}}
    for content in [{"answer": "ok", "action": "approve"}, {"answer": "[item_2]"}, {"answer": " "}]:
        with pytest.raises(ValueError):
            validate_answer(content, payload)


@pytest.mark.parametrize("text", ["毛利为999元。", "粗利益は999です。", "Gross profit: 999."])
def test_numbers_next_to_localized_text_are_checked(text: str) -> None:
    with pytest.raises(ValueError, match="number absent"):
        validate_answer({"answer": text}, {"evidence": {"gross": "27.5950"}})


def test_localized_numbers_without_spaces_are_preserved() -> None:
    text = "已知毛利为27.5950，净利润未知。"
    assert validate_answer({"answer": text}, {"evidence": {"gross": "27.5950"}}) == text


@pytest.mark.parametrize("template", ["listing_model", "support_model", "daily_model"])
def test_other_chat_flows_finish_before_any_business_write(
    logged_in: TestClient, chat_model: ChatModel, template: str
) -> None:
    chat_model.answer = "Please review the supplied information."
    if template == "listing_model":
        shop, _, product = listing_tests.setup(logged_in, listing_tests.PRODUCTS)
        run = listing_tests.begin(logged_in, shop, product, response_mode="chat")
        path = f"/api/shops/{shop}/listings/versions"
    elif template == "support_model":
        shop, _, message = support_tests.setup(logged_in, support_tests.FAQ)
        policy = support_tests.policy(
            logged_in, shop, code="faq", topic="faq", text="Hand wash only."
        )
        run = support_tests.begin(
            logged_in, shop, message, policies=[policy["id"]], response_mode="chat"
        )
        path = support_tests.support_root(shop) + "/drafts"
    else:
        shop, _ = operation_tests.setup(logged_in)
        run = operation_tests.begin(logged_in, shop, response_mode="chat")
        path = operation_tests.operations_root(shop) + "/tasks?data_identity=synthetic"
    while run["status"] == "ready":
        run = act(logged_in, run)
    assert run["status"] == "succeeded", run
    assert run["reason"] == "chat_answered"
    assert not any(
        step["next_node"] in {"listing_candidate", "support_candidate", "propose_tasks"}
        for step in run["steps"]
    )
    saved = logged_in.get(path).json()
    assert (saved["items"] if isinstance(saved, dict) else saved) == []
    pending = act(logged_in, run, "request_save")
    assert pending["status"] == "waiting_approval"
    done = act(logged_in, act(logged_in, act(logged_in, pending, "approve")))
    assert done["status"] == "succeeded", done
