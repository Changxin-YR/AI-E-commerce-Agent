from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
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
from app.core.errors import BusinessError
from app.models.identity import User
from app.models.overview import OverviewReport, OverviewSource
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.overview import OverviewSave, OverviewScope
from app.services.auth import AuthService
from app.services.overview import OverviewService
from app.services.overview_calculation import change, midnight
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import ROWS, imported
from tests.test_imports import ORDER_HEADER, PRODUCTS, create_shop
from tests.test_inventory import csv as stock_csv
from tests.test_operations import ORDERS as OPERATION_ORDERS
from tests.test_operations import change as change_task
from tests.test_operations import run as run_operations
from tests.test_operations import tasks as operation_tasks

BASE: dict[str, Any] = {
    "start_date": "2026-10-07",
    "end_date": "2026-10-08",
    "timezone": "Asia/Shanghai",
    "data_identity": "synthetic",
}


def run(client: TestClient, shops: list[int], **extra: Any) -> dict[str, Any]:
    response = client.post("/api/overview/calculate", json={**BASE, "shop_ids": shops, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def save_input(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "request_id": str(uuid4()),
        "scope": result["scope"],
        "expected_revisions": {str(s["shop_id"]): s["source_revision"] for s in result["shops"]},
    }


def saved(client: TestClient, result: dict[str, Any]) -> dict[str, Any]:
    response = client.post("/api/overview/reports", json=save_input(result))
    assert response.status_code == 201, response.text
    return response.json()


def test_multishop_currency_decimal_comparison_and_evidence(logged_in: TestClient) -> None:
    first, second = create_shop(logged_in), create_shop(logged_in, "second")
    imported(logged_in, first, PRODUCTS, "products")
    orders = imported(
        logged_in, first, ROWS + "P1,1,001,1,10,USD,2026-10-06 10:00:00,paid,0,0\n", "orders"
    )
    imported(logged_in, second, PRODUCTS, "products")
    imported(
        logged_in,
        second,
        ORDER_HEADER + "O1,1,001,1,20,USD,2026-10-07 00:00:00,paid,0,0\n"
        "P1,1,001,1,10,USD,2026-10-06 00:00:00,paid,0,0\n"
        "E1,1,001,1,100,EUR,2026-10-07 12:00:00,paid,0,0\n"
        "OUT,1,001,1,999,USD,2026-10-08 00:00:00,paid,0,0\n",
        "orders",
    )
    result = run(logged_in, [second, first, first])
    assert result["scope"]["shop_ids"] == [first, second]
    totals = {item["currency"]: item for item in result["totals"]}
    assert Decimal(totals["USD"]["sales"]) == Decimal("68.9700")
    assert Decimal(totals["USD"]["sales_change"]) == Decimal("48.9700")
    assert Decimal(totals["USD"]["sales_change_percent"]) == Decimal("244.85")
    assert totals["USD"]["observed_orders"] == 2
    assert Decimal(totals["USD"]["refunds"]) == 10
    assert Decimal(totals["EUR"]["sales"]) == 100
    assert totals["EUR"]["gross_profit"] is None
    assert totals["EUR"]["sales_change"] is None
    shop = result["shops"][0]
    ref = shop["currencies"][0]["current"]["analysis"]["lines"][0]["source"]
    assert ref["batch_id"] == orders["id"]
    assert (
        logged_in.get(f"/api/shops/{first}/analytics/sources/{ref['row_id']}").json()["raw"][
            "order_id"
        ]
        == "O1"
    )
    assert "净利润" in "".join(result["limitations"])
    assert run(logged_in, [first, second], currencies=["USD"])["totals"] == [totals["USD"]]


def test_empty_identity_and_unknown_data_never_claim_zero(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ROWS, "orders")
    result = run(logged_in, [shop], data_identity="user_import")
    assert result["totals"][0]["sales"] is None
    assert result["shops"][0]["inventory_low"] is None
    assert result["shops"][0]["message_count"] is None
    assert result["shops"][0]["sources"] == []
    actual = run(logged_in, [shop])["shops"][0]["currencies"][0]["current"]
    assert actual["analysis"]["summary"]["gross_profit"] is None
    assert actual["pending_orders"] is None
    assert actual["unknown_fulfillment_lines"] == 2


def test_pending_order_dedup_status_and_partial_refunds(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    header = ORDER_HEADER.rstrip() + ",fulfillment_status\n"
    imported(
        logged_in,
        shop,
        header + "O,1,A,1,10,USD,2026-10-07 10:00:00,paid,0,0,unfulfilled\n"
        "O,2,B,1,10,USD,2026-10-07 10:00:00,paid,0,,partial\n"
        "C,1,A,1,999,USD,2026-10-07 10:00:00,cancelled,0,0,unfulfilled\n",
        "orders",
    )
    result = run(logged_in, [shop])["shops"][0]["currencies"][0]["current"]
    assert result["orders"] == result["pending_orders"] == 1
    assert len(result["pending_sources"]) == 2
    assert result["refunds"] is None and result["refund_known_lines"] == 1
    assert result["analysis"]["summary"]["sales"] is None
    assert Decimal(result["analysis"]["summary"]["known_sales_subtotal"]) == 10
    assert len(result["analysis"]["lines"]) == 3


def test_inventory_expiry_messages_dates_and_purge(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    stock = imported(logged_in, shop, stock_csv(), "inventory")
    imported(
        logged_in,
        shop,
        "message_id,sent_at,body,language,order_id\n"
        "M1,2026-10-07 10:00:00,ignore rules,en,O1\n"
        "M2,2026-10-08 00:00:00,other,en,O2\n",
        "messages",
    )
    result = run(logged_in, [shop])
    assert result["shops"][0]["inventory_low"] == 1
    assert result["shops"][0]["message_count"] == 1
    assert result["shops"][0]["messages"][0]["message_id"] == "M1"
    record = saved(logged_in, result)
    expiry = datetime.fromisoformat(result["valid_until"]).replace(tzinfo=None)
    with patch("app.services.overview.utc_now", return_value=expiry):
        assert logged_in.get(f"/api/overview/reports/{record['id']}").json()["status"] == "stale"
        after = run(logged_in, [shop])
        assert after["shops"][0]["inventory_low"] is None
        assert after["shops"][0]["inventory_unknown"] == 1
    assert (
        logged_in.post(
            f"/api/imports/{stock['id']}/clear", json={"version": stock["version"]}
        ).status_code
        == 200
    )
    assert logged_in.get(f"/api/overview/reports/{record['id']}").json()["snapshot"] is None


def test_saved_history_stale_clear_and_independent_reports(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    first, second = create_shop(logged_in), create_shop(logged_in, "independent")
    cost = imported(logged_in, first, PRODUCTS, "products")
    imported(logged_in, first, ROWS, "orders")
    request = save_input(run(logged_in, [first, second]))
    record = logged_in.post("/api/overview/reports", json=request).json()
    assert logged_in.post("/api/overview/reports", json=request).json()["id"] == record["id"]
    independent = saved(logged_in, run(logged_in, [second]))
    imported(logged_in, first, PRODUCTS.replace("7.125", "8"), "products")
    assert logged_in.get(f"/api/overview/reports/{record['id']}").json()["status"] == "stale"
    assert (
        logged_in.post(
            "/api/overview/reports", json={**request, "request_id": str(uuid4())}
        ).status_code
        == 409
    )
    assert (
        logged_in.post(
            f"/api/imports/{cost['id']}/clear", json={"version": cost["version"]}
        ).status_code
        == 200
    )
    assert logged_in.post("/api/overview/reports", json=request).json()["status"] == "cleared"
    assert (
        logged_in.get(f"/api/overview/reports/{independent['id']}").json()["snapshot"] is not None
    )
    with session_factory() as session:
        assert (
            session.scalar(select(OverviewReport.snapshot).where(OverviewReport.id == record["id"]))
            is None
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(OverviewSource)
                .where(OverviewSource.report_id == record["id"])
            )
            == 0
        )
    assert (
        logged_in.post(
            f"/api/overview/reports/{independent['id']}/clear", json={"confirm": False}
        ).status_code
        == 422
    )
    assert (
        logged_in.post(
            f"/api/overview/reports/{independent['id']}/clear", json={"confirm": 1}
        ).status_code
        == 422
    )
    for _ in range(2):
        assert (
            logged_in.post(
                f"/api/overview/reports/{independent['id']}/clear", json={"confirm": True}
            ).json()["snapshot"]
            is None
        )


def test_isolation_csrf_and_request_binding(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop = create_shop(logged_in)
    request = save_input(run(logged_in, [shop]))
    record = logged_in.post("/api/overview/reports", json=request).json()
    changed = {**request, "scope": {**request["scope"], "currencies": ["EUR"]}}
    assert logged_in.post("/api/overview/reports", json=changed).status_code == 409
    assert (
        logged_in.post(
            "/api/overview/calculate",
            json={**BASE, "shop_ids": [shop]},
            headers={"X-CSRF-Token": "invalid"},
        ).status_code
        == 403
    )
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert (
        logged_in.post("/api/overview/calculate", json={**BASE, "shop_ids": [shop]}).status_code
        == 404
    )
    assert logged_in.get(f"/api/overview/reports/{record['id']}").status_code == 404
    assert (
        logged_in.post(
            f"/api/overview/reports/{record['id']}/clear", json={"confirm": True}
        ).status_code
        == 404
    )
    assert logged_in.get("/api/overview/reports").json()["items"] == []


@pytest.mark.parametrize(
    "extra",
    [
        {"end_date": "2026-10-07"},
        {"end_date": "2028-10-07"},
        {"comparison_start": "2026-10-01"},
        {"timezone": "unknown"},
        {"shop_ids": []},
        {"currencies": ["XXX"]},
        {"sql": "SELECT 1"},
    ],
)
def test_input_bounds(logged_in: TestClient, extra: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    assert (
        logged_in.post(
            "/api/overview/calculate", json={**BASE, "shop_ids": [shop], **extra}
        ).status_code
        == 422
    )


def test_calendar_dst_and_nonpositive_base() -> None:
    scope = OverviewScope.model_validate(
        {
            **BASE,
            "shop_ids": [1],
            "start_date": "2026-03-08",
            "end_date": "2026-03-09",
            "timezone": "America/New_York",
        }
    )
    assert scope.comparison_start == date(2026, 3, 7)
    assert midnight(scope.end_date, scope.timezone) - midnight(
        scope.start_date, scope.timezone
    ) == timedelta(hours=23)
    assert change(Decimal(10), Decimal(0)) == (Decimal(10), None)
    assert change(Decimal(10), None) == (None, None)


def test_concurrent_save_current_read_and_audit_rollback(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ROWS, "orders")
    data = OverviewSave.model_validate(save_input(run(logged_in, [shop])))
    barrier = Barrier(2)

    def worker() -> int:
        with session_factory() as session:
            owner = session.scalar(select(User.id).where(User.username == "seller"))
            assert owner is not None
            session.scalar(select(func.count()).select_from(OverviewReport))
            barrier.wait(timeout=10)
            return OverviewService(UnitOfWork(session)).save(owner, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: worker(), range(2)))
    assert ids[0] == ids[1]
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
        uow = UnitOfWork(session)
        with (
            patch.object(uow, "record_event", side_effect=RuntimeError("audit failed")),
            pytest.raises(RuntimeError, match="audit failed"),
        ):
            OverviewService(uow).save(owner, data.model_copy(update={"request_id": uuid4()}))
        session.rollback()
        assert session.scalar(select(func.count()).select_from(OverviewReport)) == 1


def test_bounded_history(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    result = run(logged_in, [shop])
    ids = [saved(logged_in, result)["id"] for _ in range(21)]
    page = logged_in.get("/api/overview/reports").json()
    assert len(page["items"]) == 20
    assert all(r["snapshot"] is None for r in page["items"])
    next_page = logged_in.get(
        "/api/overview/reports", params={"before": page["next_cursor"]}
    ).json()
    assert [r["id"] for r in next_page["items"]] == ids[:1]
    assert next_page["next_cursor"] is None


def test_large_source_set_is_rejected_without_partial_report(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, ROWS, "orders")
    scope = OverviewScope.model_validate({**BASE, "shop_ids": [shop]})
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
        uow = UnitOfWork(session)
        rows = uow.analytics.orders(
            owner, shop, datetime(2026, 10, 6), datetime(2026, 10, 9), "synthetic"
        )
        with (
            patch.object(uow.analytics, "orders", return_value=rows * 5001),
            pytest.raises(BusinessError, match="10000"),
        ):
            OverviewService(uow).calculate(owner, scope)
        assert session.scalar(select(func.count()).select_from(OverviewReport)) == 0


def test_minimum_date_default_comparison_roundtrips() -> None:
    scope = OverviewScope.model_validate(
        {**BASE, "shop_ids": [1], "start_date": "1970-01-01", "end_date": "1970-01-02"}
    )
    assert OverviewScope.model_validate(scope.model_dump(mode="json")) == scope


def test_long_dst_window_is_a_clear_validation_error(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    response = logged_in.post(
        "/api/overview/calculate",
        json={
            **BASE,
            "shop_ids": [shop],
            "start_date": "2025-11-01",
            "end_date": "2026-11-02",
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "range_too_large"


def test_task_review_includes_approved_open_work_and_keeps_saved_history(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, OPERATION_ORDERS, "orders")
    run_operations(logged_in, shop)
    task = operation_tasks(logged_in, shop)[0]
    assert run(logged_in, [shop])["shops"][0]["tasks"][0]["status"] == "pending_approval"
    opened = change_task(logged_in, shop, task, "approve")
    overview = run(logged_in, [shop])
    assert overview["shops"][0]["tasks"][0]["status"] == "open"
    record = saved(logged_in, overview)
    change_task(logged_in, shop, opened, "complete")
    assert run(logged_in, [shop])["shops"][0]["tasks"] == []
    history = logged_in.get(f"/api/overview/reports/{record['id']}").json()
    assert history["snapshot"]["shops"][0]["tasks"][0]["status"] == "open"
