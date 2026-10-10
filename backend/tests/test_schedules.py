from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from threading import Barrier, Event
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.main import create_app
from app.models.agent import AgentExecution
from app.models.schedules import OperationSchedule, ScheduleOccurrence
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.schedules import ScheduleConfig
from app.services.agent_skills import ControlledSkills
from app.services.auth import AuthService
from app.services.schedule_clock import notification_time, occurrence
from app.services.scheduler import tick
from app.services.schedules import SchedulesService
from tests.test_agent import act
from tests.test_agent import root as agent_root
from tests.test_analytics import imported
from tests.test_business_rules import save as save_rule
from tests.test_imports import create_shop
from tests.test_operations import ORDERS, tasks
from tests.test_support import withdraw

NOW = datetime(2026, 10, 9, 1, 1)
CONFIG = {
    "name": "Synthetic daily",
    "timezone": "Asia/Shanghai",
    "local_time": "09:00",
    "currency": "USD",
    "data_identity": "synthetic",
}


def root(shop: int) -> str:
    return f"/api/shops/{shop}/schedules"


def create(client: TestClient, shop: int, **config: Any) -> dict[str, Any]:
    with patch("app.services.schedules.utc_now", return_value=datetime(2026, 10, 7)):
        response = client.post(
            root(shop),
            json={"request_id": str(uuid4()), "confirmed": True, "config": {**CONFIG, **config}},
        )
    assert response.status_code == 200, response.text
    return response.json()


def due(factory: sessionmaker[Session], shop: int, schedule: int, now: datetime = NOW) -> bool:
    with factory() as session:
        row = session.get(OperationSchedule, schedule)
        assert row is not None
        return SchedulesService(UnitOfWork(session)).run_due(row.owner_id, shop, schedule, now)


def change(client: TestClient, row: dict[str, Any], action: str, **extra: Any) -> dict[str, Any]:
    result = client.post(
        root(row["shop_id"]) + f"/{row['id']}",
        json={"version": row["version"], "action": action, **extra},
    )
    assert result.status_code == 200, result.text
    return result.json()


@pytest.mark.parametrize(
    "config,at,future,expected",
    [
        ({}, "2026-10-09T01:00:00", True, "2026-10-10T01:00:00"),
        ({}, "2026-10-09T01:00:00", False, "2026-10-09T01:00:00"),
        ({"frequency": "weekly", "weekday": 0}, "2026-10-09T01:00:00", True, "2026-10-12T01:00:00"),
        (
            {"frequency": "monthly", "month_day": 28},
            "2026-12-29T01:00:00",
            True,
            "2027-01-28T01:00:00",
        ),
        (
            {"timezone": "America/New_York", "local_time": "02:30"},
            "2026-03-08T05:00:00",
            True,
            "2026-03-09T06:30:00",
        ),
        (
            {"timezone": "America/New_York", "local_time": "01:30"},
            "2026-11-01T04:00:00",
            True,
            "2026-11-01T05:30:00",
        ),
        (
            {"timezone": "America/New_York", "local_time": "01:30"},
            "2026-11-01T05:30:00",
            True,
            "2026-11-02T06:30:00",
        ),
    ],
)
def test_calendar(config: dict[str, Any], at: str, future: bool, expected: str) -> None:
    value = occurrence(
        ScheduleConfig.model_validate({**CONFIG, **config}),
        datetime.fromisoformat(at),
        future=future,
    )
    assert value == datetime.fromisoformat(expected)


def test_quiet_hours_cross_midnight_and_dst() -> None:
    config = ScheduleConfig.model_validate({**CONFIG, "quiet_start": 22, "quiet_end": 8})
    assert notification_time(config, datetime(2026, 10, 9, 15, 30)) == datetime(2026, 10, 10)
    assert notification_time(config, NOW) == NOW
    config = config.model_copy(
        update={"timezone": "America/New_York", "quiet_start": 0, "quiet_end": 2}
    )
    assert notification_time(config, datetime(2026, 11, 1, 4)) == datetime(2026, 11, 1, 7)


