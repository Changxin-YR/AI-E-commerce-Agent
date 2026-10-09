from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import NotFoundError
from app.models.fee_rules import FeeRule, FeeRuleRevision
from app.models.identity import User
from app.repositories.fee_rules import FeeRuleRepository
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseScope
from app.schemas.fee_rules import FeeRuleWrite
from app.services.fee_rules import FeeRuleService, match_key
from app.services.statements import StatementService
from tests.test_analytics import imported
from tests.test_expenses import body
from tests.test_expenses import write as expense_write
from tests.test_imports import create_shop
from tests.test_statements import SCOPE, file, line, reconcile, withdraw


def root(shop: int) -> str:
    return f"/api/shops/{shop}/fee-rules"


def draft(**content: Any) -> dict[str, Any]:
    return {
        "scope": SCOPE,
        "version": 0,
        "rule_id": None,
        "content": {
            "fee_name": line()["fee_name"],
            "category": "packaging",
            "reason": "Synthetic seller definition",
            **content,
        },
    }


def preview(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    response = client.post(root(shop) + "/preview", json=data)
    assert response.status_code == 200, response.text
    return response.json()


def request(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    return data | {
        "preview_hash": preview(client, shop, data)["preview_hash"],
        "request_id": str(uuid4()),
        "confirm": True,
    }


def write(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    response = client.post(root(shop), json=data)
    assert response.status_code == 200, response.text
    return response.json()


def control(client: TestClient, shop: int, rule: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"{root(shop)}/{rule['id']}/{action}",
        json={
            "version": rule["version"],
            "confirm": True,
            "request_id": str(uuid4()),
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_save_revision_history_and_read_only_application(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, file(), "statements")
    expense = expense_write(logged_in, shop, body())
    original = reconcile(logged_in, shop)
    planned = preview(logged_in, shop, draft())
    assert planned["changes"][0]["before"]["status"] == "unmapped"
    assert planned["changes"][0]["after"]["category"] == "packaging"
    assert reconcile(logged_in, shop)["mappings"][0]["status"] == "unmapped"
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    result = reconcile(logged_in, shop)
    assert result["mappings"][0] == {
        "statement_id": original["statements"][0]["id"],
        "status": "mapped",
        "category": "packaging",
        "rule_id": saved["id"],
        "rule_version": 1,
    }
    assert result["statements"] == original["statements"]
    assert result["comparisons"] == original["comparisons"]
    changed = draft(category="platform") | {"rule_id": saved["id"], "version": 1}
    planned = preview(logged_in, shop, changed)
    assert planned["changes"][0]["after"]["status"] == "category_conflict"
    saved = write(logged_in, shop, request(logged_in, shop, changed))
    assert saved["version"] == 2 and len(saved["history"]) == 2
    assert saved["history"][1]["content"]["category"] == "packaging"
    assert logged_in.get(f"/api/shops/{shop}/expenses/{expense['id']}").json() == expense
    assert logged_in.get(f"{root(shop)}/{saved['id']}").json() == saved


def test_exact_name_scope_and_duplicate_prevention(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in,
        shop,
        file(
            line(fee_name="Fee"),
            line(line_id="2", evidence_ref="R2", fee_name="fee"),
            line(line_id="3", evidence_ref="R3", fee_name="Ｆｅｅ"),
        ),
        "statements",
    )
    write(logged_in, shop, request(logged_in, shop, draft(fee_name=" Fee ")))
    assert [m["status"] for m in reconcile(logged_in, shop)["mappings"]] == [
        "mapped",
        "unmapped",
        "unmapped",
    ]
    assert logged_in.post(root(shop) + "/preview", json=draft(fee_name="Fee")).status_code == 409
    write(logged_in, shop, request(logged_in, shop, draft(fee_name="fee")))
    other_scope = draft(fee_name="Fee") | {"scope": SCOPE | {"channel": "amazon"}}
    write(logged_in, shop, request(logged_in, shop, other_scope))
    actual = draft(fee_name="Fee") | {"scope": SCOPE | {"data_identity": "user_import"}}
    write(logged_in, shop, request(logged_in, shop, actual))
    rows = logged_in.get(
        root(shop), params={"data_identity": "synthetic", "channel": "generic"}
    ).json()
    assert len(rows["items"]) == 2


def test_duplicates_and_cross_currency_remain_unresolved(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in,
        shop,
        file(line(), line(line_id="2"), line(line_id="3", evidence_ref="FX", currency="CNY")),
        "statements",
    )
    expense_write(logged_in, shop, body(evidence_ref="FX"))
    write(logged_in, shop, request(logged_in, shop, draft()))
    mappings = reconcile(logged_in, shop)["mappings"]
    assert [m["status"] for m in mappings] == ["ambiguous", "ambiguous", "currency_mismatch"]
    assert all(m["category"] is None for m in mappings)


@pytest.mark.parametrize("mutation", ["expense", "source", "restore", "rule", "rule_restore"])
def test_stale_preview_rejected(logged_in: TestClient, mutation: str) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, file(), "statements")
    data = request(logged_in, shop, draft())
    if mutation == "expense":
        expense_write(logged_in, shop, body())
    elif mutation in {"source", "restore"}:
        batch = imported(logged_in, shop, file(line(amount="15")), "statements")
        if mutation == "restore":
            withdraw(logged_in, batch, "revoke")
    else:
        other = write(logged_in, shop, request(logged_in, shop, draft(fee_name="Other")))
        if mutation == "rule_restore":
            control(logged_in, shop, other, "withdraw")
    response = logged_in.post(root(shop), json=data)
    assert response.status_code == 409


def test_idempotency_binding_and_clear_never_restores(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    data = request(logged_in, shop, draft())
    saved = write(logged_in, shop, data)
    assert write(logged_in, shop, data) == saved
    bad = data | {"content": data["content"] | {"reason": "Different"}}
    assert logged_in.post(root(shop), json=bad).status_code == 409
    saved = control(logged_in, shop, saved, "withdraw")
    assert saved["status"] == "withdrawn"
    assert (
        logged_in.post(
            root(shop) + "/preview",
            json=draft(category="tax")
            | {
                "rule_id": saved["id"],
                "version": saved["version"],
            },
        ).status_code
        == 409
    )
    replacement = write(logged_in, shop, request(logged_in, shop, draft()))
    saved = control(logged_in, shop, saved, "clear")
    assert saved["content"] is None and all(h["content"] is None for h in saved["history"])
    assert write(logged_in, shop, data) == saved
    with session_factory() as session:
        rule = session.get(FeeRule, saved["id"])
        assert rule and rule.match_key is None
        assert all(
            r.content is None
            for r in session.scalars(
                select(FeeRuleRevision).where(FeeRuleRevision.rule_id == rule.id)
            )
        )
    assert logged_in.get(f"{root(shop)}/{replacement['id']}").json()["content"] is not None


def test_source_lifecycle_recomputes_without_saved_conclusions(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = imported(logged_in, shop, file(), "statements")
    rule = write(logged_in, shop, request(logged_in, shop, draft()))
    override = imported(logged_in, shop, file(line(fee_name="Unknown")), "statements")
    assert reconcile(logged_in, shop)["mappings"][0]["status"] == "unmapped"
    withdraw(logged_in, override, "revoke")
    assert reconcile(logged_in, shop)["mappings"][0]["rule_version"] == 1
    withdraw(logged_in, batch, "clear")
    assert reconcile(logged_in, shop)["mappings"] == []
    assert logged_in.get(f"{root(shop)}/{rule['id']}").json() == rule


def test_permissions_and_csrf(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    rule = write(logged_in, shop, request(logged_in, shop, draft()))
    other_shop = create_shop(logged_in, "other-shop")
    assert logged_in.get(f"{root(other_shop)}/{rule['id']}").status_code == 404
    assert (
        logged_in.post(
            root(shop) + "/preview", json=draft(), headers={"X-CSRF-Token": "bad"}
        ).status_code
        == 403
    )
    with session_factory() as session:
        user = User(username="other", password_hash="unused")
        session.add(user)
        session.commit()
        with pytest.raises(NotFoundError):
            FeeRuleService(UnitOfWork(session)).get(user.id, shop, rule["id"])


@pytest.mark.parametrize(
    "change",
    [
        {"fee_name": " "},
        {"fee_name": "x" * 121},
        {"reason": "x" * 501},
        {"category": "invalid"},
        {"pattern": ".*"},
    ],
)
def test_bounded_contract(logged_in: TestClient, change: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    assert logged_in.post(root(shop) + "/preview", json=draft(**change)).status_code == 422


def test_confirmation_hash_and_scope_binding(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    data = request(logged_in, shop, draft())
    assert logged_in.post(root(shop), json=data | {"confirm": False}).status_code == 422
    assert logged_in.post(root(shop), json=data | {"preview_hash": "0" * 64}).status_code == 409
    assert (
        logged_in.post(
            root(shop), json=data | {"content": data["content"] | {"category": "tax"}}
        ).status_code
        == 409
    )
    assert (
        logged_in.post(root(shop), json=data | {"scope": SCOPE | {"channel": "other"}}).status_code
        == 409
    )


def test_audit_failure_rolls_back_creation_and_clear(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    data = request(logged_in, shop, draft())
    with (
        patch.object(
            UnitOfWork, "record_event", side_effect=RuntimeError("synthetic audit failure")
        ),
        pytest.raises(RuntimeError),
    ):
        write(logged_in, shop, data)
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(FeeRule)) == 0
        assert session.scalar(select(func.count()).select_from(FeeRuleRevision)) == 0
    rule = write(logged_in, shop, data)
    with (
        patch.object(
            UnitOfWork, "record_event", side_effect=RuntimeError("synthetic audit failure")
        ),
        pytest.raises(RuntimeError),
    ):
        control(logged_in, shop, rule, "clear")
    assert logged_in.get(f"{root(shop)}/{rule['id']}").json() == rule


def test_concurrent_same_request_saves_once(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    data = FeeRuleWrite.model_validate(request(logged_in, shop, draft()))
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner
    barrier = Barrier(2)

    def run() -> int:
        with session_factory() as session:
            barrier.wait()
            return FeeRuleService(UnitOfWork(session)).write(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(FeeRuleRevision)) == 1


def test_current_read_refreshes_rule_snapshot(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, file(), "statements")
    rule = write(logged_in, shop, request(logged_in, shop, draft()))
    with session_factory() as session:
        old = session.get(FeeRule, rule["id"])
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert old and owner
        updated = draft(category="tax") | {"rule_id": rule["id"], "version": 1}
        write(logged_in, shop, request(logged_in, shop, updated))
        assert old.version == 1
        result = StatementService(UnitOfWork(session)).reconcile(
            owner, shop, ExpenseScope.model_validate(SCOPE)
        )
        assert result.mappings[0].rule_version == 2 and result.mappings[0].category == "tax"


def test_active_rule_limit_and_history_limit(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
        assert owner
        for i in range(200):
            session.add(
                FeeRule(
                    owner_id=owner,
                    shop_id=shop,
                    data_identity="synthetic",
                    channel="generic",
                    match_key=match_key(str(i)),
                    content=draft(fee_name=str(i))["content"],
                )
            )
        session.commit()
    response = logged_in.post(root(shop) + "/preview", json=draft())
    assert response.status_code == 422
    first = logged_in.get(
        root(shop), params={"data_identity": "synthetic", "channel": "generic"}
    ).json()
    assert len(first["items"]) == 20 and first["next_cursor"]
    second = logged_in.get(
        root(shop),
        params={"data_identity": "synthetic", "channel": "generic", "before": first["next_cursor"]},
    ).json()
    assert len(second["items"]) == 20 and second["items"][0]["id"] < first["items"][-1]["id"]
    selected = first["items"][0]
    changed = draft(category="tax") | {"rule_id": selected["id"], "version": 1}
    with patch.object(FeeRuleRepository, "revisions", return_value=[None] * 100):
        assert logged_in.post(root(shop) + "/preview", json=changed).status_code == 422
    assert control(logged_in, shop, selected, "clear")["status"] == "cleared"
