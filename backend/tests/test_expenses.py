from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.expenses import Expense, ExpenseRevision, ExpenseSource
from app.models.identity import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseWrite
from app.schemas.identity import AccountInput
from app.services.auth import AuthService
from app.services.expenses import ExpenseService
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import ROWS, calculate, imported, setup_data
from tests.test_imports import PRODUCTS, create_shop


def root(shop: int) -> str:
    return f"/api/shops/{shop}/expenses"


def body(**changes: Any) -> dict[str, Any]:
    return {
        "request_id": str(uuid4()),
        "confirm": True,
        "version": 0,
        "data_identity": "synthetic",
        "channel": "generic",
        "content": {
            "label": "合成包装费",
            "category": "packaging",
            "amount": "12.3456",
            "currency": "USD",
            "occurred_at": "2026-10-07T08:30:00+08:00",
            "timezone": "Asia/Shanghai",
            "evidence_ref": "RECEIPT-001",
            "evidence_note": "合成收据：一笔包装支出",
            "allocation": "shop",
            "reason": "依据收据录入",
            **changes,
        },
    }


def write(
    client: TestClient, shop: int, data: dict[str, Any], expense: int | None = None
) -> dict[str, Any]:
    response = client.post(root(shop) + (f"/{expense}" if expense else ""), json=data)
    assert response.status_code == (200 if expense else 201), response.text
    return response.json()


def orders(client: TestClient, shop: int, **changes: Any) -> dict[str, Any]:
    response = client.get(
        root(shop) + "/orders",
        params={"order_id": "O1", "data_identity": "synthetic", "channel": "generic", **changes},
    )
    assert response.status_code == 200, response.text
    return response.json()


def linked(client: TestClient, shop: int, **changes: Any) -> dict[str, Any]:
    available = orders(client, shop)
    order = available["items"][0]
    return body(
        allocation="order_line",
        order_line_id=order["id"],
        expected_source_row_id=order["source"]["row_id"],
        expected_source_revision=available["source_revision"],
        **changes,
    )


