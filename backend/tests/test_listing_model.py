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
from app.models.listings import ListingVersion
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.agent import ModelStatus
from app.schemas.listings import ProductFacts
from app.services.agent_model import GenerationReply, OpenAIResponsesModel
from app.services.listing_composition import listing_request
from tests.test_agent import act, root, start
from tests.test_analytics import SCOPE, imported
from tests.test_imports import create_shop
from tests.test_listings import decide, generate, setup
from tests.test_support import withdraw

PRODUCTS = 'sku,name,facts\nMODEL-SKU,Synthetic bottle,"容量 500 ml\n仅限冷水\n手洗"\n'


class ListingDouble:
    def __init__(self) -> None:
        self.requests: list[dict[str, Any]] = []
        self.content: dict[str, Any] | None = None
        self.unknown = False

    def generate(self, request: dict[str, Any], timeout: float) -> GenerationReply:
        self.requests.append(request)
        assert request["name"] == "listing_composition"
        keys = list(request["payload"]["facts"])
        return GenerationReply(
            self.content
            if self.content is not None
            else {
                "title_fact_ids": keys[:1],
                "description_fact_ids": keys[::-1],
                "next_action": "offer_draft",
            },
            None if self.unknown else Decimal("0.001"),
            100,
            30,
            "test_double",
        )


@pytest.fixture()
def model() -> Iterator[ListingDouble]:
    fake = ListingDouble()
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


def begin(client: TestClient, shop: int, product: dict[str, Any], **changes: Any) -> dict[str, Any]:
    values = {
        "template": "listing_model",
        "allow_model": True,
        "allow_listing_data": True,
        "expected_product_source_row_id": product["source"]["row_id"],
        "product_id": product["product_id"],
        "budget": {"max_cost_usd": "0.03"},
    }
    return start(client, shop, **(values | changes))


def candidate(client: TestClient, shop: int, product: dict[str, Any]) -> dict[str, Any]:
    return act(client, act(client, begin(client, shop, product)))


def save(client: TestClient, run: dict[str, Any]) -> dict[str, Any]:
    return act(client, act(client, act(client, run, "approve")))


def test_model_candidate_diff_approval_readback_dedupe_and_clear(
    logged_in: TestClient, model: ListingDouble
) -> None:
    shop, batch, product = setup(logged_in, PRODUCTS)
    run = candidate(logged_in, shop, product)
    assert run["status"] == "waiting_approval" and run["next_node"] == "listing_candidate"
    assert run["result"]["candidate"] == {
        "title": "Synthetic bottle · 容量 500 ml",
        "description": "手洗\n仅限冷水\n容量 500 ml",
    }
    assert run["spent_usd"] == "0.001000"
    assert logged_in.get(f"/api/shops/{shop}/listings/versions").json() == []
    payload = model.requests[0]["payload"]
    assert set(payload) == {"goal", "name", "facts"}
    assert "MODEL-SKU" not in json.dumps(payload) and "filename" not in json.dumps(payload)
    done = save(logged_in, run)
    assert done["status"] == "succeeded" and done["result"]["status"] == "draft"
    item_id = done["result"]["record_id"]
    item = logged_in.get(f"/api/shops/{shop}/listings/versions/{item_id}").json()
    assert item["snapshot"]["before"]["title"] == product["name"]
    assert item["snapshot"]["blockers"] == [] and item["engine"] == "test_double"
    repeated = save(logged_in, candidate(logged_in, shop, product))
    assert repeated["result"]["record_id"] == item_id
    assert decide(logged_in, shop, item, confirmed=False).status_code == 422
    assert decide(logged_in, shop, item).json()["status"] == "approved"
    assert (
        logged_in.get(f"/api/shops/{shop}/listings/products/{product['product_id']}").json()[
            "active_id"
        ]
        == item_id
    )
    withdraw(logged_in, batch, "clear")
    erased = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert erased["result"] is None and erased["input"] is None
    assert all(step["output"] is None and step["input"] is None for step in erased["steps"])
    assert (
        logged_in.get(f"/api/shops/{shop}/listings/versions/{item_id}").json()["snapshot"] is None
    )


