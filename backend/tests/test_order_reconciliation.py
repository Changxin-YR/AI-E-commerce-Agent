from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.identity import AuditEvent, User
from app.models.imports import StatementLine
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.order_reconciliation import OrderReconciliationScope
from app.services.auth import AuthService
from app.services.order_reconciliation import OrderReconciliationService
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import ORDER_HEADER, commit, create_shop, preview, upload
from tests.test_statements import SCOPE, file, line, withdraw

BASIS = {
    "sale_basis": "merchandise_after_discount",
    "basis_note": "Synthetic: discounted merchandise before refund, excluding tax/shipping",
}


def order(**changes: Any) -> str:
    values = {
        "order_id": "O1",
        "line_id": "1",
        "sku": "001",
        "quantity": "2",
        "unit_price": "19.9999",
        "currency": "USD",
        "ordered_at": "2026-10-07 08:30:00",
        "status": "paid",
        "discount": "1.0001",
        "refund": "0",
        **changes,
    }
    return ",".join(values.values()) + "\n"


def sale(**changes: Any) -> dict[str, str]:
    return line(
        entry_type="sale", fee_name="", evidence_ref="", order_id="O1", amount="38.9997", **changes
    )


def root(shop: int) -> str:
    return f"/api/shops/{shop}/statements/orders/reconcile"


def reconcile(client: TestClient, shop: int, **scope: Any) -> dict[str, Any]:
    response = client.post(root(shop), json=SCOPE | BASIS | scope)
    assert response.status_code == 200, response.text
    return response.json()


def test_decimal_declared_basis_provenance_read_only_and_repeatable(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in, shop, ORDER_HEADER + order(status="partially_refunded", refund="3"), "orders"
    )
    imported(logged_in, shop, file(sale()), "statements")
    with session_factory() as session:
        before = session.scalar(select(func.count()).select_from(AuditEvent))
    result = reconcile(logged_in, shop)
    comparison = result["comparisons"][0]
    assert comparison["status"] == "matched"
    assert comparison["order_amount"] == "38.9997" and comparison["difference"] == "0.0000"
    assert result["comparisons"][1]["status"] == "pending"
    assert result["coverage"] == "unknown"
    assert result["statements"][0]["occurred_at"] == "2026-10-07T00:30:00.123456Z"
    for item in result["orders"] + result["statements"]:
        source = item["source"]
        detail = logged_in.get(f"/api/shops/{shop}/analytics/sources/{source['row_id']}").json()
        assert detail["raw"]["order_id"] == "O1"
    again = reconcile(logged_in, shop)
    assert result | {"calculated_at": ""} == again | {"calculated_at": ""}
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditEvent)) == before
        assert session.scalar(select(StatementLine.amount)) == Decimal("38.9997")
    unknown = reconcile(logged_in, shop, sale_basis="unknown", basis_note="")
    assert unknown["comparisons"][0]["difference"] is None
    assert "sale_basis_unknown" in unknown["comparisons"][0]["reasons"]


@pytest.mark.parametrize("amount,expected", [("39.0001", "0.0004"), ("1", "-37.9997")])
def test_difference_direction(logged_in: TestClient, amount: str, expected: str) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDER_HEADER + order(), "orders")
    imported(logged_in, shop, file(line(**(sale() | {"amount": amount}))), "statements")
    item = reconcile(logged_in, shop)["comparisons"][0]
    assert item["status"] == "amount_difference" and item["difference"] == expected


@pytest.mark.parametrize(
    "order_change,bill_change,reason",
    [
        ({"discount": ""}, {}, "discount_unknown"),
        ({"status": "pending"}, {}, "order_status_uncomparable"),
        ({"status": "cancelled"}, {}, "order_status_uncomparable"),
        ({"status": "test"}, {}, "order_status_uncomparable"),
        ({}, {"currency": "CNY"}, "currency_mismatch"),
        ({"ordered_at": "2026-10-06 08:30:00"}, {}, "outside_window"),
        ({}, {"occurred_at": "2026-10-08T00:00:00+08:00"}, "outside_window"),
        ({}, {"order_id": "o1"}, "statement_not_imported"),
        ({}, {"order_id": "Ｏ１"}, "statement_not_imported"),
    ],
)
def test_unknowns_never_compute(
    logged_in: TestClient, order_change: dict[str, str], bill_change: dict[str, str], reason: str
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDER_HEADER + order(**order_change), "orders")
    imported(logged_in, shop, file(sale() | bill_change), "statements")
    result = reconcile(logged_in, shop)
    assert reason in result["comparisons"][0]["reasons"]
    assert all(c["difference"] is None and c["order_amount"] is None for c in result["comparisons"])


