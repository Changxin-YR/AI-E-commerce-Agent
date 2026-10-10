import csv
import io
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import func, select

from app.core.time import utc_now
from app.models.identity import AuditEvent, User
from app.models.imports import CustomerMessage, OrderLine
from app.models.support import ReplyManualAction, SupportPolicy
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.support_delivery import RecordManualAction
from app.services.auth import AuthService
from app.services.support_delivery import SupportDeliveryService
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import ORDERS, create_shop
from tests.test_support import generate, get, policy, root, setup, withdraw


def review(client, shop, item, **changes):
    return client.post(
        f"{root(shop)}/drafts/{item['id']}/review",
        json={
            "expected_version": item["version"],
            "target_language": "en",
            "confirmed": True,
            **changes,
        },
    )


def delivery(client, shop, item):
    return client.get(
        f"{root(shop)}/drafts/{item['id']}/delivery", params={"expected_version": item["version"]}
    )


def details(item, **changes):
    return {
        "request_id": str(uuid4()),
        "expected_version": item["version"],
        "occurred_at": "2026-10-09T18:00:00+08:00",
        "method": "原渠道人工回复",
        "evidence_ref": "SYNTHETIC-LOCAL-001",
        "note": "合成操作证据",
        "confirmed": True,
        **changes,
    }


def record(client, shop, item, data):
    return client.post(f"{root(shop)}/drafts/{item['id']}/manual-actions", json=data)


def prepared(client, verified=True):
    shop, batch, mid = setup(client)
    imported(client, shop, ORDERS, "orders")
    selected = policy(client, shop)
    draft = generate(client, shop, mid, verified, [selected["id"]])
    return shop, batch, selected, draft


