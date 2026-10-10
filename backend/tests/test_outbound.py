import hashlib
import re
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import select

from app.api.dependencies import get_settings
from app.api.routes.outbound import get_provider
from app.core.config import Settings
from app.core.errors import ConflictError
from app.core.time import utc_now
from app.models.identity import User
from app.models.outbound import OutboundApproval, OutboundMessage
from app.models.outbound import TestMailChannel as Channel
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.outbound import SendMail
from app.services.outbound import OutboundService
from app.services.outbound_provider import MailEnvelope, MailResult, ResendMailProvider
from tests.test_analytics import imported
from tests.test_business_rules import save as change_rules
from tests.test_imports import create_shop
from tests.test_operations import ORDERS, run
from tests.test_support import withdraw


class FakeMail:
    def __init__(self) -> None:
        self.sent: list[MailEnvelope] = []
        self.domain = True
        self.result = MailResult("accepted", str(uuid4()), "submitted")
        self.lookup = MailResult("unknown")
        self.before_send: Callable[[], None] | None = None
        self.before_domain: Callable[[], None] | None = None

    def verify_sender(self) -> bool:
        if self.before_domain:
            self.before_domain()
        return self.domain

    def send(self, envelope: MailEnvelope) -> MailResult:
        self.sent.append(envelope)
        if self.before_send:
            self.before_send()
        return self.result

    def reconcile(self, envelope: MailEnvelope, receipt_id: str | None) -> MailResult:
        return self.lookup


def root(shop: int) -> str:
    return f"/api/shops/{shop}/outbound"


@pytest.fixture()
def mailbox(logged_in: TestClient, settings: Settings) -> Iterator[tuple[int, FakeMail, Settings]]:
    shop = create_shop(logged_in)
    owner = logged_in.get("/api/auth/session").json()["user_id"]
    configured = settings.model_copy(
        update={
            "outbound_enabled": True,
            "outbound_api_key": SecretStr("synthetic-not-a-real-key"),
            "outbound_owner_id": owner,
            "outbound_shop_id": shop,
            "outbound_sender": "owner@example.com",
            "outbound_test_recipient": "test@example.net",
            "outbound_domain_id": uuid4(),
        }
    )
    fake = FakeMail()
    logged_in.app.dependency_overrides[get_settings] = lambda: configured  # type: ignore[union-attr]
    logged_in.app.dependency_overrides[get_provider] = lambda: fake  # type: ignore[union-attr]
    yield shop, fake, configured
    logged_in.app.dependency_overrides.clear()  # type: ignore[union-attr]


def verify(client: TestClient, shop: int, fake: FakeMail) -> dict[str, Any]:
    connected = client.post(root(shop) + "/channel/connect", json={"confirmed": True})
    assert connected.status_code == 200, connected.text
    channel = connected.json()
    code = re.search(r"\d{8}", fake.sent[-1].body)
    assert code and code.group() not in connected.text
    response = client.post(
        root(shop) + f"/channel/{channel['id']}/verify", json={"code": code.group()}
    )
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "active"
    return response.json()


def prepare(client: TestClient, shop: int, fake: FakeMail, orders: str = ORDERS) -> dict[str, Any]:
    verify(client, shop, fake)
    imported(client, shop, orders, "orders")
    report = run(client, shop)
    result = client.post(root(shop) + "/messages", json={"run_id": report["id"]})
    assert result.status_code == 200, result.text
    return result.json()


def approve(client: TestClient, mail: dict[str, Any], mode: str = "once") -> dict[str, Any]:
    result = client.post(
        root(mail["shop_id"]) + f"/messages/{mail['id']}/approve",
        json={"version": mail["version"], "confirmed": True, "mode": mode, "valid_hours": 1},
    )
    assert result.status_code == 200, result.text
    return result.json()


def dispatch(client: TestClient, mail: dict[str, Any]) -> httpx.Response:
    return client.post(
        root(mail["shop_id"]) + f"/messages/{mail['id']}/send",
        json={"version": mail["version"], "approval_id": mail["approvals"][0]["id"]},
    )


