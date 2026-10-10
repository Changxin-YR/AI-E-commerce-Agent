from datetime import timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select, update

from app.core.time import utc_now
from app.models.agent import AgentExecution
from app.models.operations import OperationTask
from tests.test_agent import act, start
from tests.test_business_rules import save as save_rule
from tests.test_operation_rechecks import KINDS, get, setup, updated
from tests.test_operations import change
from tests.test_support import withdraw
from tests.test_workbench import page


@pytest.mark.parametrize("kind", KINDS)
def test_home_matches_task_review_through_source_lifecycle(logged_in, kind):
    shop, task, original, base = setup(logged_in, kind)

    def verify(view):
        detail = get(logged_in, shop, task)
        item = next(
            r
            for r in page(logged_in, shop_id=shop, kind="operation_task")["items"]
            if r["id"] == task["id"]
        )
        assert item["business_state"] == detail["business_state"]
        assert item["review_current"] == detail["review_current"]
        assert item["view"] == view
        return item

    verify("attention")
    task = change(logged_in, shop, task, "complete")
    assert verify("attention")["business_state"] == "checked_pending"
    assert not page(logged_in, shop_id=shop, view="ai_completed")["items"]
    task = change(logged_in, shop, task, "wait_source")
    verify("update_data")
    updated(logged_in, shop, kind, base, False)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert verify("attention")["business_state"] == "still_anomalous"
    latest = updated(logged_in, shop, kind, base, True)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    item = verify(None)
    assert item["source_status"] == "stale" and item["business_state"] == "resolved"
    assert (
        page(logged_in, shop_id=shop, kind="operation_task", view="update_data")["view_counts"].get(
            "update_data", 0
        )
        == 0
    )
    latest = withdraw(logged_in, latest, "revoke")
    verify("update_data")
    withdraw(logged_in, latest, "clear")
    assert verify(None)["business_state"] == "cleared"


@pytest.mark.parametrize("invalidate", ["rule", "expiry", "ignored"])
def test_review_rule_expiry_and_disposition_match_detail(logged_in, session_factory, invalidate):
    shop, task, _, base = setup(logged_in, "low_inventory")
    updated(logged_in, shop, "low_inventory", base, True)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    if invalidate == "rule":
        save_rule(logged_in, shop)
    if invalidate == "ignored":
        task = change(logged_in, shop, task, "ignore")
    now = utc_now()
    if invalidate == "expiry":
        with session_factory() as session:
            stored = session.get(OperationTask, task["id"])
            review = dict(stored.review)
            review["recheck"] = dict(review["recheck"], valid_until=now.isoformat() + "+00:00")
            stored.review = review
            session.commit()
    with (
        patch("app.services.workbench.utc_now", return_value=now),
        patch("app.services.operations.utc_now", return_value=now),
    ):
        detail = get(logged_in, shop, task)
        item = page(logged_in, kind="operation_task")["items"][0]
        assert (item["business_state"], item["review_current"]) == (
            detail["business_state"],
            detail["review_current"],
        )
        assert item["view"] == (None if invalidate == "ignored" else "update_data")


def test_three_views_use_full_counts_stable_cursor_and_original_buckets(logged_in, session_factory):
    shop, task, _, _ = setup(logged_in, "order_review")
    # Each execution really runs through the controlled daily skills and approval.
    for _ in range(22):
        execution = act(logged_in, start(logged_in, shop))
        execution = act(logged_in, act(logged_in, execution, "approve"))
        execution = act(logged_in, execution)
        assert execution["status"] == "succeeded"
    with session_factory() as session:
        session.execute(update(AgentExecution).values(created_at=utc_now()))
        session.commit()
    first = page(logged_in, shop_id=shop, view="ai_completed")
    assert len(first["items"]) == 20 and first["view_counts"]["ai_completed"] == 22
    assert first["counts"]["history"] >= 22
    second = page(logged_in, shop_id=shop, view="ai_completed", cursor=first["next_cursor"])
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}
    assert (
        logged_in.get(
            "/api/workbench",
            params=dict(shop_id=shop, view="attention", cursor=first["next_cursor"]),
        ).status_code
        == 422
    )
    with session_factory() as session:
        one = session.scalar(select(AgentExecution).order_by(AgentExecution.id))
        one.valid_until = utc_now() - timedelta(seconds=1)
        session.commit()
    data = page(logged_in, shop_id=shop, kind="agent", view="update_data")
    assert len(data["items"]) == data["view_counts"]["update_data"] == 1
    assert data["view_counts"]["ai_completed"] == 21
    assert page(logged_in, data_identity="user_import")["view_counts"] == {}
