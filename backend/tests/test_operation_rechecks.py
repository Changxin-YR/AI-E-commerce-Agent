from datetime import timedelta
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.core.time import utc_now
from app.models.operations import OperationTask, OperationTaskEvent, OperationTaskSource
from app.services.profit_calculation import utc_text
from tests.test_imports import PRODUCTS, commit, create_shop, preview
from tests.test_operations import ORDERS, change, root, run, tasks
from tests.test_support import MESSAGES, withdraw

KINDS = ["low_inventory", "order_review", "low_margin", "message_review"]


def source(client, shop, content, kind, exported=None, channel="generic", identity="synthetic"):
    params = dict(
        filename=f"recheck-{kind}.csv",
        kind=kind,
        source_channel=channel,
        data_identity=identity,
        timezone="UTC",
    )
    if exported:
        params["exported_at"] = utc_text(exported)
    response = client.post(f"/api/shops/{shop}/imports", params=params, content=content.encode())
    assert response.status_code == 201, response.text
    batch = preview(client, response.json())
    assert not batch["error_rows"], batch
    return commit(client, batch, allow_updates=True)


def stock(stamp, available=2, threshold=5):
    return (
        "sku,available,snapshot_at,safety_threshold\n"
        f"001,{available},{utc_text(stamp)},{threshold}\n"
    )


def message(stamp, status, body="Where is my order?", evidence="Reply-123"):
    lines = MESSAGES.splitlines()
    values = lines[1].replace("Where is my order?", body)
    return (
        f"{lines[0]},reply_status,reply_updated_at,reply_evidence\n"
        f"{values},{status},{utc_text(stamp)},{evidence}\n"
    )


def setup(client, kind):
    base = utc_now() - timedelta(hours=2)
    shop = create_shop(client)
    content, imported_kind = {
        "low_inventory": (stock(base - timedelta(minutes=1)), "inventory"),
        "order_review": (ORDERS, "orders"),
        "low_margin": (PRODUCTS, "products"),
        "message_review": (MESSAGES, "messages"),
    }[kind]
    batch = source(client, shop, content, imported_kind)
    if kind == "low_margin":
        source(client, shop, ORDERS, "orders")
    with patch("app.services.operations.utc_now", return_value=base):
        run(client, shop)
    task = next(item for item in tasks(client, shop) if item["kind"] == kind)
    return shop, change(client, shop, task, "approve"), batch, base


def get(client, shop, task):
    response = client.get(root(shop) + f"/tasks/{task['id']}")
    assert response.status_code == 200, response.text
    return response.json()


def updated(client, shop, kind, base, resolved, **options):
    stamp = base + timedelta(minutes=40 if resolved else 30)
    content, imported_kind = {
        "low_inventory": (stock(stamp, 8 if resolved else 3), "inventory"),
        "order_review": (
            ORDERS.replace("unfulfilled", "fulfilled" if resolved else "partial"),
            "orders",
        ),
        "low_margin": (PRODUCTS.replace("7.125", "3.25" if resolved else "7.5"), "products"),
        "message_review": (message(stamp, "replied" if resolved else "awaiting_reply"), "messages"),
    }[kind]
    return source(client, shop, content, imported_kind, options.pop("exported", stamp), **options)