@pytest.mark.parametrize(
    "change",
    [
        {"allow_model": False},
        {"allow_listing_data": False},
        {"expected_product_source_row_id": None},
        {"expected_product_source_row_id": 9999999},
    ],
)
def test_explicit_consent_binds_source_before_network(
    logged_in: TestClient, model: ListingDouble, change: dict[str, Any]
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    run = act(logged_in, act(logged_in, begin(logged_in, shop, product, **change)))
    assert run["status"] in {"blocked", "waiting_configuration"}
    assert model.requests == []


@pytest.mark.parametrize(
    "value",
    [
        {
            "title_fact_ids": ["fake"],
            "description_fact_ids": ["fact_1", "fact_2", "fact_3"],
            "next_action": "offer_draft",
        },
        {"title_fact_ids": [], "description_fact_ids": ["fact_1"], "next_action": "offer_draft"},
        {
            "title_fact_ids": ["fact_1", "fact_1"],
            "description_fact_ids": ["fact_1", "fact_2", "fact_3"],
            "next_action": "offer_draft",
        },
        {
            "title_fact_ids": [],
            "description_fact_ids": ["fact_1", "fact_1", "fact_3"],
            "next_action": "offer_draft",
        },
        {"title_fact_ids": [], "description_fact_ids": [], "next_action": "publish"},
        {
            "title_fact_ids": [],
            "description_fact_ids": [],
            "next_action": "needs_review",
            "title": "FDA approved",
        },
    ],
)
def test_fabrication_omission_duplicate_and_extra_fields_blocked(
    logged_in: TestClient, model: ListingDouble, value: dict[str, Any]
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    model.content = value
    run = candidate(logged_in, shop, product)
    assert run["status"] == "blocked" and run["reason"] == "invalid_model_output"
    assert run["spent_usd"] == "0.001000"
    assert "candidate" not in run["result"]


def test_missing_facts_and_model_review_branch_stop_without_draft(
    logged_in: TestClient, model: ListingDouble
) -> None:
    shop, _, product = setup(logged_in, "sku,name,facts\nEMPTY,Empty,\n")
    missing = act(logged_in, begin(logged_in, shop, product))
    assert missing["status"] == "waiting_input" and not model.requests
    imported(logged_in, shop, PRODUCTS, "products")
    product = next(
        p
        for p in logged_in.get(f"/api/shops/{shop}/listings/products").json()
        if p["sku"] == "MODEL-SKU"
    )
    model.content = {
        "title_fact_ids": [],
        "description_fact_ids": [],
        "next_action": "needs_review",
    }
    review = candidate(logged_in, shop, product)
    assert review["reason"] == "listing_needs_review" and review["status"] == "waiting_input"
    assert "candidate" not in review["result"]


@pytest.mark.parametrize("change", ["pause", "cancel", "clear", "revoke", "active"])
def test_inflight_changes_discard_candidate_and_keep_known_charge(
    logged_in: TestClient, model: ListingDouble, change: str
) -> None:
    shop, batch, product = setup(logged_in, PRODUCTS)
    local = generate(logged_in, shop, product)
    run = act(logged_in, begin(logged_in, shop, product))

    def mutate(request: dict[str, Any], timeout: float) -> GenerationReply:
        current = logged_in.get(root(shop) + f"/{run['id']}").json()
        if change in {"pause", "cancel"}:
            act(logged_in, current, change)
        elif change == "active":
            assert decide(logged_in, shop, local).status_code == 200
        else:
            withdraw(logged_in, batch, change)
        return model.generate(request, timeout)

    with patch.object(OpenAIResponsesModel, "generate", side_effect=mutate):
        result = act(logged_in, run)
    assert result["spent_usd"] == "0.001000" and result["reserved_usd"] == "0.000000"
    assert not any(s["output"] and "candidate" in s["output"] for s in result["steps"])
    if change == "clear":
        assert result["input"] is None and result["result"] is None
        assert all(s["input"] is None and s["output"] is None for s in result["steps"])
    if change == "pause":
        resumed = act(logged_in, act(logged_in, result, "resume"))
        assert resumed["status"] == "waiting_approval" and resumed["spent_usd"] == "0.002000"
    if change == "active":
        assert result["status"] == "blocked" and result["reason"] == "conflict"


def test_budget_unknown_and_replay(logged_in: TestClient, model: ListingDouble) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    run = act(logged_in, begin(logged_in, shop, product, budget={"max_cost_usd": "0"}))
    paused = act(logged_in, run)
    assert paused["reason"] == "cost_budget" and not model.requests
    resumed = act(logged_in, paused, "resume", budget={"max_cost_usd": "0.03"})
    model.unknown = True
    unknown = act(logged_in, resumed)
    assert unknown["status"] == "result_unknown" and unknown["reserved_usd"] == "0.010000"
    assert act(logged_in, unknown)["status"] == "result_unknown" and len(model.requests) == 1


def test_save_revalidates_active_base_and_rolls_back_on_audit_failure(
    logged_in: TestClient, model: ListingDouble, session_factory: sessionmaker[Session]
) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    run = candidate(logged_in, shop, product)
    approved = act(logged_in, run, "approve")
    original = UnitOfWork.record_event

    def fail(self: UnitOfWork, *args: Any, **kwargs: Any) -> None:
        if args[1] == "listing.draft_created":
            raise BusinessError("synthetic_audit_failure", "synthetic")
        original(self, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", new=fail):
        failed = act(logged_in, approved)
    assert failed["status"] == "blocked"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ListingVersion)) == 0
    run = candidate(logged_in, shop, product)
    local = generate(logged_in, shop, product)
    assert decide(logged_in, shop, local).status_code == 200
    blocked = act(logged_in, act(logged_in, run, "approve"))
    assert blocked["reason"] == "conflict" and blocked["status"] == "blocked"


def test_product_scope_is_checked_before_model(logged_in: TestClient, model: ListingDouble) -> None:
    shop, _, product = setup(logged_in, PRODUCTS)
    other = create_shop(logged_in, "other-model-shop")
    assert act(logged_in, begin(logged_in, other, product))["status"] == "blocked"
    run = act(
        logged_in, begin(logged_in, shop, product, scope={**SCOPE, "data_identity": "user_import"})
    )
    assert run["reason"] == "scope_mismatch" and not model.requests


def test_listing_responses_protocol_keeps_only_authorized_text(
    logged_in: TestClient, settings: Settings
) -> None:
    _, _, product = setup(logged_in, PRODUCTS)
    request = listing_request("突出容量，保留限制", ProductFacts.model_validate(product))
    adapter = OpenAIResponsesModel(
        settings.model_copy(
            update={
                "model_enabled": True,
                "model_api_key": SecretStr("synthetic-key"),
                "model_name": "synthetic",
                "model_input_usd_per_million": Decimal(1),
                "model_output_usd_per_million": Decimal(2),
            }
        )
    )
    calls: list[httpx.Request] = []

    def respond(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "usage": {"input_tokens": 20, "output_tokens": 10},
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {
                                "type": "output_text",
                                "text": json.dumps(
                                    {
                                        "title_fact_ids": ["fact_1"],
                                        "description_fact_ids": ["fact_2", "fact_1", "fact_3"],
                                        "next_action": "offer_draft",
                                    }
                                ),
                            }
                        ],
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
    assert body["text"]["format"]["name"] == "listing_composition"
    assert body["text"]["format"]["strict"] and body["store"] is False and "tools" not in body
    assert set(json.loads(body["input"])) == {"goal", "name", "facts"}
    assert reply.cost == Decimal("0.000040") and reply.content is not None
