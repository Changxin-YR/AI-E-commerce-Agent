"""B1 source validity must be visible before visiting or mutating the task."""

import pytest
from sqlalchemy import event, func, select

from app.models.agent import AgentExecution, AgentStep
from app.models.identity import AuditEvent
from app.models.listings import ListingVersion
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from tests.conftest import TEST_PASSWORD
from tests.test_agent import act, root
from tests.test_analytics import imported
from tests.test_imports import create_shop
from tests.test_listings import decide, generate, revise
from tests.test_margin_review import ORDER, PARAMETERS, finish_write, prepared, review
from tests.test_support import withdraw
from tests.test_workbench import page


def test_b1_inbox_reflects_changed_listing_before_opening_task(logged_in):
    shop, _, product = prepared(logged_in, history="1", content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    assert run["next_node"] == "product_context"
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    home = page(logged_in, shop_id=shop, kind="agent")
    item = next(item for item in home["items"] if item["id"] == run["id"])
    assert item["source_status"] == "stale"
    assert item["view"] == "update_data"
    assert home["view_counts"]["update_data"] == 1
    assert home["view_counts"].get("attention", 0) == 0
    detail = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert detail["source_status"] == item["source_status"]


@pytest.mark.parametrize("approved", [False, True])
def test_home_does_not_allow_old_approval_or_repeat_write(logged_in, approved):
    shop, _, product = prepared(logged_in, history="1", content=True)
    run = act(logged_in, review(logged_in, shop, product_id=product["product_id"]))
    if approved:
        run = act(logged_in, run, "approve")
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    before = logged_in.get(f"/api/shops/{shop}/listings/versions").json()
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["view"] == "update_data"
    denied = logged_in.post(
        root(shop) + f"/{run['id']}",
        json={"version": run["version"], "action": "advance" if approved else "approve"},
    )
    assert denied.status_code == 409
    detail = logged_in.get(root(shop) + f"/{run['id']}").json()
    if approved:
        blocked = act(logged_in, detail)
        assert (blocked["status"], blocked["reason"]) == ("blocked", "source_changed")
        assert act(logged_in, blocked)["steps_used"] == blocked["steps_used"]
    else:
        assert (
            logged_in.post(
                root(shop) + f"/{run['id']}",
                json={"version": detail["version"], "action": "approve"},
            ).status_code
            == 409
        )
    assert logged_in.get(f"/api/shops/{shop}/listings/versions").json() == before
    assert logged_in.get(f"/api/shops/{shop}/analytics/saved").json() == []


def test_home_read_only_bounded_queries_counts_pagination_and_relogin(logged_in, session_factory):
    shop, _, product = prepared(logged_in, history="1", content=True)
    first = review(logged_in, shop, product_id=product["product_id"])
    engine = logged_in.app.state.session_factory.kw["bind"]

    def measured(**query):
        statements = []

        def capture(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", capture)
        try:
            result = page(logged_in, shop_id=shop, kind="agent", **query)
        finally:
            event.remove(engine, "before_cursor_execute", capture)
        assert all(sql.lstrip().upper().startswith("SELECT") for sql in statements)
        return result, len(statements)

    _, single_queries = measured()
    runs = [first] + [review(logged_in, shop, product_id=product["product_id"]) for _ in range(21)]
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200

    def state():
        with session_factory() as session:
            return (
                list(
                    session.execute(
                        select(
                            AgentExecution.id,
                            AgentExecution.version,
                            AgentExecution.source_status,
                            AgentExecution.result,
                        )
                    )
                ),
                tuple(
                    session.scalar(select(func.count()).select_from(model))
                    for model in (AgentStep, ListingVersion, AuditEvent)
                ),
            )

    before = state()
    home, many_queries = measured(view="update_data")
    assert many_queries == single_queries
    assert len(home["items"]) == 20 and home["view_counts"] == {"update_data": 22}
    tail, _ = measured(view="update_data", cursor=home["next_cursor"])
    assert len(tail["items"]) == 2 and tail["next_cursor"] is None
    assert {r["id"] for r in home["items"] + tail["items"]} == {r["id"] for r in runs}
    assert all(r["source_status"] == "stale" for r in home["recent_runs"])
    assert state() == before  # no version changes, source events, or internal writes on GET.
    assert logged_in.post("/api/auth/logout").status_code == 204
    login = logged_in.post(
        "/api/auth/login", json={"username": "seller", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    after_login = state()
    assert after_login[0] == before[0]
    assert after_login[1][:2] == before[1][:2]
    assert after_login[1][2] == before[1][2] + 2  # logout/login retain their audit events.
    assert measured(view="update_data")[0]["view_counts"] == {"update_data": 22}
    assert state() == after_login


def test_unrelated_product_and_shop_do_not_invalidate_run(logged_in):
    shop, _, product = prepared(logged_in, history="1", content=True)
    # Prepare the other source before starting, so only Listing approval changes afterwards.
    imported(logged_in, shop, PARAMETERS.replace("001", "002"), "products")
    product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[0]
    baseline = generate(logged_in, shop, product)
    baseline = revise(
        logged_in,
        shop,
        baseline,
        {"title": "Test Cup", "description": "Material: Steel"},
        active=baseline["base_version_id"],
    )
    assert decide(logged_in, shop, baseline).status_code == 200
    other = create_shop(logged_in, code="margin-unrelated")
    imported(logged_in, other, PARAMETERS, "products")
    imported(logged_in, other, ORDER, "orders")
    run = review(logged_in, shop, product_id=product["product_id"])
    other_product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[1]
    foreign_product = logged_in.get(f"/api/shops/{other}/listings/products").json()[0]
    for target_shop, target in [(shop, other_product), (other, foreign_product)]:
        assert (
            decide(logged_in, target_shop, generate(logged_in, target_shop, target)).status_code
            == 200
        )
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["source_status"] == "current"
    assert logged_in.get(root(shop) + f"/{run['id']}").json()["source_status"] == "current"
    assert page(logged_in, shop_id=other, kind="agent")["items"] == []
    assert page(logged_in, channel="amazon", kind="agent")["items"] == []
    assert page(logged_in, data_identity="user_import", kind="agent")["items"] == []


def test_completed_history_and_clear_remain_readable_and_owner_scoped(
    logged_in, session_factory, settings
):
    shop, batch, product = prepared(logged_in, history="1", content=True)
    done = finish_write(
        logged_in, act(logged_in, review(logged_in, shop, product_id=product["product_id"]))
    )
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    home = page(logged_in, shop_id=shop, kind="agent")
    assert home["items"][0]["view"] == "update_data"
    detail = logged_in.get(root(shop) + f"/{done['id']}").json()
    assert detail["status"] == "succeeded" and detail["result"] == done["result"]
    assert detail["steps_used"] == done["steps_used"]
    withdraw(logged_in, batch, "clear")
    assert page(logged_in, shop_id=shop, kind="agent", view="update_data")["items"] == []
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["source_status"] == "cleared"
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="margin-home-other", password=TEST_PASSWORD)
        )
    login = logged_in.post(
        "/api/auth/login", json={"username": "margin-home-other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert page(logged_in, kind="agent")["items"] == []
    assert logged_in.get(root(shop) + f"/{done['id']}").status_code == 404


def test_paused_run_cannot_resume_changed_listing_and_new_run_reads_new_baseline(logged_in):
    shop, _, product = prepared(logged_in, history="1", content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    paused = act(logged_in, run, "pause")
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["source_status"] == "current"
    assert act(logged_in, paused, "resume")["next_node"] == run["next_node"]
    paused = act(logged_in, logged_in.get(root(shop) + f"/{run['id']}").json(), "pause")
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    home = page(logged_in, shop_id=shop, kind="agent")
    assert home["items"][0]["status"] == "paused"
    assert home["view_counts"] == {"update_data": 1}
    detail = logged_in.get(root(shop) + f"/{run['id']}").json()
    assert detail["source_status"] == "stale" and detail["steps_used"] == paused["steps_used"]
    denied = logged_in.post(
        root(shop) + f"/{run['id']}", json={"version": detail["version"], "action": "resume"}
    )
    assert denied.status_code == 409
    fresh = review(logged_in, shop, product_id=product["product_id"])
    assert (fresh["status"], fresh["reason"]) == ("succeeded", "margin_no_action")
    items = {item["id"]: item for item in page(logged_in, shop_id=shop, kind="agent")["items"]}
    assert items[run["id"]]["source_status"] == "stale"
    assert items[fresh["id"]]["source_status"] == "current"


@pytest.mark.parametrize("selected", [False, True])
def test_without_listing_evidence_approval_does_not_invalidate_independent_cost_review(
    logged_in, selected
):
    shop, _, product = prepared(logged_in)
    run = review(logged_in, shop, **({"product_id": product["product_id"]} if selected else {}))
    assert run["result"]["listing"] is None
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    home = page(logged_in, shop_id=shop, kind="agent")
    assert home["items"][0]["source_status"] == "current"
    assert home["view_counts"] == {"attention": 1}
    assert logged_in.get(root(shop) + f"/{run['id']}").json()["source_status"] == "current"
    assert finish_write(logged_in, run)["status"] == "succeeded"


def test_reverted_product_source_preserves_stale_history_and_fresh_run_is_independent(logged_in):
    shop, _, product = prepared(logged_in, history="1", content=True)
    run = review(logged_in, shop, product_id=product["product_id"])
    update = imported(logged_in, shop, PARAMETERS.replace("400ml", "500ml"), "products")
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["source_status"] == "stale"
    withdraw(logged_in, update, "revoke")
    assert page(logged_in, shop_id=shop, kind="agent")["items"][0]["source_status"] == "stale"
    assert logged_in.get(root(shop) + f"/{run['id']}").json()["source_status"] == "stale"
    product = logged_in.get(f"/api/shops/{shop}/listings/products").json()[0]
    assert product["facts"].endswith("Capacity: 400ml")
    assert decide(logged_in, shop, generate(logged_in, shop, product)).status_code == 200
    fresh = review(logged_in, shop, product_id=product["product_id"])
    assert fresh["source_status"] == "current"
    assert page(logged_in, shop_id=shop, kind="agent")["view_counts"] == {
        "update_data": 1,
        "ai_completed": 1,
    }