@pytest.mark.parametrize("kind", KINDS)
def test_four_lifecycles_preserve_manual_state_and_require_new_evidence(logged_in, kind):
    shop, task, original, base = setup(logged_in, kind)
    completed = change(logged_in, shop, task, "complete")
    assert completed["business_state"] == "checked_pending"
    task = change(logged_in, shop, completed, "reopen")
    assert task["business_state"] == "pending_review"
    evidence = dict(
        description="合成外部操作说明",
        evidence_ref="Evidence-001",
        occurred_at=utc_text(base + timedelta(minutes=10)),
        confirmed=True,
    )
    saved = change(logged_in, shop, task, "record_evidence", evidence=evidence)
    assert saved["business_state"] == "evidence_recorded"
    assert saved["review"]["evidence"]["provenance"] == "seller_reported"
    assert change(logged_in, shop, task, "record_evidence", evidence=evidence) == saved
    task = change(logged_in, shop, saved, "wait_source")
    task = change(logged_in, shop, task, "recheck")
    assert task["business_state"] == "awaiting_source"
    assert change(logged_in, shop, task, "recheck") == task
    updated(logged_in, shop, kind, base, False)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert task["business_state"] == "still_anomalous", task
    final_batch = updated(logged_in, shop, kind, base, True)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert task["business_state"] == "resolved" and task["review_current"]
    assert task["status"] == "open" and task["external_status"] == "not_submitted"
    assert any(s["batch_id"] == original["id"] for s in task["snapshot"]["sources"])
    assert any(s["batch_id"] == final_batch["id"] for s in task["review"]["recheck"]["sources"])
    assert task["review"]["evidence"]["recorded_by"] == task["owner_id"]
    assert get(logged_in, shop, task) == task
    assert change(logged_in, shop, task, "recheck") == task
    if kind == "low_margin":
        assert task["review"]["recheck"]["facts"]["商品毛利估算"] == "9.5000"
    # A repeated daily check never overwrites the original task or manual record.
    run(logged_in, shop)
    assert get(logged_in, shop, task)["business_state"] == "resolved"
    final_batch = withdraw(logged_in, final_batch, "revoke")
    assert get(logged_in, shop, task)["business_state"] == "awaiting_source"
    repeated = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert repeated["business_state"] != "resolved"
    withdraw(logged_in, final_batch, "clear")
    cleared = get(logged_in, shop, task)
    assert cleared["business_state"] == "cleared" and cleared["review"] is None
    assert cleared["snapshot"] is None and not cleared["note"]
    assert all(event["review"] is None and event["note"] is None for event in cleared["history"])
    assert (
        logged_in.post(
            root(shop) + f"/tasks/{task['id']}",
            json=dict(action="recheck", version=cleared["version"]),
        ).status_code
        == 409
    )


@pytest.mark.parametrize("kind", KINDS)
def test_original_source_clear_and_resolved_reopen(logged_in, kind):
    shop, task, original, base = setup(logged_in, kind)
    updated(logged_in, shop, kind, base, True)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert task["business_state"] == "resolved"
    # Complete is blocked for stale original sources; a legacy completed record can still reopen.
    with patch("app.services.operations.utc_now", return_value=base + timedelta(days=2)):
        assert get(logged_in, shop, task)["business_state"] == "awaiting_source"
    withdraw(logged_in, original, "clear")
    task = get(logged_in, shop, task)
    assert task["review"] is None and task["snapshot"] is None


@pytest.mark.parametrize("kind", ["order_review", "low_margin", "message_review"])
@pytest.mark.parametrize("time_case", ["missing", "old", "future", "expired"])
def test_new_file_requires_valid_business_time(logged_in, kind, time_case):
    shop, task, _, base = setup(logged_in, kind)
    exported = {
        "missing": None,
        "old": base,
        "future": utc_now() + timedelta(hours=1),
        "expired": base - timedelta(days=2),
    }[time_case]
    updated(logged_in, shop, kind, base, True, exported=exported)
    result = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert result["business_state"] == "awaiting_source", result


@pytest.mark.parametrize("kind", ["low_inventory", "message_review"])
def test_other_channel_cannot_resolve_original(logged_in, kind):
    shop, task, _, base = setup(logged_in, kind)
    updated(logged_in, shop, kind, base, True, channel="amazon")
    result = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert result["business_state"] == "awaiting_source"


@pytest.mark.parametrize("kind", KINDS)
def test_manual_time_after_source_requires_later_evidence(logged_in, kind):
    shop, task, _, base = setup(logged_in, kind)
    updated(logged_in, shop, kind, base, True)
    task = change(
        logged_in,
        shop,
        get(logged_in, shop, task),
        "record_evidence",
        evidence=dict(
            description="较晚的处理",
            evidence_ref="later",
            occurred_at=utc_text(base + timedelta(minutes=50)),
            confirmed=True,
        ),
    )
    assert change(logged_in, shop, task, "recheck")["business_state"] == "awaiting_source"


@pytest.mark.parametrize(
    "case",
    [
        "threshold",
        "sku",
        "body",
        "unknown",
        "cancelled",
        "missing_cost",
        "currency",
        "missing_order",
    ],
)
def test_object_and_accounting_gaps_never_resolve(logged_in, case):
    kind = {
        "threshold": "low_inventory",
        "sku": "order_review",
        "body": "message_review",
        "unknown": "order_review",
        "cancelled": "order_review",
    }.get(case, "low_margin")
    shop, task, _, base = setup(logged_in, kind)
    stamp = base + timedelta(minutes=40)
    content, imported_kind = {
        "threshold": (stock(stamp, 8, 10), "inventory"),
        "sku": (ORDERS.replace("001", "002").replace("unfulfilled", "fulfilled"), "orders"),
        "body": (message(stamp, "replied", body="Different question"), "messages"),
        "unknown": (ORDERS.replace("unfulfilled", "unknown"), "orders"),
        "cancelled": (
            ORDERS.replace("paid", "cancelled").replace("unfulfilled", "fulfilled"),
            "orders",
        ),
        "missing_cost": (PRODUCTS.replace("7.125", ""), "products"),
        "currency": (PRODUCTS.replace("7.125,USD", "3.25,EUR"), "products"),
        "missing_order": (ORDERS.replace("paid", "cancelled"), "orders"),
    }[case]
    source(logged_in, shop, content, imported_kind, stamp)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert task["business_state"] == "awaiting_source", task