def test_review_delivery_and_report_preserve_uncertainty(logged_in, settings, session_factory):
    shop, _, selected, draft = prepared(logged_in)
    assert delivery(logged_in, shop, draft).status_code == 409
    assert review(logged_in, shop, draft, confirmed=False).status_code == 422
    response = review(logged_in, shop, draft)
    assert response.status_code == 200, response.text
    reviewed = response.json()
    assert reviewed["version"] == reviewed["reviewed_version"] == draft["version"] + 1
    assert review(logged_in, shop, draft).json() == reviewed
    delivered = delivery(logged_in, shop, reviewed)
    assert delivered.status_code == 200, delivered.text
    result = delivered.json()
    for value in [
        "M1",
        "O1",
        "2026.1",
        selected["data"]["title"],
        "没有可验证",
        "敏感诉求",
        "no refund has been confirmed",
    ]:
        assert value in result["plain_text"]
    assert draft["snapshot"]["message"]["body"] not in result["plain_text"]
    assert result["target_language"] == "en"
    rows = list(csv.reader(io.StringIO(result["csv_text"][1:])))
    assert len(rows) == 2 and all(cell.startswith("'") for cell in rows[1])
    assert rows[1][-1] == "'" + draft["snapshot"]["reply"]
    data = details(reviewed)
    saved = record(logged_in, shop, reviewed, data)
    assert saved.status_code == 201, saved.text
    item = saved.json()
    assert item["occurred_at"].startswith("2026-10-09T10:00:00")
    assert item["provenance"] == "seller_reported" and item["external_status"] == "not_submitted"
    assert record(logged_in, shop, reviewed, data).json() == item
    assert record(logged_in, shop, reviewed, data | {"note": "different"}).status_code == 409
    assert get(logged_in, shop, reviewed) == reviewed
    with session_factory() as session:
        assert session.scalar(select(func.count(ReplyManualAction.id))) == 1
        assert (
            session.scalar(
                select(func.count(AuditEvent.id)).where(
                    AuditEvent.action == "support.reply_reviewed"
                )
            )
            == 1
        )
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.action == "support.manual_action_recorded")
        ).all()
        assert all("SYNTHETIC-LOCAL-001" not in json.dumps(e.details) for e in events)
    script = """
import json, os, sys
from app.core.config import Settings
from app.repositories.database import create_database_engine, create_session_factory
from app.repositories.unit_of_work import UnitOfWork
from app.services.support_delivery import SupportDeliveryService
settings=Settings(_env_file=None,database_url=os.environ['SOLOOPS_TEST_DATABASE_URL'],model_enabled=False,outbound_enabled=False,scheduler_enabled=False)
engine=create_database_engine(settings)
with create_session_factory(engine)() as session:
    result=SupportDeliveryService(UnitOfWork(session)).history(*map(int,sys.argv[1:]),None)
    print(json.dumps([r.model_dump() for r in result]))
engine.dispose()
"""
    reread = subprocess.run(
        [sys.executable, "-c", script, str(owner), str(shop), str(draft["id"])],
        env={**os.environ, "SOLOOPS_TEST_DATABASE_URL": settings.database_url.get_secret_value()},
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(reread.stdout) == [item]
    with pytest.MonkeyPatch.context() as env:
        env.setenv("SOLOOPS_DATABASE_URL", settings.database_url.get_secret_value())
        try:
            with pytest.raises(RuntimeError, match="存在客服审阅"):
                command.downgrade(Config("alembic.ini"), "c84a06e31bd2")
        finally:
            command.upgrade(Config("alembic.ini"), "head")
        command.check(Config("alembic.ini"))


@pytest.mark.parametrize("change", ["edit", "archive", "policy", "expiry", "message", "order"])
def test_review_invalidated_by_content_status_and_evidence(logged_in, session_factory, change):
    shop, _, selected, draft = prepared(logged_in)
    item = review(logged_in, shop, draft).json()
    if change == "edit":
        assert (
            logged_in.post(
                f"{root(shop)}/drafts/{item['id']}/edit",
                json={"expected_version": item["version"], "reply": "Edited reply"},
            ).status_code
            == 200
        )
    elif change == "archive":
        assert (
            logged_in.post(
                f"{root(shop)}/drafts/{item['id']}/action",
                json={"expected_version": item["version"], "action": "archive"},
            ).status_code
            == 200
        )
    elif change == "policy":
        policy(logged_in, shop, selected["id"], source_version="2026.2")
    else:
        with session_factory() as session:
            if change == "expiry":
                row = session.get(SupportPolicy, selected["id"])
                row.valid_until = utc_now() - timedelta(seconds=1)
            elif change == "message":
                row = session.get(CustomerMessage, item["snapshot"]["message"]["id"])
                row.body = "Changed message"
            else:
                row = session.scalar(select(OrderLine).where(OrderLine.shop_id == shop))
                row.fulfillment_status = "partial"
            session.commit()
    assert delivery(logged_in, shop, item).status_code == 409
    assert record(logged_in, shop, item, details(item)).status_code == 409


@pytest.mark.parametrize("purge", ["message", "policy"])
def test_source_clear_erases_manual_evidence_and_review(logged_in, purge):
    shop, batch, selected, draft = prepared(logged_in)
    item = review(logged_in, shop, draft).json()
    data = details(item)
    assert record(logged_in, shop, item, data).status_code == 201
    if purge == "message":
        withdraw(logged_in, withdraw(logged_in, batch, "revoke"), "clear")
    else:
        assert logged_in.post(f"{root(shop)}/policies/{selected['id']}/clear").status_code == 200
    assert get(logged_in, shop, item)["reviewed_version"] is None
    history = logged_in.get(f"{root(shop)}/drafts/{item['id']}/manual-actions").json()
    assert len(history) == 1 and history[0]["details"] is None
    assert record(logged_in, shop, item, data).json()["details"] is None
    assert delivery(logged_in, shop, item).status_code == 409


def test_unknown_identity_does_not_export_order_or_message_content(logged_in):
    shop, _, _, draft = prepared(logged_in, False)
    item = review(logged_in, shop, draft).json()
    result = delivery(logged_in, shop, item).json()
    assert "O1" not in result["plain_text"] and "待关联" not in result["plain_text"]
    assert "客户与订单尚未核验" in result["plain_text"]
    assert "未核验关联" in result["plain_text"]


@pytest.mark.parametrize(
    "changes",
    [
        {"confirmed": False},
        {"occurred_at": "2099-01-01T00:00:00Z"},
        {"occurred_at": "2026-10-01T00:00:00"},
        {"method": " "},
        {"evidence_ref": ""},
    ],
)
def test_manual_evidence_input_gate(logged_in, changes):
    shop, _, mid = setup(logged_in)
    item = review(logged_in, shop, generate(logged_in, shop, mid)).json()
    assert record(logged_in, shop, item, details(item, **changes)).status_code == 422


def test_cross_user_shop_and_concurrent_uuid(logged_in, session_factory, settings):
    shop, _, mid = setup(logged_in)
    item = review(logged_in, shop, generate(logged_in, shop, mid)).json()
    other = create_shop(logged_in, "other")
    assert delivery(logged_in, other, item).status_code == 404
    assert review(logged_in, other, item).status_code == 404
    data = RecordManualAction.model_validate(details(item))
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
    barrier = Barrier(2)

    def run():
        with session_factory() as session:
            barrier.wait(timeout=10)
            return (
                SupportDeliveryService(UnitOfWork(session)).record(owner, shop, item["id"], data).id
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    assert ids[0] == ids[1]
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other", password=TEST_PASSWORD)
        )
    session_info = logged_in.post(
        "/api/auth/login", json={"username": "other", "password": TEST_PASSWORD}
    ).json()
    logged_in.headers["X-CSRF-Token"] = session_info["csrf_token"]
    assert delivery(logged_in, shop, item).status_code == 404
    assert record(logged_in, shop, item, details(item)).status_code == 404
    assert logged_in.get(f"{root(shop)}/drafts/{item['id']}/manual-actions").status_code == 404


def test_blank_language_review_csrf_and_explicit_translation(logged_in):
    from tests.test_support import MESSAGES

    shop, _, mid = setup(logged_in, MESSAGES.replace(",en,O1", ",und,O1"))
    item = generate(logged_in, shop, mid)
    assert review(logged_in, shop, item).status_code == 409
    edited = logged_in.post(
        f"{root(shop)}/drafts/{item['id']}/edit",
        json={"expected_version": item["version"], "reply": "人工翻译：退款尚未确认。"},
    ).json()
    response = logged_in.post(
        f"{root(shop)}/drafts/{item['id']}/review",
        json={"expected_version": edited["version"], "target_language": "zh", "confirmed": True},
        headers={"X-CSRF-Token": "invalid"},
    )
    assert response.status_code == 403
    reviewed = review(logged_in, shop, edited, target_language="zh").json()
    assert delivery(logged_in, shop, reviewed).json()["target_language"] == "zh"
    assert review(logged_in, shop, reviewed, target_language="unknown").status_code == 422


def test_manual_history_pagination_and_scope(logged_in, session_factory):
    shop, _, mid = setup(logged_in)
    item = review(logged_in, shop, generate(logged_in, shop, mid)).json()
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        for number in range(51):
            session.add(
                ReplyManualAction(
                    owner_id=owner,
                    shop_id=shop,
                    draft_id=item["id"],
                    draft_version=item["version"],
                    request_key=str(uuid4()),
                    request_hash="a" * 64,
                    occurred_at=utc_now(),
                    payload={"method": "原平台回复", "evidence_ref": f"SYN-{number}", "note": ""},
                )
            )
        session.commit()
    url = f"{root(shop)}/drafts/{item['id']}/manual-actions"
    first = logged_in.get(url).json()
    second = logged_in.get(url, params={"before": first[-1]["id"]}).json()
    assert len(first) == 50 and len(second) == 1
    assert not {i["id"] for i in first} & {i["id"] for i in second}
    assert logged_in.get(url, params={"before": 0}).status_code == 422