def test_mailbox_verification_code_is_secret_and_replay_does_not_resend(
    logged_in, mailbox, session_factory
):
    shop, fake, _ = mailbox
    result = logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True})
    channel = result.json()
    code = re.search(r"\d{8}", fake.sent[0].body).group()
    assert code not in result.text
    assert (
        logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True}).json()["id"]
        == channel["id"]
    )
    assert len(fake.sent) == 1
    assert logged_in.post(root(shop) + "/messages", json={"run_id": 1}).status_code == 409
    with session_factory() as session:
        stored = session.get(Channel, channel["id"])
        assert stored.verification_hash == hashlib.sha256(code.encode()).hexdigest()
    verified = logged_in.post(root(shop) + f"/channel/{channel['id']}/verify", json={"code": code})
    assert verified.json()["status"] == "active"


def test_verify_attempts_committed_and_lockout(logged_in, mailbox):
    shop, fake, _ = mailbox
    channel = logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True}).json()
    code = re.search(r"\d{8}", fake.sent[0].body).group()
    wrong = "11111111" if code != "11111111" else "22222222"
    url = root(shop) + f"/channel/{channel['id']}/verify"
    for _ in range(5):
        assert logged_in.post(url, json={"code": wrong}).status_code == 422
    assert logged_in.post(url, json={"code": code}).status_code == 409
    assert logged_in.get(root(shop) + "/channel").json()["status"] == "locked"


def test_preview_approval_send_replay_receipt_and_erasure(logged_in, mailbox):
    shop, fake, _ = mailbox
    mail = prepare(
        logged_in,
        shop,
        fake,
        ORDERS + "O2,1,001,1,8,USD,2026-10-07T02:00:00Z,paid,0,0,fulfilled\n",
    )
    base = root(shop) + f"/messages/{mail['id']}"
    assert mail["risk"] == "R2" and mail["body"] and "synthetic" in mail["body"]
    report = logged_in.get(f"/api/shops/{shop}/operations/runs/{mail['run_id']}").json()
    order_branch = next(
        branch for branch in report["snapshot"]["branches"] if branch["name"] == "订单履约核对"
    )
    assert order_branch["count"] == 2
    assert "订单履约核对：checked；检查记录数 2" in mail["body"]
    assert "异常数" not in mail["body"]
    assert (
        logged_in.post(
            base + "/send", json={"version": mail["version"], "approval_id": 999}
        ).status_code
        == 409
    )
    approved = approve(logged_in, mail)
    sent = dispatch(logged_in, approved).json()
    assert sent["status"] == "accepted" and sent["receipt_id"]
    assert sent["received_at"] is None and sent["approvals"][0]["used_count"] == 1
    assert dispatch(logged_in, approved).json()["status"] == "accepted"
    assert (
        logged_in.post(root(shop) + "/messages", json={"run_id": mail["run_id"]}).json()["id"]
        == mail["id"]
    )
    assert len(fake.sent) == 2  # verification + one summary
    assert fake.sent[-1].body == mail["body"]
    evidence = logged_in.post(
        base + "/receipt", json={"confirmed": True, "evidence": "合成测试邮箱截图索引 synthetic-1"}
    )
    assert evidence.json()["received_at"] and "synthetic-1" in evidence.json()["receipt_evidence"]


def test_edit_invalidates_old_grant_and_requires_full_preview(logged_in, mailbox):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake), "preauthorized")
    base = root(shop) + f"/messages/{mail['id']}"
    edited = logged_in.patch(
        base, json={"version": mail["version"], "subject": "新主题", "body": "完整修改后的测试正文"}
    ).json()
    assert edited["approvals"][0]["status"] == "invalidated"
    assert dispatch(logged_in, mail).status_code == 409
    assert dispatch(logged_in, approve(logged_in, edited)).json()["status"] == "accepted"
    assert fake.sent[-1].subject == "新主题"