def summary(client: TestClient, shop: int, **changes: Any) -> dict[str, Any]:
    response = client.post(
        root(shop) + "/summary",
        json={
            "data_identity": "synthetic",
            "channel": "generic",
            "timezone": "Asia/Shanghai",
            "start_at": "2026-10-07T00:00:00+08:00",
            "end_at": "2026-10-08T00:00:00+08:00",
            **changes,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def control(client: TestClient, shop: int, fee: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"{root(shop)}/{fee['id']}/{action}",
        json={"version": fee["version"], "confirm": True, "request_id": str(uuid4())},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_decimal_utc_history_summary_and_original_profit_unchanged(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, _ = setup_data(logged_in)
    before = calculate(logged_in, shop)
    original = body()
    created = write(logged_in, shop, original)
    changed = body(amount="15.6789", reason="修订收据金额") | {"version": 1}
    updated = write(logged_in, shop, changed, created["id"])
    assert updated["version"] == 2 and len(updated["history"]) == 2
    assert updated["snapshot"]["content"]["amount"] == "15.6789"
    assert updated["history"][1]["snapshot"]["content"]["amount"] == "12.3456"
    assert write(logged_in, shop, original) == updated
    assert write(logged_in, shop, changed, created["id"]) == updated
    result = summary(logged_in, shop)
    assert result["included_count"] == 1 and result["totals"][0]["amount"] == "15.6789"
    assert "费用完整性未知" in " ".join(result["checks"])
    assert "无法确定净利润" in " ".join(result["checks"])
    assert calculate(logged_in, shop)["summary"] == before["summary"]
    with session_factory() as session:
        revision = session.scalar(select(ExpenseRevision).where(ExpenseRevision.version == 1))
        assert revision and revision.amount == Decimal("12.3456")
        assert revision.occurred_at == datetime(2026, 10, 7, 0, 30)
        assert "amount" not in revision.snapshot["content"]


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "NaN"},
        {"amount": "1.12345"},
        {"amount": "100000000000000"},
        {"evidence_note": " "},
        {"evidence_ref": " "},
        {"reason": "x" * 501},
        {"evidence_note": "x" * 1001},
        {"occurred_at": "2026-10-07T08:00:00"},
        {"timezone": "Mars/Test"},
        {"occurred_at": "2026-10-07T08:00:00Z"},
        {"allocation": "order_line"},
        {"order_line_id": 1},
        {"unknown": "field"},
        {"occurred_at": "2026-03-08T02:30:00-05:00", "timezone": "America/New_York"},
    ],
)
def test_invalid_fields_rejected(logged_in: TestClient, change: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    response = logged_in.post(root(shop), json=body(**change))
    assert response.status_code == 422, response.text


def test_duplicate_scope_confirmation_versions_and_request_binding(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    data = body()
    assert logged_in.post(root(shop), json=data | {"confirm": False}).status_code == 422
    fee = write(logged_in, shop, data)
    assert logged_in.post(root(shop), json=body(evidence_ref=" receipt-001 ")).status_code == 409
    assert logged_in.post(root(shop), json=data | {"channel": "other"}).status_code == 409
    assert (
        logged_in.post(f"{root(shop)}/{fee['id']}", json=body() | {"version": 0}).status_code == 409
    )
    assert (
        logged_in.post(
            f"{root(shop)}/{fee['id']}",
            json=body() | {"version": 1, "data_identity": "user_import"},
        ).status_code
        == 409
    )
    write(logged_in, shop, body() | {"channel": "other"})
    write(logged_in, shop, body() | {"data_identity": "user_import"})
    assert summary(logged_in, shop)["included_count"] == 1
    params = {"data_identity": "synthetic", "channel": "generic"}
    assert len(logged_in.get(root(shop), params=params).json()["items"]) == 1


def test_order_link_scope_currency_and_source_revision(logged_in: TestClient) -> None:
    shop, _, _ = setup_data(logged_in)
    assert len(orders(logged_in, shop)["items"]) == 2
    assert orders(logged_in, shop, data_identity="user_import")["items"] == []
    assert orders(logged_in, shop, channel="other")["items"] == []
    data = linked(logged_in, shop)
    mismatch = {**data, "content": {**data["content"], "currency": "EUR"}}
    assert logged_in.post(root(shop), json=mismatch).status_code == 422
    wrong_identity = {**data, "data_identity": "user_import"}
    assert logged_in.post(root(shop), json=wrong_identity).status_code == 409
    fee = write(logged_in, shop, data)
    assert fee["snapshot"]["order_id"] == "O1" and fee["snapshot"]["line_id"] == "1"
    assert fee["snapshot"]["source"]["data_identity"] == "synthetic"
    assert (
        summary(logged_in, shop)["totals"][0]["amount"] == "12.3456"
    )  # not multiplied by quantity
    imported(logged_in, shop, PRODUCTS.replace("Travel Mug", "Changed Mug"), "products")
    stale = logged_in.get(f"{root(shop)}/{fee['id']}").json()
    assert stale["status"] == "stale" and stale["version"] > fee["version"]
    assert summary(logged_in, shop)["stale_count"] == 1
    retry = body(**data["content"]) | {"version": stale["version"]}
    assert logged_in.post(f"{root(shop)}/{fee['id']}", json=retry).status_code == 409
    updated = write(
        logged_in, shop, linked(logged_in, shop) | {"version": stale["version"]}, fee["id"]
    )
    assert updated["status"] == "active" and summary(logged_in, shop)["included_count"] == 1


def test_history_dependency_clear_and_replay_never_restores(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, source = setup_data(logged_in)
    data = linked(logged_in, shop)
    fee = write(logged_in, shop, data)
    shop_fee = write(logged_in, shop, body(evidence_ref="independent"))
    updated = write(logged_in, shop, body() | {"version": 1}, fee["id"])
    assert updated["snapshot"]["source"] is None
    response = logged_in.post(
        f"/api/imports/{source['id']}/clear", json={"version": source["version"]}
    )
    assert response.status_code == 200, response.text
    cleared = logged_in.get(f"{root(shop)}/{fee['id']}").json()
    assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert all(r["snapshot"] is None for r in cleared["history"])
    assert write(logged_in, shop, data) == cleared
    assert logged_in.get(f"{root(shop)}/{shop_fee['id']}").json()["status"] == "active"
    with session_factory() as session:
        assert not session.scalar(select(ExpenseSource.expense_id))
        for revision in session.scalars(
            select(ExpenseRevision).where(ExpenseRevision.expense_id == fee["id"])
        ):
            assert (
                revision.snapshot is None
                and revision.amount is None
                and revision.occurred_at is None
            )


def test_revoked_order_restoration_does_not_reactivate(logged_in: TestClient) -> None:
    shop, _, _ = setup_data(logged_in)
    fee = write(logged_in, shop, linked(logged_in, shop))
    newer = imported(logged_in, shop, ROWS.replace("19.99", "20.00"), "orders")
    response = logged_in.post(
        f"/api/imports/{newer['id']}/revoke", json={"version": newer["version"]}
    )
    assert response.status_code == 200, response.text
    assert logged_in.get(f"{root(shop)}/{fee['id']}").json()["status"] == "stale"
    assert summary(logged_in, shop)["included_count"] == 0


def test_control_idempotency_withdraw_and_clear(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    data = body()
    fee = write(logged_in, shop, data)
    request = {"version": fee["version"], "confirm": True, "request_id": str(uuid4())}
    url = f"{root(shop)}/{fee['id']}/withdraw"
    response = logged_in.post(url, json=request)
    assert response.status_code == 200
    withdrawn = response.json()
    assert logged_in.post(url, json=request).json() == withdrawn
    assert summary(logged_in, shop)["withdrawn_count"] == 1
    assert (
        logged_in.post(
            f"{root(shop)}/{fee['id']}", json=body() | {"version": withdrawn["version"]}
        ).status_code
        == 409
    )
    cleared = control(logged_in, shop, withdrawn, "clear")
    assert logged_in.post(url, json=request).json() == cleared
    assert write(logged_in, shop, data) == cleared
    assert not cleared["snapshot"]


def test_summary_half_open_separate_currencies_and_current_versions(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    write(logged_in, shop, body(occurred_at="2026-10-07T00:00:00+08:00"))
    write(logged_in, shop, body(evidence_ref="EUR", currency="EUR", amount="3.0001"))
    write(logged_in, shop, body(evidence_ref="END", occurred_at="2026-10-08T00:00:00+08:00"))
    result = summary(logged_in, shop)
    assert result["included_count"] == 2
    assert {t["currency"]: t["amount"] for t in result["totals"]} == {
        "EUR": "3.0001",
        "USD": "12.3456",
    }
    assert summary(logged_in, shop, data_identity="user_import")["totals"] == []
    invalid = {**result["scope"], "end_at": "2028-01-01T00:00:00Z"}
    assert logged_in.post(root(shop) + "/summary", json=invalid).status_code == 422


def test_isolation_csrf_and_audit_rollback(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    data = body()
    with (
        patch.object(UnitOfWork, "record_event", side_effect=RuntimeError("audit unavailable")),
        pytest.raises(RuntimeError),
    ):
        logged_in.post(root(shop), json=data)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Expense)) == 0
        assert session.scalar(select(func.count()).select_from(ExpenseRevision)) == 0
    fee = write(logged_in, shop, data)
    other = create_shop(logged_in, "another")
    assert logged_in.get(f"{root(other)}/{fee['id']}").status_code == 404
    assert (
        logged_in.post(root(shop), json=body(), headers={"X-CSRF-Token": "bad"}).status_code == 403
    )
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="second", password=TEST_PASSWORD)
        )
    login = logged_in.post(
        "/api/auth/login", json={"username": "second", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert logged_in.get(f"{root(shop)}/{fee['id']}").status_code == 404
    assert logged_in.post(root(shop), json=body()).status_code == 404


def test_two_sessions_same_request_commit_once(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    data = ExpenseWrite.model_validate(body())
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner
    barrier = Barrier(2)

    def save_one() -> int:
        with session_factory() as session:
            barrier.wait(timeout=10)
            return ExpenseService(UnitOfWork(session)).write(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: save_one(), range(2)))
    assert results[0] == results[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ExpenseRevision)) == 1


def test_source_purge_atomic_with_expense_history(logged_in: TestClient) -> None:
    shop, _, source = setup_data(logged_in)
    fee = write(logged_in, shop, linked(logged_in, shop))
    with (
        patch.object(UnitOfWork, "record_event", side_effect=RuntimeError("audit unavailable")),
        pytest.raises(RuntimeError),
    ):
        logged_in.post(f"/api/imports/{source['id']}/clear", json={"version": source["version"]})
    assert logged_in.get(f"{root(shop)}/{fee['id']}").json() == fee
    assert logged_in.get(f"/api/imports/{source['id']}").json()["status"] == "committed"


def test_limits_pagination_and_revision_cap(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    fee = write(logged_in, shop, body())
    with session_factory() as session:
        first = session.scalar(select(Expense).where(Expense.id == fee["id"]))
        revision = session.scalar(
            select(ExpenseRevision).where(ExpenseRevision.expense_id == fee["id"])
        )
        assert first is not None and revision is not None
        added = [
            Expense(
                owner_id=first.owner_id,
                shop_id=shop,
                data_identity="synthetic",
                channel="generic",
                allocation="shop",
            )
            for _ in range(1000)
        ]
        session.add_all(added)
        session.flush()
        session.add_all(
            ExpenseRevision(
                expense_id=e.id,
                owner_id=e.owner_id,
                version=1,
                request_id=str(uuid4()),
                request_hash="a" * 64,
                action="create",
                amount=Decimal("1"),
                occurred_at=revision.occurred_at,
                snapshot=revision.snapshot,
            )
            for e in added
        )
        session.add_all(
            ExpenseRevision(
                expense_id=first.id,
                owner_id=first.owner_id,
                version=v,
                request_id=str(uuid4()),
                request_hash="b" * 64,
                action="update",
                amount=Decimal("1"),
                occurred_at=revision.occurred_at,
                snapshot=revision.snapshot,
            )
            for v in range(2, 101)
        )
        first.version = first.content_version = 100
        session.commit()
    result = summary(logged_in, shop, channel="other")
    assert result["included_count"] == 0
    assert (
        logged_in.post(
            root(shop) + "/summary", json=result["scope"] | {"channel": "generic"}
        ).status_code
        == 422
    )
    params = {"data_identity": "synthetic", "channel": "generic"}
    page = logged_in.get(root(shop), params=params).json()
    next_page = logged_in.get(root(shop), params=params | {"before": page["next_cursor"]}).json()
    assert len(page["items"]) == len(next_page["items"]) == 20
    assert not {e["id"] for e in page["items"]} & {e["id"] for e in next_page["items"]}
    assert (
        logged_in.post(f"{root(shop)}/{fee['id']}", json=body() | {"version": 100}).status_code
        == 422
    )
    control(logged_in, shop, fee | {"version": 100}, "clear")
    assert summary(logged_in, shop)["included_count"] == 1000


def test_future_time_and_datetime_bounds(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    for timestamp in ["2100-01-01T00:00:00Z", "0001-01-01T00:00:00+08:00"]:
        assert (
            logged_in.post(root(shop), json=body(occurred_at=timestamp, timezone="UTC")).status_code
            == 422
        )
    for timestamp in ["2025-11-02T01:30:00-04:00", "2025-11-02T01:30:00-05:00"]:
        write(
            logged_in,
            shop,
            body(occurred_at=timestamp, timezone="America/New_York", evidence_ref=timestamp),
        )


def test_update_and_clear_audit_failure_roll_back(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    fee = write(logged_in, shop, body())
    for action in ["update", "clear"]:
        with (
            patch.object(UnitOfWork, "record_event", side_effect=RuntimeError("audit unavailable")),
            pytest.raises(RuntimeError),
        ):
            if action == "update":
                write(logged_in, shop, body(amount="20") | {"version": 1}, fee["id"])
            else:
                control(logged_in, shop, fee, "clear")
        assert logged_in.get(f"{root(shop)}/{fee['id']}").json() == fee
