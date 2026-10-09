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

from app.models.identity import User
from app.models.imports import StatementLine
from app.models.settlements import (
    Settlement,
    SettlementReceipt,
    SettlementRevision,
    SettlementSource,
)
from app.repositories.settlements import SettlementRepository
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.settlements import SettlementWrite
from app.services.settlements import SettlementService
from tests.test_analytics import imported
from tests.test_imports import create_shop
from tests.test_statements import SCOPE, file, line, withdraw


def root(shop: int) -> str:
    return f"/api/shops/{shop}/settlements"


def receipt(**changes: Any) -> dict[str, Any]:
    return {
        "payout_ref": "PAY-1",
        "receipt_ref": "BANK-1",
        "amount": "80.1234",
        "currency": "USD",
        "received_at": "2026-10-08T09:30:00.123456+08:00",
        "timezone": "Asia/Shanghai",
        "note": "合成凭据，卖家人工声明",
        **changes,
    }


def draft(**changes: Any) -> dict[str, Any]:
    return {
        "scope": SCOPE,
        "settlement_id": None,
        "version": 0,
        "content": {"statement_id": "STATEMENT-1", "note": "合成周期依据", "receipts": [receipt()]},
        **changes,
    }


def payout(**changes: Any) -> dict[str, str]:
    return line(entry_type="payout", fee_name="", evidence_ref="PAY-1", amount="80.1234", **changes)


def setup(client: TestClient) -> tuple[int, dict[str, Any]]:
    shop = create_shop(client)
    batch = imported(client, shop, file(payout()), "statements")
    return shop, batch


def request(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    r = client.post(root(shop) + "/preview", json=data)
    assert r.status_code == 200, r.text
    return data | {
        "preview_hash": r.json()["preview_hash"],
        "confirm": True,
        "request_id": str(uuid4()),
    }


def write(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    r = client.post(root(shop), json=data)
    assert r.status_code == 200, r.text
    return r.json()


def get(client: TestClient, shop: int, saved: dict[str, Any]) -> dict[str, Any]:
    r = client.get(f"{root(shop)}/{saved['id']}")
    assert r.status_code == 200, r.text
    return r.json()


def control(client: TestClient, shop: int, saved: dict[str, Any], action: str) -> dict[str, Any]:
    r = client.post(
        f"{root(shop)}/{saved['id']}/{action}",
        json={"version": saved["version"], "confirm": True, "request_id": str(uuid4())},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_preview_write_history_numeric_utc_and_current(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _ = setup(logged_in)
    data = request(logged_in, shop, draft())
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Settlement)) == 0
    saved = write(logged_in, shop, data)
    assert saved == write(logged_in, shop, data) == get(logged_in, shop, saved)
    snapshot = saved["snapshot"]
    assert snapshot["comparisons"][0]["difference"] == "0.0000"
    assert snapshot["bank_status"] == "unverified"
    assert snapshot["balance_status"] == snapshot["coverage_status"] == "unknown"
    with session_factory() as session:
        r = session.scalar(select(SettlementReceipt))
        assert r and r.amount == Decimal("80.1234")
        assert r.received_at == datetime(2026, 10, 8, 1, 30, 0, 123456)
    updated_draft = draft(settlement_id=saved["id"], version=1)
    updated_draft["content"]["receipts"][0]["amount"] = "79"
    revised = write(logged_in, shop, request(logged_in, shop, updated_draft))
    assert revised["snapshot"]["comparisons"][0]["difference"] == "1.1234"
    assert len(revised["history"]) == 2
    assert logged_in.get(f"{root(shop)}/{saved['id']}?version=1").json()["snapshot"] == snapshot
    current = logged_in.get(f"{root(shop)}/{saved['id']}/current").json()
    assert (
        current["record"] == revised
        and current["preview"]["snapshot"]["comparisons"] == revised["snapshot"]["comparisons"]
    )
    withdrawn = control(logged_in, shop, revised, "withdraw")
    assert withdrawn["snapshot"] and withdrawn["status"] == "withdrawn"
    # Read withdrawn evidence without reserving identifiers or changing the status.
    assert logged_in.get(f"{root(shop)}/{saved['id']}/current").json()["record"] == withdrawn
    cleared = control(logged_in, shop, withdrawn, "clear")
    assert cleared["snapshot"] is None and not any(h["has_content"] for h in cleared["history"])
    assert write(logged_in, shop, data) == cleared
    assert logged_in.get(f"{root(shop)}/{saved['id']}/current").json() == {
        "record": cleared,
        "preview": None,
    }
    assert logged_in.get(f"{root(shop)}/{saved['id']}?version=999").status_code == 404
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SettlementReceipt)) == 0