@pytest.mark.parametrize("invalidate", ["revoke", "expire", "rules", "data", "channel", "key"])
def test_all_authorization_boundaries_block_sending(
    logged_in, mailbox, session_factory, invalidate
):
    shop, fake, config = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake), "preauthorized")
    if invalidate == "revoke":
        logged_in.post(
            root(shop) + f"/messages/{mail['id']}/approvals/{mail['approvals'][0]['id']}/revoke"
        )
    elif invalidate == "expire":
        with session_factory() as session:
            session.get(OutboundApproval, mail["approvals"][0]["id"]).expires_at = (
                utc_now() - timedelta(seconds=1)
            )
            session.commit()
    elif invalidate == "rules":
        change_rules(logged_in, shop, max_age_hours=25)
    elif invalidate == "data":
        imported(logged_in, shop, ORDERS.replace("O1,", "O2,"), "orders")
    elif invalidate == "channel":
        logged_in.post(root(shop) + f"/channel/{mail['channel_id']}/revoke")
    else:
        config.outbound_api_key = SecretStr("rotated-synthetic-key")
    assert dispatch(logged_in, mail).status_code == 409
    assert len(fake.sent) == 1


def test_unknown_only_reconciles_and_never_reposts(logged_in, mailbox, session_factory):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    fake.result = MailResult("unknown")
    assert dispatch(logged_in, mail).json()["status"] == "unknown"
    base = root(shop) + f"/messages/{mail['id']}"
    assert dispatch(logged_in, mail).json()["status"] == "unknown"
    assert logged_in.post(base + "/reconcile", json={}).json()["status"] == "unknown"
    with session_factory() as session:
        session.get(OutboundMessage, mail["id"]).checked_at = None
        session.commit()
    fake.lookup = MailResult("accepted", str(uuid4()), "delivered")
    checked = logged_in.post(base + "/reconcile", json={}).json()
    assert checked["status"] == "accepted" and checked["provider_event"] == "delivered"
    assert checked["received_at"] is None
    assert len(fake.sent) == 2


def test_rechecks_revocation_after_domain_network(logged_in, mailbox):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    fake.before_domain = lambda: logged_in.post(
        root(shop) + f"/channel/{mail['channel_id']}/revoke"
    )
    assert dispatch(logged_in, mail).status_code == 409
    assert len(fake.sent) == 1


def test_source_clear_during_send_erases_body_but_preserves_external_result(
    logged_in, mailbox, session_factory
):
    shop, fake, _ = mailbox
    verify(logged_in, shop, fake)
    batch = imported(logged_in, shop, ORDERS, "orders")
    report = run(logged_in, shop)
    mail = logged_in.post(root(shop) + "/messages", json={"run_id": report["id"]}).json()
    mail = approve(logged_in, mail)
    fake.before_send = lambda: withdraw(logged_in, batch, "clear")
    result = dispatch(logged_in, mail).json()
    assert result["status"] == "accepted" and result["source_status"] == "cleared"
    assert result["body"] is None and result["subject"] is None
    with session_factory() as session:
        assert session.get(OutboundMessage, mail["id"]).body is None
    assert dispatch(logged_in, mail).json()["status"] == "accepted"
    assert len(fake.sent) == 2


def test_crash_after_claim_persists_unknown_without_retry(logged_in, mailbox, session_factory):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))

    def crash():
        raise RuntimeError("simulated process interruption")

    fake.before_send = crash
    with pytest.raises(RuntimeError):
        dispatch(logged_in, mail)
    with session_factory() as session:
        session.get(OutboundMessage, mail["id"]).dispatch_at = utc_now() - timedelta(minutes=2)
        session.commit()
    assert dispatch(logged_in, mail).json()["status"] == "unknown"
    assert len(fake.sent) == 2