def test_due_coalesces_persists_requires_fresh_approval_and_readback(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, ORDERS, "orders")
    plan = create(logged_in, shop)
    assert due(session_factory, shop, plan["id"])
    assert not due(session_factory, shop, plan["id"])
    notices = logged_in.get(root(shop) + "/history").json()
    assert len(notices) == 1 and notices[0]["status"] == "waiting_approval"
    notice = notices[0]
    assert notice["coalesced_from"] and notice["scheduled_at"].startswith("2026-10-09T01:")
    assert tasks(logged_in, shop) == []
    run = logged_in.get(agent_root(shop) + f"/{notice['execution_id']}").json()
    assert run["input"]["scope"]["end_at"].startswith("2026-10-09T01:")
    assert run["authorization_id"] is None and run["spent_usd"] == "0.000000"
    assert run["input"]["allow_model"] is False
    run = act(logged_in, act(logged_in, act(logged_in, run, "approve")))
    assert run["status"] == "succeeded" and len(tasks(logged_in, shop)) == 1
    read_path = root(shop) + f"/history/{notice['id']}/read"
    read = logged_in.post(read_path).json()
    assert logged_in.post(read_path).json()["read_at"] == read["read_at"]
    assert logged_in.get(root(shop) + "/history?unread=true").json() == []
    batch = withdraw(logged_in, batch, "revoke")
    withdraw(logged_in, batch, "clear")
    erased = logged_in.get(agent_root(shop) + f"/{notice['execution_id']}").json()
    assert erased["source_status"] == "cleared" and erased["result"] is None
    assert "O1" not in str(logged_in.get(root(shop) + "/history").json())


def test_pause_resume_edit_revoke_and_stale_version(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop)
    paused = change(logged_in, row, "pause")
    assert paused["next_run_at"] is None
    assert change(logged_in, row, "pause") == paused
    assert (
        logged_in.post(
            root(shop) + f"/{row['id']}", json={"action": "resume", "version": paused["version"]}
        ).status_code
        == 409
    )
    row = change(
        logged_in,
        paused,
        "edit",
        config={**paused["config"], "frequency": "weekly"},
        confirmed=True,
    )
    assert row["status"] == "paused" and row["next_run_at"] is None
    resumed = change(logged_in, row, "resume", confirmed=True)
    assert resumed["next_run_at"] and resumed["status"] == "active"
    assert (
        logged_in.post(
            root(shop) + f"/{row['id']}", json={"action": "pause", "version": row["version"]}
        ).status_code
        == 409
    )
    revoked = change(logged_in, resumed, "revoke")
    assert revoked["status"] == "revoked" and revoked["next_run_at"] is None
    assert (
        logged_in.post(
            root(shop) + f"/{row['id']}/check",
            json={"request_id": str(uuid4()), "version": revoked["version"]},
        ).status_code
        == 409
    )


def test_rule_change_blocks_and_pauses_without_execution(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop)
    rule = save_rule(logged_in, shop, max_age_hours=12)
    assert due(session_factory, shop, row["id"])
    notice = logged_in.get(root(shop) + "/history").json()[0]
    assert notice["status"] == "blocked" and notice["execution_id"] is None
    latest = logged_in.get(root(shop)).json()[0]
    assert latest["status"] == "paused"
    assert (
        logged_in.post(
            root(shop) + f"/{row['id']}",
            json={"action": "resume", "version": latest["version"], "confirmed": True},
        ).status_code
        == 409
    )
    config = {**latest["config"], "rule_revision_id": rule["version"], "max_age_hours": 12}
    latest = change(logged_in, latest, "edit", config=config, confirmed=True)
    assert change(logged_in, latest, "resume", confirmed=True)["status"] == "active"