def test_manual_evidence_validation_version_conflict_and_stale_completed_reopen(logged_in):
    shop, task, _, base = setup(logged_in, "low_inventory")
    task = change(logged_in, shop, task, "complete")
    data = dict(description="确认", evidence_ref="ref", occurred_at=utc_text(base), confirmed=True)
    endpoint = root(shop) + f"/tasks/{task['id']}"
    for field, value in [
        ("confirmed", False),
        ("confirmed", "true"),
        ("description", " "),
        ("evidence_ref", ""),
        ("occurred_at", "2026-10-10T10:00:00"),
        ("occurred_at", utc_text(utc_now() + timedelta(hours=1))),
    ]:
        assert (
            logged_in.post(
                endpoint,
                json=dict(
                    version=task["version"],
                    action="record_evidence",
                    evidence={**data, field: value},
                ),
            ).status_code
            == 422
        )
    record = change(logged_in, shop, task, "record_evidence", evidence=data)
    assert (
        logged_in.post(
            endpoint,
            json=dict(
                version=task["version"],
                action="record_evidence",
                evidence={**data, "description": "different"},
            ),
        ).status_code
        == 409
    )
    updated(logged_in, shop, "low_inventory", base, True)
    record = change(logged_in, shop, get(logged_in, shop, record), "recheck")
    assert record["business_state"] == "resolved"
    reopened = change(logged_in, shop, record, "reopen")
    assert reopened["review"] is None and reopened["business_state"] == "pending_review"
    assert any(e["review"] and e["review"]["evidence"] for e in reopened["history"])


def test_legacy_snapshot_no_scope_and_migration_guard(
    logged_in, session_factory, settings, monkeypatch
):
    shop, task, _, _ = setup(logged_in, "low_inventory")
    with session_factory() as session:
        record = session.get(OperationTask, task["id"])
        snapshot = dict(record.snapshot)
        snapshot.pop("scope")
        record.snapshot = snapshot
        session.commit()
    monkeypatch.setenv("SOLOOPS_DATABASE_URL", settings.database_url.get_secret_value())
    try:
        command.downgrade(Config("alembic.ini"), "b37e820ca491")
    finally:
        command.upgrade(Config("alembic.ini"), "head")
    command.check(Config("alembic.ini"))
    result = change(logged_in, shop, task, "recheck")
    assert (
        result["business_state"] == "awaiting_source"
        and "旧事项" in result["review"]["recheck"]["reason"]
    )
    try:
        with pytest.raises(RuntimeError, match="事项复核"):
            command.downgrade(Config("alembic.ini"), "b37e820ca491")
    finally:
        # MySQL DDL in newer revisions can commit before this older guard refuses.
        command.upgrade(Config("alembic.ini"), "head")
    with session_factory() as session:
        record = session.get(OperationTask, task["id"])
        record.review = None
        for event in session.scalars(
            select(OperationTaskEvent).where(OperationTaskEvent.task_id == task["id"])
        ):
            event.details = None
        session.commit()
    try:
        with pytest.raises(RuntimeError, match="事项复核"):
            command.downgrade(Config("alembic.ini"), "b37e820ca491")
    finally:
        # MySQL DDL in newer revisions can commit before this older guard refuses.
        command.upgrade(Config("alembic.ini"), "head")


def test_review_dependencies_deduplicate(logged_in, session_factory):
    shop, task, _, base = setup(logged_in, "low_inventory")
    updated(logged_in, shop, "low_inventory", base, True)
    result = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    result = change(logged_in, shop, result, "wait_source")
    change(logged_in, shop, result, "recheck")
    with session_factory() as session:
        assert (
            len(
                session.scalars(
                    select(OperationTaskSource).where(OperationTaskSource.task_id == task["id"])
                ).all()
            )
            == 2
        )