def test_two_old_snapshots_only_one_external_post(logged_in, mailbox, session_factory):
    shop, fake, config = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    barrier = Barrier(2)

    def worker():
        with session_factory() as session:
            owner = session.scalar(select(User.id))  # both RR snapshots precede dispatch
            barrier.wait(timeout=10)
            service = OutboundService(UnitOfWork(session), config, fake)
            try:
                return service.send(
                    owner,
                    shop,
                    mail["id"],
                    SendMail(version=mail["version"], approval_id=mail["approvals"][0]["id"]),
                ).status
            except ConflictError:
                return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: worker(), range(2)))
    assert "accepted" in results
    assert len(fake.sent) == 2


def test_rate_limit_and_isolation_csrf_strict_contract(logged_in, mailbox):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    assert dispatch(logged_in, mail).status_code == 200
    second = logged_in.post(
        root(shop) + "/messages", json={"run_id": run(logged_in, shop)["id"]}
    ).json()
    assert dispatch(logged_in, approve(logged_in, second)).status_code == 409
    other = create_shop(logged_in, "other")
    assert logged_in.get(root(other) + f"/messages/{mail['id']}").status_code == 404
    assert not logged_in.get(root(other) + "/channel").json()["configured"]
    assert (
        logged_in.post(root(shop) + "/channel/connect", json={"confirmed": "true"}).status_code
        == 422
    )
    assert (
        logged_in.post(
            root(shop) + "/messages",
            json={"run_id": mail["run_id"], "recipient": "buyer@example.net"},
        ).status_code
        == 409
    )
    assert (
        logged_in.post(
            root(shop) + f"/messages/{second['id']}/approve",
            json={"version": 1, "confirmed": True, "mode": "preauthorized", "authorization_id": 1},
        ).status_code
        == 422
    )
    token = logged_in.headers.pop("X-CSRF-Token")
    assert (
        logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True}).status_code == 403
    )
    logged_in.headers["X-CSRF-Token"] = token


def test_unconfigured_channel_never_calls_provider(logged_in):
    shop = create_shop(logged_in)
    assert logged_in.get(root(shop) + "/channel").json()["status"] == "not_configured"
    assert (
        logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True}).status_code == 409
    )


def test_dispatch_audit_failure_rolls_back_consent_before_network(
    logged_in, mailbox, session_factory
):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))
    original = UnitOfWork.record_event

    def failing(self, actor, action, *args, **kwargs):
        if action == "outbound.dispatch_claimed":
            raise RuntimeError("simulated audit failure")
        return original(self, actor, action, *args, **kwargs)

    with patch.object(UnitOfWork, "record_event", failing), pytest.raises(RuntimeError):
        dispatch(logged_in, mail)
    assert len(fake.sent) == 1
    with session_factory() as session:
        assert session.get(OutboundMessage, mail["id"]).dispatch_at is None
        assert session.get(OutboundApproval, mail["approvals"][0]["id"]).used_at is None


def test_expiry_during_domain_check_blocks_dispatch(logged_in, mailbox, session_factory):
    shop, fake, _ = mailbox
    mail = approve(logged_in, prepare(logged_in, shop, fake))

    def expire():
        with session_factory() as session:
            session.get(OutboundApproval, mail["approvals"][0]["id"]).expires_at = (
                utc_now() - timedelta(seconds=1)
            )
            session.commit()

    fake.before_domain = expire
    assert dispatch(logged_in, mail).status_code == 409
    assert len(fake.sent) == 1


def test_domain_unverified_and_expired_mailbox_are_blocked(logged_in, mailbox, session_factory):
    shop, fake, _ = mailbox
    fake.domain = False
    result = logged_in.post(root(shop) + "/channel/connect", json={"confirmed": True}).json()
    assert result["status"] == "domain_unverified" and not fake.sent
    with session_factory() as session:
        item = session.get(Channel, result["id"])
        item.created_at = utc_now() - timedelta(minutes=16)
        item.verification_expires_at = utc_now() - timedelta(minutes=1)
        session.commit()
    assert (
        logged_in.post(
            root(shop) + f"/channel/{result['id']}/verify", json={"code": "12345678"}
        ).status_code
        == 409
    )