def test_cross_date_inside_window_and_explicit_local_day(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDER_HEADER + order(ordered_at="2026-10-06T23:59:00Z"), "orders")
    imported(logged_in, shop, file(sale() | {"occurred_at": "2026-10-07T00:01:00Z"}), "statements")
    assert reconcile(logged_in, shop)["comparisons"][0]["status"] == "matched"
    result = reconcile(logged_in, shop, timezone="UTC", start_at="2026-10-06T00:00:00Z")
    assert result["comparisons"][0]["reasons"] == ["different_local_date"]


@pytest.mark.parametrize("side", ["orders", "statements"])
def test_all_dates_lookup_prevents_hidden_duplicates(logged_in: TestClient, side: str) -> None:
    shop = create_shop(logged_in)
    rows = ORDER_HEADER + order()
    bills = [sale()]
    if side == "orders":
        rows += order(line_id="2", ordered_at="2026-10-01 08:30:00")
    else:
        bills.append(sale() | {"line_id": "2", "occurred_at": "2026-10-01T00:30:00Z"})
    imported(logged_in, shop, rows, "orders")
    imported(logged_in, shop, file(*bills), "statements")
    result = reconcile(logged_in, shop)
    item = result["comparisons"][0]
    reason = "multiple_order_lines" if side == "orders" else "multiple_statement_lines"
    assert reason in item["reasons"] and "outside_window" in item["reasons"]
    assert item["difference"] is None
    assert len(result[side]) == 2


def test_refund_cumulative_unknown_missing_reference_and_unrelated_types(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in,
        shop,
        ORDER_HEADER + order(refund="") + order(order_id="O2", refund="3"),
        "orders",
    )
    imported(
        logged_in,
        shop,
        file(
            sale() | {"entry_type": "refund", "amount": "3", "order_id": "O2"},
            sale() | {"line_id": "2", "entry_type": "refund", "amount": "3", "order_id": "O2"},
            sale() | {"line_id": "3", "order_id": ""},
            sale() | {"line_id": "4", "entry_type": "payout"},
            line(line_id="5", order_id="O1"),
        ),
        "statements",
    )
    result = reconcile(logged_in, shop)
    assert len(result["statements"]) == 3
    refunds = [c for c in result["comparisons"] if c["entry_type"] == "refund"]
    assert "refund_amount_unknown" in refunds[0]["reasons"]
    assert "multiple_statement_lines" in refunds[1]["reasons"]
    assert all("refund_transaction_unknown" in c["reasons"] for c in refunds)
    assert "missing_order_reference" in result["comparisons"][-1]["reasons"]
    assert all(c["difference"] is None for c in result["comparisons"])


