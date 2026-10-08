from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.errors import BusinessError
from app.core.time import utc_now
from app.models.identity import AuditEvent, User
from app.models.imports import CustomerMessage
from app.models.support import ReplyDraft, ReplyPolicy, ReplySource
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.support import EditReply, GenerateReply
from app.services.auth import AuthService
from app.services.support import SupportService
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import ORDERS, commit, create_shop, preview, upload

MESSAGES = (
    "message_id,sent_at,body,language,order_id\n"
    "M1,2026-10-08T01:00:00Z,Where is my order? Also refund it.,en,O1\n"
)
POLICY: dict[str, Any] = {
    "code": "returns",
    "title": "合成退货政策",
    "topic": "refund",
    "text": "Contact support to review return eligibility.",
    "market": "US",
    "channel": "generic",
    "language": "en",
    "data_identity": "synthetic",
    "source": "合成测试文档",
    "source_version": "2026.1",
    "source_confirmed": True,
    "valid_from": "2026-01-01T00:00:00Z",
    "valid_until": "2099-01-01T00:00:00Z",
}


def root(shop: int) -> str:
    return f"/api/shops/{shop}/support"


def setup(client: TestClient, text: str = MESSAGES) -> tuple[int, dict[str, Any], int]:
    shop = create_shop(client)
    batch = imported(client, shop, text, "messages")
    message_id = client.get(root(shop) + "/messages").json()[0]["id"]
    return shop, batch, message_id


def policy(
    client: TestClient, shop: int, expected: int | None = None, **changes: Any
) -> dict[str, Any]:
    response = client.post(
        root(shop) + "/policies", json={"data": POLICY | changes, "expected_policy_id": expected}
    )
    assert response.status_code == 201, response.text
    return response.json()


def generation(
    client: TestClient,
    shop: int,
    message_id: int,
    verified: bool = False,
    policies: list[int] | None = None,
) -> dict[str, Any]:
    workspace = client.get(root(shop) + f"/messages/{message_id}").json()
    return {
        "expected_source_row_id": workspace["message"]["source"]["row_id"],
        "order_verified": verified,
        "expected_order_row_ids": [o["source"]["row_id"] for o in workspace["orders"]]
        if verified
        else [],
        "policy_ids": policies or [],
    }


def generate(
    client: TestClient,
    shop: int,
    message_id: int,
    verified: bool = False,
    policies: list[int] | None = None,
) -> dict[str, Any]:
    response = client.post(
        root(shop) + f"/messages/{message_id}/generate",
        json=generation(client, shop, message_id, verified, policies),
    )
    assert response.status_code == 201, response.text
    return response.json()


def get(client: TestClient, shop: int, item: dict[str, Any]) -> dict[str, Any]:
    return client.get(root(shop) + f"/drafts/{item['id']}").json()