def test_empty_history_quiet_hours_and_missed_cycle(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    plan = create(logged_in, shop, quiet_start=8, quiet_end=12)
    assert due(session_factory, shop, plan["id"])
    with patch("app.services.schedules.utc_now", return_value=NOW):
        assert logged_in.get(root(shop) + "/history?unread=true").json() == []
    notice = logged_in.get(root(shop) + "/history").json()[0]
    assert notice["status"] == "succeeded" and notice["notify_at"].startswith("2026-10-09T04:")
    with patch("app.services.schedules.utc_now", return_value=NOW + timedelta(hours=4)):
        assert len(logged_in.get(root(shop) + "/history?unread=true").json()) == 1
    monthly = create(logged_in, shop, frequency="monthly", month_day=8)
    assert due(session_factory, shop, monthly["id"], NOW + timedelta(days=5))
    missed = logged_in.get(root(shop) + "/history").json()[0]
    assert missed["status"] == "missed" and missed["execution_id"] is None
    assert logged_in.get(root(shop) + "/status").json()["latest_timer"] == missed


def test_concurrent_workers_commit_one_cycle(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop)
    barrier = Barrier(2)

    def worker() -> bool:
        barrier.wait(timeout=10)
        return due(session_factory, shop, row["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert sorted(results) == [False, True]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ScheduleOccurrence)) == 1
        assert session.scalar(select(func.count()).select_from(AgentExecution)) == 1


@pytest.mark.parametrize("database_error", [False, True])
def test_atomic_rollback_then_restart(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
    database_error: bool,
) -> None:
    shop = create_shop(logged_in)
    row = create(logged_in, shop)
    failure = (
        OperationalError("synthetic", {}, Exception(1213))
        if database_error
        else RuntimeError("synthetic")
    )
    with (
        patch.object(ControlledSkills, "call", side_effect=failure),
        pytest.raises(type(failure)),
    ):
        due(session_factory, shop, row["id"])
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ScheduleOccurrence)) == 0
        assert session.scalar(select(func.count()).select_from(AgentExecution)) == 0
    assert due(session_factory, shop, row["id"])


def test_manual_and_create_idempotency(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    body = {"request_id": str(uuid4()), "config": CONFIG, "confirmed": True}
    row = logged_in.post(root(shop), json=body).json()
    assert logged_in.post(root(shop), json=body).json() == row
    assert (
        logged_in.post(
            root(shop), json={**body, "config": {**CONFIG, "name": "changed"}}
        ).status_code
        == 409
    )
    path = root(shop) + f"/{row['id']}/check"
    payload = {"request_id": str(uuid4()), "version": row["version"]}
    one = logged_in.post(path, json=payload)
    assert one.status_code == 200, one.text
    assert logged_in.post(path, json=payload).json() == one.json()
    assert logged_in.get(root(shop)).json()[0]["next_run_at"] == row["next_run_at"]


@pytest.mark.parametrize(
    "values",
    [
        {"timezone": "Mars/Sea"},
        {"frequency": "minute"},
        {"local_time": "24:01"},
        {"month_day": 31},
        {"lookback_days": 366},
        {"quiet_start": 8},
        {"quiet_start": 8, "quiet_end": 8},
        {"allow_model": True},
        {"authorization_id": 1},
    ],
)
def test_invalid_schedule_rejected(logged_in: TestClient, values: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    response = logged_in.post(
        root(shop),
        json={"request_id": str(uuid4()), "confirmed": True, "config": {**CONFIG, **values}},
    )
    assert response.status_code == 422


def test_isolation_csrf_confirmation(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    shop = create_shop(logged_in)
    other_shop = create_shop(logged_in, code="other-shop")
    row = create(logged_in, shop)
    assert (
        logged_in.post(
            root(other_shop) + f"/{row['id']}", json={"action": "pause", "version": 1}
        ).status_code
        == 404
    )
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="another-seller", password="Synthetic-Password-2026!")
        )
        # This account cannot discover a schedule or read its notifications.
    session_data = logged_in.post(
        "/api/auth/login",
        json={"username": "another-seller", "password": "Synthetic-Password-2026!"},
    ).json()
    logged_in.headers["X-CSRF-Token"] = session_data["csrf_token"]
    assert logged_in.get(root(shop)).status_code == 404
    assert logged_in.get(root(shop) + "/history").status_code == 404
    assert logged_in.get(root(shop) + "/status").status_code == 404
    del logged_in.headers["X-CSRF-Token"]
    assert (
        logged_in.post(
            root(shop), json={"request_id": str(uuid4()), "confirmed": True, "config": CONFIG}
        ).status_code
        == 403
    )


def test_worker_tick_uses_bounded_due_batch(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    create(logged_in, shop)
    with patch("app.services.scheduler.utc_now", return_value=NOW):
        assert tick(session_factory) == 1
        assert tick(session_factory) == 0


def test_worker_failure_is_readable_and_pauses(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    create(logged_in, shop)
    with (
        patch("app.services.scheduler.utc_now", return_value=NOW),
        patch.object(
            ControlledSkills, "call", side_effect=RuntimeError("synthetic private failure")
        ),
    ):
        assert tick(session_factory) == 0
    notice = logged_in.get(root(shop) + "/history").json()[0]
    assert notice["status"] == "blocked" and notice["reason"] == "local_check_failed"
    assert "private" not in str(notice)
    assert logged_in.get(root(shop)).json()[0]["status"] == "paused"


def test_lifespan_starts_and_stops_real_worker(logged_in: TestClient, settings: Settings) -> None:
    shop = create_shop(logged_in)
    create(logged_in, shop)
    completed = Event()

    def observed(factory: sessionmaker[Session]) -> int:
        count = tick(factory)
        completed.set()
        return count

    with (
        patch("app.services.scheduler.utc_now", return_value=NOW),
        patch("app.services.scheduler.tick", side_effect=observed),
        TestClient(create_app(settings.model_copy(update={"scheduler_enabled": True}))),
    ):
        assert completed.wait(timeout=10)
    notices = logged_in.get(root(shop) + "/history").json()
    assert len(notices) == 1 and notices[0]["status"] == "succeeded"


def test_runtime_status_is_scoped_and_independent_of_manual_and_notification_filters(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    other = create_shop(logged_in, code="runtime-other")
    path = root(shop) + "/status"
    assert logged_in.get(path).json() == {"worker_enabled": False, "latest_timer": None}
    plans = [create(logged_in, shop), create(logged_in, shop)]
    for plan in plans:
        assert due(session_factory, shop, plan["id"])
    latest = logged_in.get(root(shop) + "/history").json()[0]
    assert latest["schedule_id"] == plans[-1]["id"]
    assert latest["coalesced_from"]
    assert logged_in.get(path).json()["latest_timer"] == latest
    assert logged_in.get(root(other) + "/status").json()["latest_timer"] is None
    # A later manual check, read marker and history cursor must not hide the last timer.
    manual = logged_in.post(
        root(shop) + f"/{plans[-1]['id']}/check",
        json={"request_id": str(uuid4()), "version": plans[-1]["version"]},
    ).json()
    assert manual["trigger"] == "manual" and manual["id"] > latest["id"]
    read = logged_in.post(root(shop) + f"/history/{latest['id']}/read").json()
    logged_in.get(root(shop) + f"/history?unread=true&before={latest['id']}")
    assert logged_in.get(path).json()["latest_timer"] == read
    # Sort by actual saved time, with ID only as tie breaker, not by scheduled time or ID alone.
    with session_factory() as session:
        earlier = session.get(ScheduleOccurrence, latest["id"] - 1)
        assert earlier is not None
        earlier.created_at = NOW + timedelta(seconds=1)
        session.commit()
        earlier_id = earlier.id
    assert logged_in.get(path).json()["latest_timer"]["id"] == earlier_id
