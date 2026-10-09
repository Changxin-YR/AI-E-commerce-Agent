from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError, NotFoundError
from app.models.identity import User
from app.models.statement_reviews import (
    StatementReview,
    StatementReviewRevision,
    StatementReviewSource,
)
from app.repositories.statement_reviews import StatementReviewRepository
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.statement_reviews import ReviewWrite
from app.services.statement_reviews import StatementReviewService
from tests.test_analytics import imported, setup_data
from tests.test_expenses import body, linked
from tests.test_expenses import control as expense_control
from tests.test_expenses import write as expense_write
from tests.test_fee_rules import control as rule_control
from tests.test_fee_rules import draft as rule_draft
from tests.test_fee_rules import request as rule_request
from tests.test_fee_rules import write as rule_write
from tests.test_imports import create_shop
from tests.test_statements import SCOPE, file, line, reconcile, withdraw


def root(shop: int) -> str:
    return f"/api/shops/{shop}/statement-reviews"


def draft(outcome: str = "pending", **changes: Any) -> dict[str, Any]:
    return {
        "scope": SCOPE,
        "review_id": None,
        "version": 0,
        "conclusion": {"outcome": outcome, "note": "合成核对依据与差异说明"},
        **changes,
    }


def request(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    response = client.post(root(shop) + "/preview", json=data)
    assert response.status_code == 200, response.text
    return data | {
        "preview_hash": response.json()["preview_hash"],
        "request_id": str(uuid4()),
        "confirm": True,
    }


def write(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    response = client.post(root(shop), json=data)
    assert response.status_code == 200, response.text
    return response.json()


def get(client: TestClient, shop: int, item: dict[str, Any]) -> dict[str, Any]:
    response = client.get(f"{root(shop)}/{item['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def control(client: TestClient, shop: int, item: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"{root(shop)}/{item['id']}/{action}",
        json={"version": item["version"], "request_id": str(uuid4()), "confirm": True},
    )
    assert response.status_code == 200, response.text
    return response.json()


def setup(client: TestClient) -> tuple[int, dict[str, Any], dict[str, Any], dict[str, Any]]:
    shop = create_shop(client)
    batch = imported(client, shop, file(), "statements")
    expense = expense_write(client, shop, body())
    rule = rule_write(client, shop, rule_request(client, shop, rule_draft()))
    return shop, batch, expense, rule


def test_preview_save_current_history_and_clear(logged_in: TestClient) -> None:
    shop, _, _, _ = setup(logged_in)
    original = reconcile(logged_in, shop)
    data = request(logged_in, shop, draft("consistent"))
    saved = write(logged_in, shop, data)
    assert saved == write(logged_in, shop, data) == get(logged_in, shop, saved)
    assert saved["snapshot"]["result"]["comparisons"][0]["difference"] == "0.0000"
    assert saved["snapshot"]["result"]["statements"] == original["statements"]
    assert saved["snapshot"]["blockers"] == []
    revised = write(
        logged_in, shop, request(logged_in, shop, draft(review_id=saved["id"], version=1))
    )
    assert revised["version"] == 2 and len(revised["history"]) == 2
    old = logged_in.get(f"{root(shop)}/{saved['id']}?version=1").json()
    assert old["snapshot"]["conclusion"]["outcome"] == "consistent"
    current = logged_in.get(f"{root(shop)}/{saved['id']}/current").json()
    assert current["preview"]["snapshot"]["conclusion"]["outcome"] == "pending"
    assert current["record"] == revised
    assert get(logged_in, shop, saved) == revised
    withdrawn = control(logged_in, shop, revised, "withdraw")
    assert withdrawn["status"] == "withdrawn" and withdrawn["snapshot"]
    cleared = control(logged_in, shop, withdrawn, "clear")
    assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert all(h["conclusion"] is None for h in cleared["history"])
    assert write(logged_in, shop, data) == cleared
    assert logged_in.get(f"{root(shop)}/{saved['id']}?version=1").json()["snapshot"] is None
    cleared_current = logged_in.get(f"{root(shop)}/{saved['id']}/current").json()
    assert cleared_current == {"record": cleared, "preview": None}
    assert logged_in.get(f"{root(shop)}/{saved['id']}?version=999").status_code == 404
    assert reconcile(logged_in, shop)["statements"] == original["statements"]


@pytest.mark.parametrize(
    "case",
    ["empty", "missing", "duplicate", "currency", "unmapped", "category", "withdrawn", "stale"],
)
def test_unresolved_only_allows_pending(logged_in: TestClient, case: str) -> None:
    if case == "empty":
        shop = create_shop(logged_in)
    elif case == "stale":
        shop, _, _ = setup_data(logged_in)
        expense_write(logged_in, shop, linked(logged_in, shop))
        imported(logged_in, shop, file(), "statements")
    else:
        shop, _, fee, rule = setup(logged_in)
        if case == "missing":
            expense_control(logged_in, shop, fee, "clear")
        elif case == "duplicate":
            imported(logged_in, shop, file(line(line_id="2")), "statements")
        elif case == "currency":
            imported(logged_in, shop, file(line(currency="CNY")), "statements")
        elif case == "unmapped":
            rule_control(logged_in, shop, rule, "withdraw")
        elif case == "category":
            rule_write(
                logged_in,
                shop,
                rule_request(
                    logged_in,
                    shop,
                    rule_draft(category="platform") | {"rule_id": rule["id"], "version": 1},
                ),
            )
        elif case == "withdrawn":
            expense_control(logged_in, shop, fee, "withdraw")
    for outcome in ("consistent", "differences_recorded"):
        assert logged_in.post(root(shop) + "/preview", json=draft(outcome)).status_code == 422
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    assert saved["snapshot"]["blockers"]
    assert saved["snapshot"]["conclusion"]["outcome"] == "pending"


def test_amount_difference_explanation_is_not_payment(logged_in: TestClient) -> None:
    shop, _, _, _ = setup(logged_in)
    assert (
        logged_in.post(root(shop) + "/preview", json=draft("differences_recorded")).status_code
        == 422
    )
    imported(logged_in, shop, file(line(amount="15")), "statements")
    assert logged_in.post(root(shop) + "/preview", json=draft("consistent")).status_code == 422
    saved = write(logged_in, shop, request(logged_in, shop, draft("differences_recorded")))
    assert saved["snapshot"]["result"]["comparisons"][0]["difference"] == "2.6544"
    assert saved["snapshot"]["result"]["comparisons"] == reconcile(logged_in, shop)["comparisons"]


@pytest.mark.parametrize(
    "change",
    [
        "source_restore",
        "expense_restore",
        "expense_set_restore",
        "rule_restore",
        "rule_set_restore",
    ],
)
def test_change_and_restore_never_revives_confirmation(logged_in: TestClient, change: str) -> None:
    shop, _, fee, rule = setup(logged_in)
    data = request(logged_in, shop, draft())
    saved = write(logged_in, shop, data)
    pending = request(logged_in, shop, draft(review_id=saved["id"], version=1))
    new_preview = request(logged_in, shop, draft())
    if change == "source_restore":
        replaced = imported(logged_in, shop, file(line(amount="20")), "statements")
        withdraw(logged_in, replaced, "revoke")
    elif change == "expense_restore":
        updated = expense_write(logged_in, shop, body(amount="20") | {"version": 1}, fee["id"])
        expense_write(logged_in, shop, body() | {"version": updated["version"]}, fee["id"])
    elif change == "expense_set_restore":
        other = expense_write(
            logged_in, shop, body(evidence_ref="NEW", occurred_at="2026-09-01T00:00:00+08:00")
        )
        expense_control(logged_in, shop, other, "clear")
    elif change == "rule_restore":
        updated = rule_write(
            logged_in,
            shop,
            rule_request(
                logged_in,
                shop,
                rule_draft(category="platform") | {"rule_id": rule["id"], "version": 1},
            ),
        )
        rule_write(
            logged_in,
            shop,
            rule_request(
                logged_in,
                shop,
                rule_draft() | {"rule_id": rule["id"], "version": updated["version"]},
            ),
        )
    else:
        other = rule_write(
            logged_in, shop, rule_request(logged_in, shop, rule_draft(fee_name="UNUSED"))
        )
        rule_control(logged_in, shop, other, "withdraw")
    assert get(logged_in, shop, saved)["status"] == "stale"
    assert logged_in.post(root(shop), json=pending).status_code == 409
    assert logged_in.post(root(shop), json=new_preview).status_code == 409
    # Idempotent replay returns the current stale record, never the original success.
    assert write(logged_in, shop, data)["status"] == "stale"
    stale = get(logged_in, shop, saved)
    renewed = write(
        logged_in,
        shop,
        request(logged_in, shop, draft(review_id=saved["id"], version=stale["version"])),
    )
    assert renewed["status"] == "active"


@pytest.mark.parametrize("dependency", ["source", "expense", "rule", "expense_ancestor"])
def test_clear_any_historical_dependency_erases_all_versions(
    logged_in: TestClient, session_factory: sessionmaker[Session], dependency: str
) -> None:
    if dependency == "expense_ancestor":
        shop, _, source = setup_data(logged_in)
        fee = expense_write(logged_in, shop, linked(logged_in, shop))
        # The expense no longer exposes its order link, but keeps the historical dependency.
        fee = expense_write(logged_in, shop, body() | {"version": 1}, fee["id"])
        batch = imported(logged_in, shop, file(), "statements")
        rule = rule_write(logged_in, shop, rule_request(logged_in, shop, rule_draft()))
    else:
        shop, batch, fee, rule = setup(logged_in)
        source = batch
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    # Replace all visible evidence with an empty window; old dependencies must remain.
    empty = SCOPE | {"start_at": "2026-09-01T00:00:00Z", "end_at": "2026-09-02T00:00:00Z"}
    saved = write(
        logged_in,
        shop,
        request(logged_in, shop, draft(review_id=saved["id"], version=1, scope=empty)),
    )
    if dependency in {"source", "expense_ancestor"}:
        withdraw(logged_in, source, "clear")
    elif dependency == "expense":
        expense_control(logged_in, shop, fee, "clear")
    else:
        rule_control(logged_in, shop, rule, "clear")
    cleared = get(logged_in, shop, saved)
    assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert all(h["conclusion"] is None for h in cleared["history"])
    with session_factory() as session:
        assert not session.scalar(
            select(StatementReviewRevision.id).where(
                StatementReviewRevision.review_id == saved["id"],
                StatementReviewRevision.snapshot.is_not(None),
            )
        )
        assert not session.scalar(
            select(StatementReviewSource.review_id).where(
                StatementReviewSource.review_id == saved["id"]
            )
        )


@pytest.mark.parametrize(
    "operation", ["create", "update", "clear", "source_clear", "expense_clear", "rule_clear"]
)
def test_audit_failure_rolls_back_entire_transaction(
    logged_in: TestClient, session_factory: sessionmaker[Session], operation: str
) -> None:
    shop, batch, fee, rule = setup(logged_in)
    data = request(logged_in, shop, draft())
    saved = write(logged_in, shop, data)
    if operation == "update":
        data = request(logged_in, shop, draft(review_id=saved["id"], version=1))
    elif operation == "create":
        data = request(logged_in, shop, draft())
    with (
        patch.object(
            UnitOfWork, "record_event", side_effect=RuntimeError("synthetic audit failure")
        ),
        pytest.raises(RuntimeError),
    ):
        if operation in {"create", "update"}:
            logged_in.post(root(shop), json=data)
        elif operation == "clear":
            control(logged_in, shop, saved, "clear")
        elif operation == "source_clear":
            withdraw(logged_in, batch, "clear")
        elif operation == "expense_clear":
            expense_control(logged_in, shop, fee, "clear")
        else:
            rule_control(logged_in, shop, rule, "clear")
    assert get(logged_in, shop, saved) == saved
    assert reconcile(logged_in, shop)["mappings"][0]["status"] == "mapped"
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StatementReview)) == 1