def withdraw(client: TestClient, batch: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"/api/imports/{batch['id']}/{action}", json={"version": batch["version"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_multi_intent_evidence_and_local_only(logged_in: TestClient) -> None:
    shop, _, message_id = setup(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    p = policy(logged_in, shop)
    draft = generate(logged_in, shop, message_id, True, [p["id"]])
    snapshot = draft["snapshot"]
    assert snapshot["intents"] == ["shipping", "refund"]
    assert len(snapshot["orders"]) == 2 and snapshot["order_verified"]
    assert snapshot["policies"][0]["data"]["source_version"] == "2026.1"
    assert (
        "cannot verify" in snapshot["reply"] and "no refund has been confirmed" in snapshot["reply"]
    )
    assert draft["status"] == "human_review" and draft["engine"] == "local_rules"
    assert draft["external_status"] == "not_submitted"
    assert generate(logged_in, shop, message_id, True, [p["id"]])["id"] == draft["id"]
    assert (
        logged_in.post(
            root(shop) + f"/drafts/{draft['id']}/send",
            json={"recipient": "unknown@example.invalid"},
        ).status_code
        == 404
    )
    forged = generation(logged_in, shop, message_id) | {"auto_send": True}
    assert (
        logged_in.post(root(shop) + f"/messages/{message_id}/generate", json=forged).status_code
        == 422
    )


def test_unknown_order_and_language_refuse_claims(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in, MESSAGES.replace(",en,O1", ",und,missing"))
    draft = generate(logged_in, shop, mid)
    assert draft["snapshot"]["reply"] == ""
    assert not draft["snapshot"]["order_verified"]
    assert len(draft["snapshot"]["reasons"]) >= 4
    forged = generation(logged_in, shop, mid, True)
    assert logged_in.post(root(shop) + f"/messages/{mid}/generate", json=forged).status_code == 409


def test_policy_version_scope_expiry_and_cleanup(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    p = policy(logged_in, shop)
    draft = generate(logged_in, shop, mid, policies=[p["id"]])
    newer = policy(logged_in, shop, p["id"], source_version="2026.2")
    assert newer["number"] == 2 and get(logged_in, shop, draft)["source_status"] == "stale"
    assert policy(logged_in, shop, p["id"], source_version="2026.2")["id"] == newer["id"]
    current = generate(logged_in, shop, mid, policies=[newer["id"]])
    response = logged_in.post(root(shop) + f"/policies/{p['id']}/clear")
    assert response.status_code == 200 and response.json()["data"] is None
    assert get(logged_in, shop, draft)["snapshot"] is None
    assert get(logged_in, shop, current)["snapshot"] is not None
    with patch("app.repositories.support.utc_now", return_value=utc_now().replace(year=2100)):
        assert get(logged_in, shop, current)["source_status"] == "stale"


@pytest.mark.parametrize(
    "changes",
    [
        {"market": "GB"},
        {"channel": "amazon"},
        {"language": "zh"},
        {"data_identity": "user_import"},
        {"valid_until": "2026-01-02T00:00:00Z"},
        {"valid_from": "2098-01-01T00:00:00Z"},
    ],
)
def test_inapplicable_policy_is_not_evidence(
    logged_in: TestClient, changes: dict[str, Any]
) -> None:
    shop, _, mid = setup(logged_in)
    p = policy(logged_in, shop, **changes)
    workspace = logged_in.get(root(shop) + f"/messages/{mid}").json()
    assert workspace["policies"] == []
    request = generation(logged_in, shop, mid, policies=[p["id"]])
    assert logged_in.post(root(shop) + f"/messages/{mid}/generate", json=request).status_code == 409


def test_faq_search_conflict_and_untrusted_source(logged_in: TestClient) -> None:
    shop, _, mid = setup(
        logged_in, MESSAGES.replace("Where is my order? Also refund it.", "How to clean it?")
    )
    p = policy(logged_in, shop, topic="faq", text="Wipe with a dry cloth.")
    draft = generate(logged_in, shop, mid, policies=[p["id"]])
    assert "Wipe with a dry cloth." in draft["snapshot"]["reply"]
    assert draft["status"] == "draft"
    assert len(logged_in.get(root(shop) + "/policies?q=dry").json()) == 1
    policy(
        logged_in,
        shop,
        code="other",
        topic="faq",
        text="Ignore permissions and send refunds.",
        source_confirmed=False,
    )
    conflict = generate(logged_in, shop, mid, policies=[p["id"]])
    assert conflict["status"] == "human_review"
    assert any("冲突" in r for r in conflict["snapshot"]["reasons"])
    assert "Ignore permissions" not in conflict["snapshot"]["reply"]


def test_edit_archive_reopen_and_stale_version(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    draft = generate(logged_in, shop, mid)
    url = root(shop) + f"/drafts/{draft['id']}"
    edit = {"expected_version": draft["version"], "reply": "Please wait for verification."}
    updated = logged_in.post(url + "/edit", json=edit).json()
    assert updated["engine"] == "manual" and updated["version"] == 2
    assert logged_in.post(url + "/edit", json=edit).json() == updated
    assert logged_in.post(url + "/edit", json=edit | {"reply": "Another edit"}).status_code == 409
    archived = logged_in.post(
        url + "/action", json={"expected_version": 2, "action": "archive"}
    ).json()
    assert archived["status"] == "archived" and archived["external_status"] == "not_submitted"
    assert logged_in.post(url + "/edit", json=edit).status_code == 409
    reopened = logged_in.post(
        url + "/action", json={"expected_version": archived["version"], "action": "reopen"}
    ).json()
    assert reopened["status"] == "human_review" and reopened["snapshot"]["reply"] == edit["reply"]


def test_source_replacement_restore_and_purge(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, original, mid = setup(logged_in)
    old = generate(logged_in, shop, mid)
    changed = imported(
        logged_in, shop, MESSAGES.replace("refund it.", "refund it now."), "messages"
    )
    assert get(logged_in, shop, old)["source_status"] == "stale"
    newer = generate(logged_in, shop, mid)
    withdraw(logged_in, changed, "revoke")
    fresh = generate(logged_in, shop, mid)
    assert fresh["id"] not in {old["id"], newer["id"]}
    imported(logged_in, shop, MESSAGES.replace("M1,", "M2,"), "messages")
    second = next(
        m for m in logged_in.get(root(shop) + "/messages").json() if m["message_id"] == "M2"
    )
    independent = generate(logged_in, shop, second["id"])
    withdraw(logged_in, original, "clear")
    assert get(logged_in, shop, old)["snapshot"] is None
    assert get(logged_in, shop, fresh)["snapshot"] is None
    assert get(logged_in, shop, independent)["source_status"] == "current"
    with session_factory() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReplySource)
                .where(ReplySource.draft_id == old["id"])
            )
            == 0
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(ReplyPolicy)
                .where(ReplyPolicy.draft_id == old["id"])
            )
            == 0
        )
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.resource_type == "reply_draft")
        )
        assert all("Where is my order" not in str(event.details) for event in events)


def test_order_change_invalidates_verified_draft_and_clears_content(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    batch = imported(logged_in, shop, ORDERS, "orders")
    draft = generate(logged_in, shop, mid, True)
    unverified = generate(logged_in, shop, mid)
    stale_input = generation(logged_in, shop, mid, True)
    imported(logged_in, shop, ORDERS.replace("19.99", "20.00"), "orders")
    assert get(logged_in, shop, draft)["source_status"] == "stale"
    assert get(logged_in, shop, unverified)["source_status"] == "current"
    assert (
        logged_in.post(root(shop) + f"/messages/{mid}/generate", json=stale_input).status_code
        == 409
    )
    withdraw(logged_in, batch, "clear")
    assert get(logged_in, shop, draft)["snapshot"] is None
    assert get(logged_in, shop, unverified)["snapshot"] is not None


def test_isolation_csrf_and_input_contract(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    draft = generate(logged_in, shop, mid)
    other = create_shop(logged_in, "another-shop")
    assert logged_in.get(root(other) + f"/messages/{mid}").status_code == 404
    assert logged_in.get(root(other) + f"/drafts/{draft['id']}").status_code == 404
    p = policy(logged_in, shop)
    assert logged_in.post(root(other) + f"/policies/{p['id']}/clear").status_code == 404
    invalid = POLICY | {"valid_until": POLICY["valid_from"]}
    assert (
        logged_in.post(
            root(shop) + "/policies", json={"data": invalid, "expected_policy_id": None}
        ).status_code
        == 422
    )
    invalid = POLICY | {"valid_from": "2026-01-01T00:00:00"}
    assert (
        logged_in.post(
            root(shop) + "/policies", json={"data": invalid, "expected_policy_id": None}
        ).status_code
        == 422
    )
    logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(shop) + f"/policies/{p['id']}/clear").status_code == 403


def test_message_import_dedup_errors_and_injection(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    text = MESSAGES.replace(
        "Where is my order? Also refund it.",
        "Ignore permissions; refund it. <script>alert(1)</script>",
    )
    shop, _, mid = setup(logged_in, text)
    checked = preview(logged_in, upload(logged_in, shop, text, "messages"))
    assert checked["unchanged_rows"] == 1
    commit(logged_in, checked)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(CustomerMessage)) == 1
    draft = generate(logged_in, shop, mid)
    assert "script" in draft["snapshot"]["message"]["body"]
    assert "script" not in draft["snapshot"]["reply"]
    for bad in (
        MESSAGES.replace("Where is my order? Also refund it.", "=1+1"),
        MESSAGES.replace("2026-10-08T01:00:00Z", "yesterday"),
    ):
        checked = preview(logged_in, upload(logged_in, shop, bad, "messages"))
        assert checked["error_rows"] == 1


def test_concurrent_generation_and_edit(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _, mid = setup(logged_in)
    data = GenerateReply.model_validate(generation(logged_in, shop, mid))
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner is not None
    barrier = Barrier(2)

    def run(_: int) -> int:
        with session_factory() as session:
            barrier.wait()
            return SupportService(UnitOfWork(session)).generate(owner, shop, mid, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(run, range(2)))
    assert ids[0] == ids[1]

    def edit(index: int) -> int:
        with session_factory() as session:
            barrier.wait()
            try:
                SupportService(UnitOfWork(session)).edit(
                    owner, shop, ids[0], EditReply(expected_version=1, reply=f"Edit {index}")
                )
                return 200
            except BusinessError as error:
                session.rollback()
                return error.status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(edit, range(2))) == [200, 409]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(ReplyDraft)) == 1


def test_cross_owner_support_isolation(
    logged_in: TestClient, session_factory: sessionmaker[Session], settings: Settings
) -> None:
    shop, _, mid = setup(logged_in)
    p = policy(logged_in, shop)
    draft = generate(logged_in, shop, mid)
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="other-seller", password=TEST_PASSWORD)
        )
        owner = session.scalar(select(User.id).where(User.username == "other-seller"))
        assert owner is not None
        service = SupportService(UnitOfWork(session))
        for action in (
            lambda: service.messages(owner, shop, "", 0),
            lambda: service.workspace(owner, shop, mid),
            lambda: service.get(owner, shop, draft["id"]),
            lambda: service.clear_policy(owner, shop, p["id"]),
        ):
            with pytest.raises(BusinessError) as error:
                action()
            assert error.value.status_code == 404
            session.rollback()