@pytest.mark.parametrize(
    "case,status",
    [
        ("matched", "matched"),
        ("difference", "amount_difference"),
        ("no_receipt", "statement_only"),
        ("no_payout", "receipt_only"),
        ("currency", "currency_mismatch"),
        ("duplicate_payout", "ambiguous"),
        ("split_receipt", "ambiguous"),
        ("missing_ref", "missing_reference"),
    ],
)
def test_comparison_never_confirms_bank_or_balance(
    logged_in: TestClient, case: str, status: str
) -> None:
    shop = create_shop(logged_in)
    row = payout()
    data = draft()
    if case == "difference":
        data["content"]["receipts"][0]["amount"] = "1"
    if case == "currency":
        data["content"]["receipts"][0]["currency"] = "CNY"
    if case == "no_receipt":
        data["content"]["receipts"] = []
    if case == "missing_ref":
        row["evidence_ref"] = ""
    if case == "split_receipt":
        data["content"]["receipts"].append(receipt(receipt_ref="BANK-2"))
    if case != "no_payout":
        rows = [row, payout(line_id="2")] if case == "duplicate_payout" else [row]
        imported(logged_in, shop, file(*rows), "statements")
    snapshot = write(logged_in, shop, request(logged_in, shop, data))["snapshot"]
    assert snapshot["comparisons"][0]["status"] == status
    if status not in {"matched", "amount_difference"}:
        assert snapshot["comparisons"][0]["difference"] is None
    assert snapshot["bank_status"] == "unverified" and snapshot["balance_status"] == "unknown"


