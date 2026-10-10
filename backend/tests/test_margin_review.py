import json
import os
import subprocess
import sys
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.models.agent import AgentExecution
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.agent_skills import REGISTRY, ControlledSkills, require_skill
from app.services.auth import AuthService
from tests.conftest import TEST_PASSWORD
from tests.test_agent import act, root, start
from tests.test_analytics import SCOPE, calculate, imported
from tests.test_imports import ORDER_HEADER, PRODUCTS, create_shop
from tests.test_listings import decide, generate, revise
from tests.test_order_costs import record
from tests.test_support import withdraw

WINDOW = {**SCOPE, "start_at": "2026-10-01T00:00:00+08:00"}
ORDER = ORDER_HEADER + "M1,1,001,2,10,USD,2026-10-07 08:30:00,paid,0,0\n"
PARAMETERS = PRODUCTS.replace("Steel", '"Material: Steel\nCapacity: 400ml"')


def prepared(client, *, history=None, content=False):
    shop = create_shop(client)
    batch = imported(client, shop, PARAMETERS, "products")
    imported(client, shop, ORDER, "orders")
    product = client.get(f"/api/shops/{shop}/listings/products").json()[0]
    if history is not None:
        line = calculate(client, shop)["lines"][0]
        record(client, shop, line["source"]["row_id"], unit_cost=history)
    if content:
        draft = generate(client, shop, product)
        edited = revise(
            client, shop, draft, {"title": "Test Cup", "description": "Material: Steel"}
        )
        assert decide(client, shop, edited).status_code == 200
    return shop, batch, product


def review(client, shop, **fields):
    run = start(client, shop, template="margin_review", scope=WINDOW, **fields)
    return act(client, act(client, run))


def finish_write(client, run):
    return act(client, act(client, act(client, run, "approve")))


def test_empty_window_stops_without_write_and_rejects_nonseven_days(logged_in):
    shop = create_shop(logged_in)
    run = review(logged_in, shop)
    assert (run["status"], run["reason"]) == ("waiting_input", "margin_missing_orders")
    assert run["result"]["save_analysis"] is False
    assert run["result"]["recommendations"][0]["kind"] == "input"
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []
    assert (
        logged_in.post(
            root(shop),
            json={"request_id": str(uuid4()), "template": "margin_review", "scope": SCOPE},
        ).status_code
        == 422
    )


def test_missing_history_saves_real_todo_after_approval_only(logged_in):
    shop, _, _ = prepared(logged_in)
    run = review(logged_in, shop)
    assert run["status"] == "waiting_approval" and run["next_node"] == "analysis_todo"
    assert not run["result"]["ranking_available"] and run["result"]["candidate_count"] == 0
    assert run["result"]["recommendations"][0]["kind"] == "cost"
    assert act(logged_in, run)["version"] == run["version"]
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []
    done = finish_write(logged_in, run)
    assert done["status"] == "succeeded" and done["steps_used"] == 4
    saved = logged_in.get(f"/api/shops/{shop}/analytics/saved/{done['result']['record_id']}").json()
    assert saved["snapshot"]["summary"]["gross_profit"] is None
    assert saved["todo"]["id"] == done["result"]["todo_id"]
    assert saved["scope"]["cost_mode"] == "seller_history"