@pytest.mark.parametrize("kind", KINDS)
def test_restoring_previously_resolved_source_requires_explicit_recheck(logged_in, kind):
    shop, task, _, base = setup(logged_in, kind)
    updated(logged_in, shop, kind, base, True)
    task = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert task["business_state"] == "resolved"
    overwrite = updated(logged_in, shop, kind, base + timedelta(minutes=30), False)
    withdraw(logged_in, overwrite, "revoke")
    restored = get(logged_in, shop, task)
    assert restored["business_state"] == "awaiting_source" and not restored["review_current"]
    checked = change(logged_in, shop, restored, "recheck")
    assert checked["business_state"] == "resolved"


def test_rule_change_and_partial_group_block_new_resolution(logged_in):
    from tests.test_business_rules import save as save_rule
    from tests.test_import_groups import create_group, group_data

    shop, task, _, base = setup(logged_in, "order_review")
    updated(logged_in, shop, "order_review", base, True)
    content = ORDERS.replace("O1", "O2").encode()
    create_group(logged_in, shop, group_data([content]))
    waiting = change(logged_in, shop, get(logged_in, shop, task), "recheck")
    assert waiting["business_state"] == "awaiting_source"
    assert "未完成导入组" in waiting["review"]["recheck"]["reason"]
    save_rule(logged_in, shop, max_margin_percent="15")
    assert (
        logged_in.post(
            root(shop) + f"/tasks/{task['id']}",
            json=dict(action="recheck", version=get(logged_in, shop, task)["version"]),
        ).status_code
        == 409
    )


def test_message_reply_import_validation_and_legacy_deduplication(logged_in):
    shop = create_shop(logged_in)
    base = utc_now() - timedelta(hours=1)
    old = source(logged_in, shop, MESSAGES, "messages")
    again = source(logged_in, shop, MESSAGES, "messages")
    assert again["unchanged_rows"] == 1 and again["updated_rows"] == 0
    row = logged_in.get(f"/api/imports/{old['id']}").json()["rows"][0]
    assert "reply_status" not in row["normalized"]
    for status, stamp, evidence in [
        ("replied", utc_text(base), ""),
        ("replied", "", "ref"),
        ("replied", utc_text(utc_now() + timedelta(hours=1)), "ref"),
        ("replied", "2026-10-01T00:00:00Z", "ref"),
        ("invalid", utc_text(base), "ref"),
    ]:
        content = message(base, status, evidence=evidence).replace(utc_text(base), stamp)
        response = logged_in.post(
            f"/api/shops/{shop}/imports",
            params=dict(
                filename="invalid-reply.csv",
                kind="messages",
                data_identity="synthetic",
                timezone="UTC",
            ),
            content=content.encode(),
        )
        assert response.status_code == 201, response.text
        assert preview(logged_in, response.json())["error_rows"] == 1
    valid = source(logged_in, shop, message(base, "replied"), "messages", base)
    run(logged_in, shop)
    assert not tasks(logged_in, shop)
    withdraw(logged_in, valid, "revoke")
    run(logged_in, shop)
    assert len(tasks(logged_in, shop)) == 1


def test_concurrent_review_replay_and_owner_shop_isolation(logged_in, session_factory, settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.repositories.unit_of_work import UnitOfWork
    from app.schemas.identity import AccountInput
    from app.schemas.operations import TaskInput
    from app.services.auth import AuthService
    from app.services.operations import OperationsService
    from tests.conftest import TEST_PASSWORD

    shop, task, _, base = setup(logged_in, "low_inventory")
    updated(logged_in, shop, "low_inventory", base, True)
    task = get(logged_in, shop, task)
    data = TaskInput(version=task["version"], action="recheck")
    barrier = Barrier(2)

    def submit():
        with session_factory() as session:
            barrier.wait(timeout=10)
            return OperationsService(UnitOfWork(session)).change_task(
                task["owner_id"], shop, task["id"], data
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: submit(), range(2)))
    assert outcomes[0] == outcomes[1] and outcomes[0].business_state == "resolved"
    other_shop = create_shop(logged_in, "other-review")
    assert (
        logged_in.post(
            root(other_shop) + f"/tasks/{task['id']}", json=data.model_dump()
        ).status_code
        == 404
    )
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="review-other", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json=dict(username="review-other", password=TEST_PASSWORD)
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert logged_in.get(root(shop) + f"/tasks/{task['id']}").status_code == 404
    assert (
        logged_in.post(root(shop) + f"/tasks/{task['id']}", json=data.model_dump()).status_code
        == 404
    )