def test_scope_permissions_bounded_input_and_tamper(logged_in: TestClient) -> None:
    shop, _, _, _ = setup(logged_in)
    data = request(logged_in, shop, draft())
    assert logged_in.post(root(shop), json=data | {"confirm": False}).status_code == 422
    assert logged_in.post(root(shop), json=data | {"unexpected": True}).status_code == 422
    assert logged_in.post(root(shop), json=data | {"preview_hash": "0" * 64}).status_code == 409
    assert (
        logged_in.post(
            root(shop), json=data | {"conclusion": {"outcome": "pending", "note": "x" * 1001}}
        ).status_code
        == 422
    )
    assert (
        logged_in.post(
            root(shop), json=data | {"conclusion": {"outcome": "pending", "note": " "}}
        ).status_code
        == 422
    )
    saved = write(logged_in, shop, data)
    assert (
        logged_in.post(
            root(shop), json=data | {"conclusion": {"outcome": "pending", "note": "changed"}}
        ).status_code
        == 409
    )
    assert logged_in.get(f"{root(shop + 10000)}/{saved['id']}").status_code == 404
    wrong = draft(review_id=saved["id"], version=1, scope=SCOPE | {"data_identity": "user_import"})
    assert logged_in.post(root(shop) + "/preview", json=wrong).status_code == 409
    assert (
        logged_in.get(
            root(shop), params={"data_identity": "user_import", "channel": "generic"}
        ).json()["items"]
        == []
    )
    assert (
        logged_in.get(
            root(shop), params={"data_identity": "synthetic", "channel": "amazon"}
        ).json()["items"]
        == []
    )
    csrf = logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(shop), json=data).status_code == 403
    logged_in.headers["X-CSRF-Token"] = csrf


