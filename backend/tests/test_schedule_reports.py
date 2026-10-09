from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.models.agent import AgentExecution
from app.models.overview import OverviewReport, OverviewSource
from app.models.schedules import OperationSchedule, ScheduleOccurrence
from app.repositories.overview import OverviewRepository
from app.schemas.schedules import ScheduleConfig
from app.services.agent import AgentService
from app.services.overview_calculation import midnight
from app.services.schedule_reports import report_scope
from app.services.scheduler import tick
from app.services.schedules import SchedulesService
from tests.test_analytics import imported
from tests.test_business_rules import save as save_rule
from tests.test_imports import ORDER_HEADER, PRODUCTS, create_shop
from tests.test_schedules import CONFIG, NOW, change, create, due, root
from tests.test_support import withdraw


@pytest.mark.parametrize(
    "frequency,at,zone,start,end,prior,hours",
    [
        (
            "daily",
            "2026-10-08T17:00",
            "Asia/Shanghai",
            "2026-10-08",
            "2026-10-09",
            "2026-10-07",
            24,
        ),
        (
            "weekly",
            "2026-01-05T01:00",
            "Asia/Shanghai",
            "2025-12-29",
            "2026-01-05",
            "2025-12-22",
            168,
        ),
        (
            "monthly",
            "2024-03-01T01:00",
            "Asia/Shanghai",
            "2024-02-01",
            "2024-03-01",
            "2024-01-01",
            696,
        ),
        (
            "monthly",
            "2026-01-01T01:00",
            "Asia/Shanghai",
            "2025-12-01",
            "2026-01-01",
            "2025-11-01",
            744,
        ),
        (
            "daily",
            "2026-03-09T13:00",
            "America/New_York",
            "2026-03-08",
            "2026-03-09",
            "2026-03-07",
            23,
        ),
        (
            "daily",
            "2026-11-02T14:00",
            "America/New_York",
            "2026-11-01",
            "2026-11-02",
            "2026-10-31",
            25,
        ),
        (
            "weekly",
            "2026-03-09T13:00",
            "America/New_York",
            "2026-03-02",
            "2026-03-09",
            "2026-02-23",
            167,
        ),
    ],
)
def test_completed_calendar_windows(
    frequency: str, at: str, zone: str, start: str, end: str, prior: str, hours: int
) -> None:
    config = ScheduleConfig.model_validate(
        {**CONFIG, "task": "report", "frequency": frequency, "timezone": zone}
    )
    scope = report_scope(config, 1, datetime.fromisoformat(at))
    assert str(scope.start_date) == start and str(scope.end_date) == end
    assert str(scope.comparison_start) == prior and scope.comparison_end == scope.start_date
    assert midnight(scope.end_date, zone) - midnight(scope.start_date, zone) == timedelta(
        hours=hours
    )


def report(client: TestClient, shop: int) -> dict[str, Any]:
    notice = client.get(root(shop) + "/history").json()[0]
    assert notice["task"] == "report" and notice["execution_id"] is None
    assert notice["status"] == "succeeded" and notice["report_id"]
    response = client.get(f"/api/overview/reports/{notice['report_id']}")
    assert response.status_code == 200, response.text
    return response.json()