def test_historical_pricing_branch_decimal_idempotency_and_new_process_read(
    logged_in, settings, session_factory
):
    shop, _, _ = prepared(logged_in, history="9.5")
    run = review(logged_in, shop)
    assert run["result"]["recommendations"][0]["kind"] == "pricing"
    assert run["result"]["candidate_count"] == 1
    metrics = next(s["output"] for s in run["steps"] if s["skill"] == "metrics")
    assert Decimal(metrics["summary"]["cost"]) == 19
    assert Decimal(metrics["summary"]["gross_profit"]) == 1
    assert Decimal(metrics["summary"]["margin_percent"]) == 5
    done = finish_write(logged_in, run)
    replay = logged_in.post(root(shop), json=done["input"]).json()
    assert replay["id"] == done["id"] and replay["result"] == done["result"]
    second = finish_write(logged_in, review(logged_in, shop))
    assert second["result"] == done["result"]
    assert len(logged_in.get(f"/api/shops/{shop}/analytics/saved").json()) == 1
    with session_factory() as session:
        owner = session.scalar(
            select(AgentExecution.owner_id).where(AgentExecution.id == done["id"])
        )
    script = """
import json, os, sys
from app.core.config import Settings
from app.repositories.database import create_database_engine, create_session_factory
from app.repositories.unit_of_work import UnitOfWork
from app.services.agent import AgentService
from app.services.agent_model import OpenAIResponsesModel
settings = Settings(
    _env_file=None, database_url=os.environ['SOLOOPS_TEST_DATABASE_URL'],
    model_enabled=False, outbound_enabled=False, scheduler_enabled=False,
)
engine = create_database_engine(settings)
with create_session_factory(engine)() as session:
    service = AgentService(UnitOfWork(session), OpenAIResponsesModel(settings))
    run = service.get(*map(int, sys.argv[1:]))
    print(json.dumps({'status': run.status, 'result': run.result, 'steps': run.steps_used}))
engine.dispose()
"""
    restarted = subprocess.run(
        [sys.executable, "-c", script, str(owner), str(shop), str(done["id"])],
        env={**os.environ, "SOLOOPS_TEST_DATABASE_URL": settings.database_url.get_secret_value()},
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    assert json.loads(restarted.stdout) == {
        "status": "succeeded",
        "result": done["result"],
        "steps": 4,
    }


def test_independent_content_branch_needs_no_low_margin_claim(logged_in):
    shop, _, product = prepared(logged_in, history="1", content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    assert run["result"]["candidate_count"] == 0 and not run["result"]["save_analysis"]
    assert [r["kind"] for r in run["result"]["recommendations"]] == ["listing"]
    assert run["result"]["listing"]["missing_parameters"] == ["Capacity: 400ml"]
    run = act(logged_in, run)
    assert run["status"] == "waiting_approval" and run["next_node"] == "listing_draft"
    done = finish_write(logged_in, run)
    assert done["status"] == "succeeded" and done["steps_used"] == 5
    listing = logged_in.get(
        f"/api/shops/{shop}/listings/versions/{done['result']['record_id']}"
    ).json()
    assert (
        listing["status"] == "draft"
        and listing["snapshot"]["proposed"]["description"] == product["facts"]
    )
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []


def test_combined_gaps_have_separate_approvals_results_and_clear_chain(logged_in):
    shop, batch, product = prepared(logged_in, content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    assert [r["kind"] for r in run["result"]["recommendations"]] == ["cost", "listing"]
    first = finish_write(logged_in, run)
    assert first["next_node"] == "product_context" and first["result"]["record_type"] == "analysis"
    second = act(logged_in, first)
    assert second["status"] == "waiting_approval"
    assert act(logged_in, second)["version"] == second["version"]
    done = finish_write(logged_in, second)
    assert done["steps_used"] == 7 and done["status"] == "succeeded"
    assert [s["output"]["record_type"] for s in done["steps"] if s["node"] == "verify"] == [
        "analysis",
        "listing",
    ]
    assert Decimal(done["spent_usd"]) == 0
    withdraw(logged_in, batch, "clear")
    cleared = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert cleared["source_status"] == "cleared" and cleared["result"] is None
    assert all(s["input"] is None and s["output"] is None for s in cleared["steps"])


@pytest.mark.parametrize("change", ["source", "active"])
def test_changed_source_or_active_listing_blocks_old_approval(logged_in, change):
    shop, batch, product = prepared(logged_in, content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    if change == "source":
        withdraw(logged_in, batch, "revoke")
    else:
        newer = generate(logged_in, shop, product)
        assert decide(logged_in, shop, newer).status_code == 200
    latest = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert latest["source_status"] == "stale"
    response = logged_in.post(
        root(shop) + f"/{run['id']}", json={"version": latest["version"], "action": "approve"}
    )
    assert response.status_code == 409
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []


def test_reject_second_node_keeps_only_first_verified_result(logged_in):
    shop, _, product = prepared(logged_in, content=True)
    second = act(
        logged_in,
        finish_write(logged_in, review(logged_in, shop, product_id=product["product_id"])),
    )
    rejected = act(logged_in, second, "reject")
    assert rejected["status"] == "rejected" and act(logged_in, rejected)["status"] == "rejected"
    assert not any(s["skill"] == "listing_draft" for s in rejected["steps"])
    assert any(
        s["node"] == "verify" and s["output"]["record_type"] == "analysis"
        for s in rejected["steps"]
    )


def test_no_evidence_does_not_create_unneeded_content_or_analysis(logged_in):
    shop, _, product = prepared(logged_in, history="1")
    run = review(logged_in, shop, product_id=product["product_id"])
    assert run["status"] == "succeeded" and run["reason"] == "margin_no_action"
    assert run["result"]["listing"] is None and run["result"]["recommendations"] == []
    estimate = review(logged_in, shop, margin_cost_mode="current_estimate")
    assert estimate["result"]["scope"]["cost_mode"] == "current_estimate"
    assert estimate["status"] == "succeeded"


@pytest.mark.parametrize("scope", [{"channel": "amazon"}, {"data_identity": "user_import"}])
def test_product_identity_and_channel_isolation(logged_in, scope):
    shop, _, product = prepared(logged_in)
    run = start(
        logged_in,
        shop,
        template="margin_review",
        scope={**WINDOW, **scope},
        product_id=product["product_id"],
    )
    denied = act(logged_in, act(logged_in, run))
    assert denied["status"] == "blocked" and denied["reason"] == "scope_mismatch"


def test_foreign_shop_product_denied_and_r3_metadata_blocked(logged_in):
    shop, _, product = prepared(logged_in)
    other = create_shop(logged_in, code="margin-other")
    denied = review(logged_in, other, product_id=product["product_id"])
    assert denied["status"] == "blocked" and denied["reason"] == "not_found"
    spec = require_skill("margin_evidence")
    with patch.dict(REGISTRY, {"margin_evidence": spec.model_copy(update={"risk": "R3"})}):
        blocked = review(logged_in, shop)
    assert blocked["reason"] == "skill_policy_denied"


def test_step_time_budget_and_bounded_read_failure(logged_in, session_factory):
    shop, _, _ = prepared(logged_in)
    run = start(logged_in, shop, template="margin_review", scope=WINDOW, budget={"max_steps": 1})
    paused = act(logged_in, act(logged_in, run))
    assert paused["status"] == "paused" and paused["reason"] == "step_budget"
    resumed = act(logged_in, paused, "resume", budget={"max_steps": 7})
    with session_factory() as session:
        item = session.get(AgentExecution, resumed["id"])
        item.elapsed_ms = 120000
        session.commit()
    timed = act(logged_in, resumed)
    assert timed["reason"] == "time_budget"
    retry = act(logged_in, start(logged_in, shop, template="margin_review", scope=WINDOW))
    with patch.object(
        ControlledSkills,
        "call",
        side_effect=OperationalError("synthetic", {}, Exception(2013, "synthetic")),
    ) as call:
        for _ in range(3):
            retry = act(logged_in, retry)
        assert retry["status"] == "circuit_open" and call.call_count == 3
        assert act(logged_in, retry)["version"] == retry["version"]


def test_cross_user_cannot_read_or_start_owned_margin_run(logged_in, session_factory, settings):
    shop, _, product = prepared(logged_in)
    run = review(logged_in, shop)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="margin-other", password=TEST_PASSWORD)
        )
    login = logged_in.post(
        "/api/auth/login", json={"username": "margin-other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert logged_in.get(root(shop) + f"/{run['id']}").status_code == 404
    assert logged_in.post(root(shop), json=run["input"]).status_code == 404
    own = create_shop(logged_in, code="margin-own")
    denied = review(logged_in, own, product_id=product["product_id"])
    assert denied["reason"] == "not_found"


def test_listing_inherited_old_batch_is_part_of_agent_clear_chain(logged_in):
    shop, old_batch, _ = prepared(logged_in, content=True)
    imported(logged_in, shop, PARAMETERS.replace("400ml", "500ml"), "products")
    product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[0]
    fresh = generate(logged_in, shop, product)
    edited = revise(
        logged_in,
        shop,
        fresh,
        {"title": "Test Cup", "description": "Material: Steel"},
        active=fresh["base_version_id"],
    )
    assert decide(logged_in, shop, edited).status_code == 200
    run = review(logged_in, shop, product_id=product["product_id"])
    assert run["result"]["listing"]["missing_parameters"] == ["Capacity: 500ml"]
    withdraw(logged_in, old_batch, "clear")
    cleared = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert cleared["source_status"] == "cleared"
    assert all(s["input"] is None and s["output"] is None for s in cleared["steps"])


def test_candidate_summary_is_bounded_but_counts_full_range(logged_in):
    shop = create_shop(logged_in)
    products = "sku,name,facts,price,currency,unit_cost,cost_currency\n" + "".join(
        f"M{i:02},Cup,Steel,10,USD,9.5,USD\n" for i in range(22)
    )
    orders = ORDER_HEADER + "".join(
        f"O{i},1,M{i:02},2,10,USD,2026-10-07 08:30:00,paid,0,0\n" for i in range(22)
    )
    imported(logged_in, shop, products, "products")
    imported(logged_in, shop, orders, "orders")
    run = review(logged_in, shop, margin_cost_mode="current_estimate")
    assert run["result"]["candidate_count"] == 22
    assert len(run["result"]["candidates"]) == 20
    assert run["result"]["recommendations"][0]["kind"] == "cost"
    metrics = next(s["output"] for s in run["steps"] if s["skill"] == "metrics")
    assert len(metrics["candidates"]) == 22 and Decimal(metrics["summary"]["gross_profit"]) == 22