def test_statement_exact_scope_and_cycle_not_payment_window(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(
        logged_in,
        shop,
        file(
            payout(occurred_at="2026-10-08 09:00:00"),
            line(line_id="2", occurred_at="2026-10-08 00:00:00"),
            line(line_id="3", occurred_at="2026-10-07 00:00:00"),
            payout(statement_id="statement-1", line_id="4"),
        ),
        "statements",
    )
    s = write(logged_in, shop, request(logged_in, shop, draft()))["snapshot"]
    assert len(s["statements"]) == 3 and len(s["outside_cycle_ids"]) == 1
    assert s["comparisons"][0]["status"] == "matched"
    for key, value in [("data_identity", "user_import"), ("channel", "amazon")]:
        r = logged_in.post(root(shop) + "/preview", json=draft(scope=SCOPE | {key: value})).json()
        assert r["snapshot"]["statements"] == []


def test_source_restoration_never_revives_and_clear_erases_historical_sources(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, batch = setup(logged_in)
    data = request(logged_in, shop, draft())
    saved = write(logged_in, shop, data)
    pending = request(logged_in, shop, draft(settlement_id=saved["id"], version=1))
    replacement = imported(logged_in, shop, file(payout() | {"amount": "20"}), "statements")
    withdraw(logged_in, replacement, "revoke")
    assert logged_in.post(root(shop), json=pending).status_code == 409
    assert write(logged_in, shop, data)["status"] == "stale"
    current = logged_in.get(f"{root(shop)}/{saved['id']}/current").json()
    assert (
        current["record"]["status"] == "stale"
        and current["preview"]["snapshot"]["comparisons"][0]["status"] == "matched"
    )
    changed = draft(settlement_id=saved["id"], version=current["record"]["version"])
    changed["content"] = {"statement_id": "EMPTY", "note": "改为另一原账单", "receipts": []}
    write(logged_in, shop, request(logged_in, shop, changed))
    independent = draft(content={"statement_id": "INDEPENDENT", "note": "独立", "receipts": []})
    other = write(logged_in, shop, request(logged_in, shop, independent))
    withdraw(logged_in, batch, "clear")
    cleared = get(logged_in, shop, saved)
    assert cleared["status"] == "cleared" and cleared["snapshot"] is None
    assert all(not h["has_content"] for h in cleared["history"])
    assert get(logged_in, shop, other)["snapshot"]
    with session_factory() as session:
        assert not session.scalar(
            select(SettlementSource.settlement_id).where(
                SettlementSource.settlement_id == saved["id"]
            )
        )
        assert not session.scalar(
            select(SettlementReceipt.id).where(SettlementReceipt.settlement_id == saved["id"])
        )


def test_receipt_and_statement_occupation_release_and_stale(logged_in: TestClient) -> None:
    shop, _ = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    assert logged_in.post(root(shop) + "/preview", json=draft()).status_code == 409
    other = draft()
    other["content"]["statement_id"] = "OTHER"
    other["content"]["receipts"][0]["receipt_ref"] = "ＢＡＮＫ-1"
    assert logged_in.post(root(shop) + "/preview", json=other).status_code == 409
    imported(logged_in, shop, file(payout(line_id="2")), "statements")
    assert get(logged_in, shop, saved)["status"] == "stale"
    assert logged_in.post(root(shop) + "/preview", json=other).status_code == 409
    control(logged_in, shop, get(logged_in, shop, saved), "withdraw")
    assert write(logged_in, shop, request(logged_in, shop, other))["status"] == "active"


@pytest.mark.parametrize("operation", ["create", "update", "withdraw", "clear", "source_clear"])
def test_atomic_audit_rollback(
    logged_in: TestClient, session_factory: sessionmaker[Session], operation: str
) -> None:
    shop, batch = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    d = (
        draft(settlement_id=saved["id"], version=1)
        if operation == "update"
        else draft(content={"statement_id": "OTHER", "note": "独立", "receipts": []})
    )
    data = request(logged_in, shop, d)
    with (
        patch.object(
            UnitOfWork, "record_event", side_effect=RuntimeError("synthetic audit failure")
        ),
        pytest.raises(RuntimeError),
    ):
        if operation in {"create", "update"}:
            logged_in.post(root(shop), json=data)
        elif operation == "source_clear":
            withdraw(logged_in, batch, "clear")
        else:
            control(logged_in, shop, saved, operation)
    assert get(logged_in, shop, saved) == saved
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Settlement)) == 1
        assert session.scalar(select(func.count()).select_from(SettlementReceipt)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "0"},
        {"amount": "1.00001"},
        {"amount": "NaN"},
        {"received_at": "2026-10-08T01:00:00"},
        {"received_at": "2026-10-08T01:00:00Z"},
        {"received_at": "2100-01-01T00:00:00+08:00"},
        {"note": " "},
        {"receipt_ref": "x" * 121},
    ],
)
def test_invalid_manual_receipt(logged_in: TestClient, changes: dict[str, Any]) -> None:
    shop = create_shop(logged_in)
    d = draft()
    d["content"]["receipts"] = [receipt(**changes)]
    assert logged_in.post(root(shop) + "/preview", json=d).status_code == 422


def test_confirmation_tamper_limits_and_scope(logged_in: TestClient) -> None:
    shop, _ = setup(logged_in)
    d = draft()
    data = request(logged_in, shop, draft())
    for changes, status in [
        ({"confirm": False}, 422),
        ({"unexpected": True}, 422),
        ({"preview_hash": "0" * 64}, 409),
    ]:
        assert logged_in.post(root(shop), json=data | changes).status_code == status
    d["content"]["receipts"] *= 2
    assert logged_in.post(root(shop) + "/preview", json=d).status_code == 422
    d["content"]["receipts"] = [receipt(receipt_ref=str(i)) for i in range(51)]
    assert logged_in.post(root(shop) + "/preview", json=d).status_code == 422
    saved = write(logged_in, shop, data)
    assert logged_in.post(root(shop), json=data | {"version": 4}).status_code == 409
    assert logged_in.get(f"{root(shop + 10000)}/{saved['id']}").status_code == 404
    assert (
        logged_in.post(
            root(shop) + "/preview",
            json=draft(settlement_id=saved["id"], version=1, scope=SCOPE | {"channel": "amazon"}),
        ).status_code
        == 409
    )
    assert (
        logged_in.get(
            root(shop), params={"data_identity": "user_import", "channel": "generic"}
        ).json()["items"]
        == []
    )
    token = logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.post(root(shop), json=data).status_code == 403
    logged_in.headers["X-CSRF-Token"] = token