def test_due_report_currency_dates_current_data_evidence_and_clear(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    imported(
        logged_in,
        shop,
        ORDER_HEADER + "PRE,1,001,1,10,USD,2026-10-07 10:00:00,paid,0,0\n",
        "orders",
    )
    source = imported(
        logged_in,
        shop,
        ORDER_HEADER + "CUR,1,001,2,20,USD,2026-10-08 00:00:00,paid,1,0\n"
        "EUR,1,001,1,12,EUR,2026-10-08 23:59:59,paid,0,0\n"
        "END,1,001,1,999,USD,2026-10-09 00:00:00,paid,0,0\n",
        "orders",
    )
    row = create(logged_in, shop, task="report")
    # Reporting has independent thresholds; a new operations rule cannot authorize or block it.
    save_rule(logged_in, shop, max_age_hours=12)
    with patch.object(AgentService, "start", side_effect=AssertionError("report must stay local")):
        assert due(session_factory, shop, row["id"])
    result = report(logged_in, shop)
    assert result["scope"]["start_date"] == "2026-10-08"
    assert result["scope"]["end_date"] == "2026-10-09"
    totals = {g["currency"]: g for g in result["snapshot"]["totals"]}
    assert Decimal(totals["USD"]["sales"]) == 39
    assert Decimal(totals["USD"]["comparison_sales"]) == 10
    assert Decimal(totals["USD"]["gross_profit"]) == Decimal("24.75")
    assert Decimal(totals["EUR"]["sales"]) == 12 and totals["EUR"]["gross_profit"] is None
    assert "净利润" in str(result["snapshot"]["limitations"])
    refs = result["snapshot"]["shops"][0]["sources"]
    assert any(r["batch_id"] == source["id"] for r in refs)
    assert (
        logged_in.get(f"/api/shops/{shop}/analytics/sources/{refs[0]['row_id']}").status_code == 200
    )
    withdraw(logged_in, withdraw(logged_in, source, "revoke"), "clear")
    cleared = report(logged_in, shop)
    assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert "CUR" not in str(logged_in.get(root(shop) + "/history").json())


def test_concurrent_reports_and_manual_request_replay(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop, task="report", report_currencies=["EUR"])
    barrier = Barrier(2)

    def worker() -> bool:
        barrier.wait(timeout=10)
        return due(session_factory, shop, row["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(lambda _: worker(), range(2))) == [False, True]
    result = report(logged_in, shop)
    assert result["snapshot"]["totals"][0]["currency"] == "EUR"
    assert result["snapshot"]["totals"][0]["sales"] is None
    payload = {"request_id": str(uuid4()), "version": 1}
    path = root(shop) + f"/{row['id']}/check"
    manual = logged_in.post(path, json=payload)
    assert manual.status_code == 200, manual.text
    assert logged_in.post(path, json=payload).json() == manual.json()
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(OverviewReport)) == 2
        assert session.scalar(select(func.count()).select_from(AgentExecution)) == 0


@pytest.mark.parametrize("database_error", [False, True])
def test_failure_after_report_save_rolls_back_everything_then_recovers(
    logged_in: TestClient, session_factory: sessionmaker[Session], database_error: bool
) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in, shop, ORDER_HEADER + "S,1,001,1,12,USD,2026-10-08 10:00:00,paid,0,0\n", "orders"
    )
    row = create(logged_in, shop, task="report")
    error = (
        OperationalError("synthetic", {}, Exception(1213))
        if database_error
        else RuntimeError("synthetic")
    )
    with patch.object(SchedulesService, "_event", side_effect=error), pytest.raises(type(error)):
        due(session_factory, shop, row["id"])
    with session_factory() as session:
        for model in [OverviewReport, OverviewSource, ScheduleOccurrence]:
            assert session.scalar(select(func.count()).select_from(model)) == 0
        plan = session.get(OperationSchedule, row["id"])
        assert plan and plan.next_run_at == datetime.fromisoformat(row["next_run_at"]).replace(
            tzinfo=None
        )
    assert due(session_factory, shop, row["id"])
    assert report(logged_in, shop)["snapshot"]


@pytest.mark.parametrize("business_error", [False, True])
def test_report_failure_pauses_and_does_not_store_exception_body(
    logged_in: TestClient, session_factory: sessionmaker[Session], business_error: bool
) -> None:
    shop = create_shop(logged_in)
    create(logged_in, shop, task="report")
    error = (
        BusinessError("range_too_large", "private synthetic")
        if business_error
        else RuntimeError("private synthetic")
    )
    with (
        patch.object(OverviewRepository, "add", side_effect=error),
        patch("app.services.scheduler.utc_now", return_value=NOW),
    ):
        tick(session_factory)
    notice = logged_in.get(root(shop) + "/history").json()[0]
    assert notice["task"] == "report" and notice["report_id"] is None
    assert notice["status"] == "blocked" and "private" not in str(notice)
    assert logged_in.get(root(shop)).json()[0]["status"] == "paused"


def test_month_report_recovery_uses_due_period_and_source_identity(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in, shop, ORDER_HEADER + "S,1,001,1,12,USD,2026-10-08 10:00:00,paid,0,0\n", "orders"
    )
    row = create(
        logged_in,
        shop,
        task="report",
        frequency="monthly",
        data_identity="user_import",
        local_time="23:00",
    )
    assert due(session_factory, shop, row["id"], datetime(2026, 11, 2, 10))
    result = report(logged_in, shop)
    assert result["scope"]["start_date"] == "2026-10-01"
    assert result["scope"]["comparison_start"] == "2026-09-01"
    assert "自然月报" in result["snapshot"]["summary"][0]
    assert result["snapshot"]["totals"][0]["sales"] is None
    paused = change(logged_in, row, "pause")
    assert not due(session_factory, shop, row["id"], datetime(2026, 12, 1, 16))
    resumed = change(logged_in, paused, "resume", confirmed=True)
    assert resumed["status"] == "active"


def test_missed_report_period_and_clear_saved_report(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop, task="report", frequency="weekly")
    assert due(session_factory, shop, row["id"], datetime(2026, 10, 14))
    notice = logged_in.get(root(shop) + "/history").json()[0]
    assert notice["status"] == "missed" and notice["report_id"] is None
    assert due(session_factory, shop, row["id"], datetime(2026, 10, 19, 2))
    result = report(logged_in, shop)
    assert "自然周报" in result["snapshot"]["summary"][0]
    response = logged_in.post(f"/api/overview/reports/{result['id']}/clear", json={"confirm": True})
    assert response.status_code == 200, response.text
    assert report(logged_in, shop)["snapshot"] is None


@pytest.mark.parametrize(
    "extra",
    [
        {"weekday": 3},
        {"month_day": 2},
        {"rule_revision_id": 1},
        {"channel": "shopify"},
        {"report_currencies": ["BAD"]},
    ],
)
def test_invalid_report_configuration_rejected(
    logged_in: TestClient, extra: dict[str, Any]
) -> None:
    shop = create_shop(logged_in)
    response = logged_in.post(
        root(shop),
        json={
            "request_id": str(uuid4()),
            "confirmed": True,
            "config": {**CONFIG, "task": "report", **extra},
        },
    )
    assert response.status_code == 422


def test_report_requires_confirmation(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    response = logged_in.post(
        root(shop),
        json={
            "request_id": str(uuid4()),
            "confirmed": False,
            "config": {**CONFIG, "task": "report"},
        },
    )
    assert response.status_code == 409