def test_window_half_open_empty_is_unknown(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    empty = reconcile(logged_in, shop)
    assert empty["comparisons"] == [] and empty["coverage"] == "unknown"
    imported(
        logged_in,
        shop,
        ORDER_HEADER
        + order(ordered_at="2026-10-07T00:00:00+08:00")
        + order(order_id="OUT", ordered_at="2026-10-08T00:00:00+08:00"),
        "orders",
    )
    imported(
        logged_in,
        shop,
        file(
            sale() | {"occurred_at": "2026-10-07T00:00:00+08:00"},
            sale()
            | {"line_id": "2", "order_id": "OUT", "occurred_at": "2026-10-08T00:00:00+08:00"},
        ),
        "statements",
    )
    result = reconcile(logged_in, shop)
    assert len(result["orders"]) == len(result["statements"]) == 1
    assert result["comparisons"][0]["status"] == "matched"


@pytest.mark.parametrize(
    "scope",
    [
        {"start_at": "2026-10-07"},
        {"end_at": SCOPE["start_at"]},
        {"end_at": "2027-10-09T00:00:00Z"},
        {"timezone": "invalid"},
        {"sale_basis": "gross"},
        {"basis_note": " "},
        {"basis_note": "x" * 501},
        {"confirm": True},
    ],
)
def test_invalid_input(logged_in: TestClient, scope: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    assert logged_in.post(root(shop), json=SCOPE | BASIS | scope).status_code == 422


def test_scope_security_and_csrf(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDER_HEADER + order(), "orders")
    imported(logged_in, shop, file(sale()), "statements")
    other = create_shop(logged_in, "other-shop")
    assert reconcile(logged_in, other)["comparisons"] == []
    assert reconcile(logged_in, shop, data_identity="user_import")["comparisons"] == []
    assert reconcile(logged_in, shop, channel="amazon")["comparisons"] == []
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="second", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "second", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert logged_in.post(root(shop), json=SCOPE | BASIS).status_code == 404
    logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(other), json=SCOPE | BASIS).status_code == 403


def test_current_read_revoke_and_clear(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ORDER_HEADER + order(), "orders")
    original = imported(logged_in, shop, file(sale()), "statements")
    with session_factory() as stale:
        owner = stale.scalar(select(User.id))
        assert owner is not None
        cached = stale.scalar(select(StatementLine))
        assert cached is not None
        replacement = imported(logged_in, shop, file(sale() | {"amount": "40"}), "statements")
        current = OrderReconciliationService(UnitOfWork(stale)).reconcile(
            owner, shop, OrderReconciliationScope.model_validate(SCOPE | BASIS)
        )
        assert current.comparisons[0].difference == Decimal("1.0003")
    withdraw(logged_in, replacement, "revoke")
    assert reconcile(logged_in, shop)["comparisons"][0]["status"] == "matched"
    withdraw(logged_in, original, "clear")
    result = reconcile(logged_in, shop)
    assert result["statements"] == [] and len(result["orders"]) == 1
    assert result["comparisons"][0]["reasons"] == ["statement_not_imported"]


@pytest.mark.parametrize("kind", ["orders", "statements"])
@pytest.mark.parametrize(
    "option,value", [("source_channel", "amazon"), ("data_identity", "user_import")]
)
def test_counterpart_from_another_scope_never_matches(
    logged_in: TestClient, kind: str, option: str, value: str
) -> None:
    shop = create_shop(logged_in)
    opposite = "orders" if kind == "statements" else "statements"
    texts = {"orders": ORDER_HEADER + order(), "statements": file(sale())}
    imported(logged_in, shop, texts[opposite], opposite)
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic-scope.csv",
            "kind": kind,
            "source_channel": "generic",
            "data_identity": "synthetic",
            "timezone": "Asia/Shanghai",
            option: value,
        },
        content=texts[kind].encode(),
    )
    assert response.status_code == 201
    commit(logged_in, preview(logged_in, response.json()))
    result = reconcile(logged_in, shop)
    assert result[kind] == []
    assert result["comparisons"][0]["difference"] is None


@pytest.mark.parametrize(
    "kind,linked",
    [("orders", False), ("statements", False), ("orders", True), ("statements", True)],
)
def test_real_database_limit_rejects_incomplete_results(
    logged_in: TestClient, kind: str, linked: bool
) -> None:
    shop = create_shop(logged_in)
    if kind == "orders":
        rows = ORDER_HEADER + "".join(
            order(
                line_id=str(i),
                ordered_at=("2026-10-01 08:30:00" if linked else "2026-10-07 08:30:00"),
            )
            for i in range(1001)
        )
        if linked:
            imported(logged_in, shop, file(sale()), "statements")
    else:
        rows = file(
            *(
                sale()
                | {
                    "line_id": str(i),
                    "occurred_at": ("2026-10-01T00:30:00Z" if linked else "2026-10-07T00:30:00Z"),
                }
                for i in range(1001)
            )
        )
        if linked:
            imported(logged_in, shop, ORDER_HEADER + order(), "orders")
    commit(logged_in, preview(logged_in, upload(logged_in, shop, rows, kind)))
    response = logged_in.post(root(shop), json=SCOPE | BASIS)
    assert response.status_code == 422 and response.json()["error"]["code"] == "range_too_large"