def test_concurrent_uuid_only_one_revision(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, _, _ = setup(logged_in)
    data = ReviewWrite.model_validate(request(logged_in, shop, draft()))
    with session_factory() as session:
        owner = session.scalar(select(User.id))
        assert owner
    barrier = Barrier(2)

    def save() -> int:
        with session_factory() as session:
            barrier.wait(timeout=10)
            return StatementReviewService(UnitOfWork(session)).write(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: save(), range(2)))
    assert results[0] == results[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StatementReviewRevision)) == 1


def test_current_read_does_not_restore_and_independent_scope_survives(
    logged_in: TestClient,
) -> None:
    shop, _, _, _ = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    other = expense_write(logged_in, shop, body(evidence_ref="OTHER") | {"channel": "amazon"})
    expense_control(logged_in, shop, other, "clear")
    assert get(logged_in, shop, saved)["status"] == "active"
    expense_write(logged_in, shop, body(evidence_ref="NEW"))
    current = logged_in.get(f"{root(shop)}/{saved['id']}/current").json()
    assert current["record"]["status"] == "stale"
    assert len(current["preview"]["snapshot"]["result"]["comparisons"]) == 2
    assert get(logged_in, shop, saved)["status"] == "stale"


def test_list_cursor_has_no_evidence_bodies(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    ids = []
    for _ in range(22):
        ids.append(write(logged_in, shop, request(logged_in, shop, draft()))["id"])
    params: dict[str, Any] = {"data_identity": "synthetic", "channel": "generic"}
    first = logged_in.get(root(shop), params=params).json()
    assert len(first["items"]) == 20
    assert all(i["snapshot"] is None and not i["history"] for i in first["items"])
    second = logged_in.get(root(shop), params=params | {"before": first["next_cursor"]}).json()
    assert [i["id"] for i in second["items"]] == list(reversed(ids[:2]))
    assert second["next_cursor"] is None


def test_current_lock_refreshes_old_orm_and_repeatable_read_snapshot(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, fee, _ = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    with session_factory() as session:
        old = session.get(StatementReview, saved["id"])
        assert old and old.status == "active"
        expense_write(logged_in, shop, body(amount="20") | {"version": fee["version"]}, fee["id"])
        assert old.status == "active"
        result = StatementReviewService(UnitOfWork(session)).get(old.owner_id, shop, old.id)
        assert result.status == "stale" and result.version == 2


def test_other_owner_cannot_read_or_clear(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, _, _ = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    with session_factory() as session:
        user = User(username="other", password_hash="unused")
        session.add(user)
        session.commit()
        with pytest.raises(NotFoundError):
            StatementReviewService(UnitOfWork(session)).get(user.id, shop, saved["id"])
    assert get(logged_in, shop, saved) == saved


def test_revision_and_dependency_caps_keep_clear_available(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, _, _ = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    with patch.object(StatementReviewRepository, "history", return_value=[None] * 100):
        assert (
            logged_in.post(
                root(shop) + "/preview", json=draft(review_id=saved["id"], version=1)
            ).status_code
            == 422
        )
    with session_factory() as session:
        review = session.get(StatementReview, saved["id"])
        assert review
        with pytest.raises(BusinessError, match="10000"):
            StatementReviewRepository(session).dependencies(review, set(range(10001)), set(), set())
        session.rollback()
    assert control(logged_in, shop, saved, "clear")["snapshot"] is None


def test_unrelated_archive_survives_dependency_clear(logged_in: TestClient) -> None:
    shop, batch, _, _ = setup(logged_in)
    dependent = write(logged_in, shop, request(logged_in, shop, draft()))
    independent = write(
        logged_in, shop, request(logged_in, shop, draft(scope=SCOPE | {"channel": "amazon"}))
    )
    withdraw(logged_in, batch, "clear")
    assert get(logged_in, shop, dependent)["snapshot"] is None
    # Shop source changes conservatively invalidate, but unrelated history is retained.
    other = get(logged_in, shop, independent)
    assert other["status"] == "stale" and other["snapshot"] is not None