def test_concurrent_replay_is_single_write(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _ = setup(logged_in)
    data = SettlementWrite.model_validate(request(logged_in, shop, draft()))
    with session_factory() as session:
        owner = session.scalar(select(User.id))
        assert owner
    barrier = Barrier(2)

    def save() -> int:
        with session_factory() as session:
            barrier.wait(timeout=10)
            return SettlementService(UnitOfWork(session)).write(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        result = list(executor.map(lambda _: save(), range(2)))
    assert result[0] == result[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SettlementRevision)) == 1


def test_registry_restoration_invalidates_old_preview(logged_in: TestClient) -> None:
    shop, _ = setup(logged_in)
    old = request(logged_in, shop, draft())
    other = write(logged_in, shop, request(logged_in, shop, draft()))
    control(logged_in, shop, other, "withdraw")
    assert logged_in.post(root(shop), json=old).status_code == 409
    assert write(logged_in, shop, request(logged_in, shop, draft()))["id"] != other["id"]


def test_list_revision_size_and_dependency_limits(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    saved = None
    for i in range(22):
        saved = write(
            logged_in,
            shop,
            request(
                logged_in,
                shop,
                draft(content={"statement_id": str(i), "note": "合成", "receipts": []}),
            ),
        )
    params = {"data_identity": "synthetic", "channel": "generic"}
    first = logged_in.get(root(shop), params=params).json()
    assert len(first["items"]) == 20
    assert all(not i["snapshot"] and not i["history"] for i in first["items"])
    second = logged_in.get(root(shop), params=params | {"before": first["next_cursor"]}).json()
    assert len(second["items"]) == 2 and second["next_cursor"] is None
    assert saved
    with patch.object(
        SettlementRepository,
        "history",
        return_value=[(1, "create", datetime(2026, 1, 1), True)] * 100,
    ):
        assert (
            logged_in.post(
                root(shop) + "/preview", json=draft(settlement_id=saved["id"], version=1)
            ).status_code
            == 422
        )
    # The lifecycle remains usable after reaching the content limit.
    assert control(logged_in, shop, saved, "withdraw")["status"] == "withdrawn"


def test_current_refreshes_old_orm_snapshot_and_user_isolation(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, batch = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    with session_factory() as session:
        owner = session.scalar(select(User.id))
        assert owner
        cached = session.get(Settlement, saved["id"])
        assert cached and cached.status == "active"
        withdraw(logged_in, batch, "clear")
        current = SettlementService(UnitOfWork(session)).current(owner, shop, saved["id"])
        assert current.record.status == "cleared" and current.preview is None
    with session_factory() as session:
        other = User(username="other", password_hash="synthetic")
        session.add(other)
        session.commit()
        from app.core.errors import NotFoundError

        with pytest.raises(NotFoundError):
            SettlementService(UnitOfWork(session)).get(other.id, shop, saved["id"])


def test_real_database_source_limit_is_not_partial(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, _ = setup(logged_in)
    with session_factory() as session:
        original = session.scalar(select(StatementLine).where(StatementLine.shop_id == shop))
        assert original
        for i in range(1000):
            session.add(
                StatementLine(
                    **{
                        c.name: getattr(original, c.name)
                        for c in StatementLine.__table__.columns
                        if c.name not in {"id", "line_id"}
                    },
                    line_id=str(i + 2),
                )
            )
        session.commit()
    assert logged_in.post(root(shop) + "/preview", json=draft()).status_code == 422


def test_clear_after_receipt_revision_erases_every_numeric_history(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop, batch = setup(logged_in)
    saved = write(logged_in, shop, request(logged_in, shop, draft()))
    change = draft(settlement_id=saved["id"], version=1)
    change["content"]["receipts"] = [receipt(receipt_ref="BANK-NEW", amount="3")]
    write(logged_in, shop, request(logged_in, shop, change))
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SettlementReceipt)) == 2
    withdraw(logged_in, batch, "clear")
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(SettlementReceipt)) == 0
        assert not session.scalar(
            select(SettlementRevision.id).where(SettlementRevision.snapshot.is_not(None))
        )