def test_strict_recipient_binding_and_unknown_never_accepts_forged_receipt(settings):
    config = settings.model_copy(
        update={"outbound_enabled": True, "outbound_api_key": SecretStr("synthetic")}
    )
    receipt, key = str(uuid4()), str(uuid4())
    envelope = MailEnvelope("owner@example.com", "test@example.net", "Subject", "Text", key)
    valid = {
        "id": receipt,
        "from": envelope.sender,
        "to": [envelope.recipient],
        "subject": envelope.subject,
        "text": envelope.body,
        "tags": [{"name": "soloops_dispatch", "value": key}],
    }
    for changed in [
        {"tags": None},
        {"tags": {}},
        {"tags": 12},
        {"tags": []},
        {"text": "Changed"},
        {"cc": ["buyer@example.com"]},
        {"from": "other@example.com"},
    ]:
        provider = ResendMailProvider(
            config,
            httpx.MockTransport(
                lambda _, payload={**valid, **changed}: httpx.Response(200, json=payload)
            ),
        )
        assert provider.reconcile(envelope, receipt).status == "unknown"


def test_http_adapter_fixed_host_one_post_and_exact_readback(settings):
    key, receipt, domain = str(uuid4()), str(uuid4()), uuid4()
    config = settings.model_copy(
        update={
            "outbound_enabled": True,
            "outbound_api_key": SecretStr("synthetic"),
            "outbound_sender": "owner@example.com",
            "outbound_domain_id": domain,
        }
    )
    envelope = MailEnvelope("owner@example.com", "test@example.net", "Subject", "Exact text", key)
    calls = []

    def handler(request):
        calls.append((request.method, str(request.url)))
        assert request.url.host == "api.resend.com" and request.url.scheme == "https"
        if request.url.path.startswith("/domains"):
            return httpx.Response(
                200,
                json={
                    "name": "example.com",
                    "status": "verified",
                    "capabilities": {"sending": "enabled"},
                },
            )
        if request.method == "POST":
            assert request.headers["Idempotency-Key"] == key
            raise httpx.ReadTimeout("response lost")
        if request.url.path == "/emails":
            return httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": receipt,
                            "from": envelope.sender,
                            "to": [envelope.recipient],
                            "subject": envelope.subject,
                        }
                    ]
                },
            )
        return httpx.Response(
            200,
            json={
                "id": receipt,
                "from": envelope.sender,
                "to": [envelope.recipient],
                "subject": envelope.subject,
                "text": envelope.body,
                "tags": [{"name": "soloops_dispatch", "value": key}],
                "last_event": "delivered",
            },
        )

    provider = ResendMailProvider(config, httpx.MockTransport(handler))
    assert provider.verify_sender()
    assert provider.send(envelope).status == "unknown"
    assert provider.reconcile(envelope, None) == MailResult("accepted", receipt, "delivered")
    assert len([x for x in calls if x[0] == "POST"]) == 1
    assert (
        provider.reconcile(
            MailEnvelope(envelope.sender, "buyer@example.com", "Subject", "Exact text", key),
            receipt,
        ).status
        == "unknown"
    )


@pytest.mark.parametrize(
    "status,body,expected",
    [
        (503, {}, "unknown"),
        (429, {}, "unknown"),
        (403, {}, "rejected"),
        (200, {}, "unknown"),
        (302, {}, "unknown"),
        (200, {"id": "invalid"}, "unknown"),
    ],
)
def test_provider_handles_ambiguous_results_without_retry(settings, status, body, expected):
    calls = []
    config = settings.model_copy(
        update={"outbound_enabled": True, "outbound_api_key": SecretStr("synthetic")}
    )

    def handler(request):
        calls.append(request)
        return httpx.Response(status, json=body)

    result = ResendMailProvider(config, httpx.MockTransport(handler)).send(
        MailEnvelope("owner@example.com", "test@example.net", "Subject", "Text", str(uuid4()))
    )
    assert result.status == expected and len(calls) == 1