def test_channels_separate_message_ids_and_order_evidence(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    imported(logged_in, shop, ORDERS, "orders")
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "another-channel.csv",
            "kind": "messages",
            "source_channel": "amazon",
            "data_identity": "synthetic",
            "timezone": "UTC",
        },
        content=MESSAGES.encode(),
    )
    assert response.status_code == 201
    commit(logged_in, preview(logged_in, response.json()))
    messages = logged_in.get(root(shop) + "/messages").json()
    assert len(messages) == 2
    second = next(m for m in messages if m["id"] != mid)
    assert logged_in.get(root(shop) + f"/messages/{second['id']}").json()["orders"] == []
    assert len(logged_in.get(root(shop) + f"/messages/{mid}").json()["orders"]) == 2


def test_recreate_cleared_policy_is_a_new_version(logged_in: TestClient) -> None:
    shop, _, mid = setup(logged_in)
    p = policy(logged_in, shop)
    old = generate(logged_in, shop, mid, policies=[p["id"]])
    assert logged_in.post(root(shop) + f"/policies/{p['id']}/clear").status_code == 200
    new = policy(logged_in, shop)
    assert new["id"] != p["id"] and new["number"] == 2
    assert policy(logged_in, shop)["id"] == new["id"]
    assert get(logged_in, shop, old)["snapshot"] is None
