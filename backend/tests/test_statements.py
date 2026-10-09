import csv
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from decimal import Decimal
from io import StringIO
from threading import Barrier
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.models.expenses import ExpenseRevision
from app.models.identity import User
from app.models.imports import ImportBatch, ImportRow, StatementLine
from app.repositories.expenses import ExpenseRepository
from app.repositories.statements import StatementRepository
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseScope
from app.schemas.imports import CommitInput
from app.services.imports import ImportService
from app.services.statements import StatementService
from tests.test_analytics import imported, setup_data
from tests.test_expenses import body, control, linked, root, write
from tests.test_imports import commit, create_shop, preview, upload

SCOPE = {
    "data_identity": "synthetic",
    "channel": "generic",
    "timezone": "Asia/Shanghai",
    "start_at": "2026-10-07T00:00:00+08:00",
    "end_at": "2026-10-08T00:00:00+08:00",
}


def line(**changes: Any) -> dict[str, str]:
    return {
        "statement_id": "STATEMENT-1",
        "line_id": "1",
        "entry_type": "fee",
        "amount": "12.3456",
        "currency": "USD",
        "occurred_at": "2026-10-07 08:30:00.123456",
        "evidence_ref": "RECEIPT-001",
        "fee_name": "Source packaging charge",
        "settlement_id": "SETTLEMENT-1",
        "order_id": "",
        "note": "Synthetic statement",
        **changes,
    }


def file(*rows: dict[str, str]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=list(line()))
    writer.writeheader()
    writer.writerows(rows or [line()])
    return output.getvalue()


def reconcile(client: TestClient, shop: int, **scope: Any) -> dict[str, Any]:
    response = client.post(f"/api/shops/{shop}/statements/reconcile", json=SCOPE | scope)
    assert response.status_code == 200, response.text
    return response.json()


def withdraw(client: TestClient, batch: dict[str, Any], action: str) -> dict[str, Any]:
    response = client.post(
        f"/api/imports/{batch['id']}/{action}", json={"version": batch["version"]}
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_preview_numeric_utc_source_totals_and_idempotent_commit(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    rows = [
        line(),
        line(line_id="2", entry_type="sale", amount="100.0001", fee_name="", evidence_ref=""),
        line(line_id="3", entry_type="refund", amount="5.0001", fee_name="", evidence_ref=""),
        line(line_id="4", entry_type="payout", amount="80", fee_name="", evidence_ref=""),
        line(line_id="5", currency="CNY", amount="2", evidence_ref="OTHER-CURRENCY"),
    ]
    draft = preview(logged_in, upload(logged_in, shop, file(*rows), "statements"))
    assert draft["suggested_kind"] == "statements" and draft["new_rows"] == 5
    assert draft["coverage_start"] == "2026-10-07T00:30:00.123456Z"
    assert reconcile(logged_in, shop)["statements"] == []
    saved = commit(logged_in, draft)
    assert commit(logged_in, draft) == saved
    write(logged_in, shop, body())
    result = reconcile(logged_in, shop)
    assert len(result["statements"]) == 5
    assert result["comparisons"][1]["status"] == "matched"
    assert result["comparisons"][1]["difference"] == "0.0000"
    totals = {(t["currency"], t["entry_type"]): t["amount"] for t in result["totals"]}
    assert totals == {
        ("USD", "fee"): "12.3456",
        ("USD", "sale"): "100.0001",
        ("USD", "refund"): "5.0001",
        ("USD", "payout"): "80.0000",
        ("CNY", "fee"): "2.0000",
    }
    source = result["statements"][0]["source"]
    original = logged_in.get(f"/api/shops/{shop}/analytics/sources/{source['row_id']}").json()
    assert original["raw"]["amount"] == "12.3456"
    assert "回款到账待核" in "".join(result["checks"])
    again = reconcile(logged_in, shop)
    assert again["comparisons"] == result["comparisons"] and again["totals"] == result["totals"]
    with session_factory() as session:
        row = session.scalar(select(StatementLine).where(StatementLine.line_id == "1"))
        assert row and row.amount == Decimal("12.3456")
        assert row.occurred_at == datetime(2026, 10, 7, 0, 30, 0, 123456)
        assert session.scalar(select(func.count()).select_from(StatementLine)) == 5


@pytest.mark.parametrize(
    "change",
    [
        {"amount": "0"},
        {"amount": "-1"},
        {"amount": "NaN"},
        {"amount": "1.12345"},
        {"amount": "100000000000000"},
        {"amount": "1e3"},
        {"amount": "1,000"},
        {"evidence_ref": " "},
        {"fee_name": ""},
        {"entry_type": "balance"},
        {"entry_type": "sale"},
        {"currency": "ZZZ"},
        {"statement_id": ""},
        {"line_id": "x" * 121},
        {"note": "x" * 501},
        {"occurred_at": "2100-01-01T00:00:00Z"},
        {"occurred_at": "1999-01-01T00:00:00Z"},
        {"occurred_at": "not-a-date"},
        {"note": "=HYPERLINK(secret)"},
    ],
)
def test_invalid_statement_semantics_block_whole_batch(
    logged_in: TestClient, change: dict[str, str]
) -> None:
    shop = create_shop(logged_in)
    draft = preview(logged_in, upload(logged_in, shop, file(line(**change)), "statements"))
    assert draft["error_rows"] == 1
    response = logged_in.post(
        f"/api/imports/{draft['id']}/commit", json={"version": draft["version"]}
    )
    assert response.status_code == 409
    assert reconcile(logged_in, shop)["statements"] == []


def test_all_comparison_states_and_exact_reference_normalization(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    rows = [
        line(evidence_ref=" ＲＥＣＥＩＰＴ－００１ "),
        line(line_id="2", evidence_ref="DIFF", amount="14.6789"),
        line(line_id="3", evidence_ref="FX", currency="CNY"),
        line(line_id="4", evidence_ref="ONLY-BILL"),
        line(line_id="5", evidence_ref="DUP"),
        line(line_id="6", evidence_ref=" dup "),
    ]
    imported(logged_in, shop, file(*rows), "statements")
    for reference in ("receipt-001", "DIFF", "FX", "ONLY-FEE", "DUP"):
        write(logged_in, shop, body(evidence_ref=reference))
    result = reconcile(logged_in, shop)
    assert {c["status"] for c in result["comparisons"]} == {
        "matched",
        "amount_difference",
        "currency_mismatch",
        "statement_only",
        "expense_only",
        "ambiguous",
    }
    difference = next(c for c in result["comparisons"] if c["status"] == "amount_difference")
    assert difference["difference"] == "2.3333"
    for c in result["comparisons"]:
        if c["status"] not in {"matched", "amount_difference"}:
            assert c["difference"] is None
    ambiguous = next(c for c in result["comparisons"] if c["status"] == "ambiguous")
    assert len(ambiguous["statement_ids"]) == 2 and len(ambiguous["expenses"]) == 1


def test_duplicate_lines_block_preview_but_reimport_compares_updates(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    draft = preview(logged_in, upload(logged_in, shop, file(line(), line()), "statements"))
    assert draft["error_rows"] == 2
    first = imported(logged_in, shop, file(), "statements")
    second = preview(logged_in, upload(logged_in, shop, file(), "statements"))
    assert second["unchanged_rows"] == 1
    changed = preview(
        logged_in, upload(logged_in, shop, file(line(amount="13.0001")), "statements")
    )
    assert changed["updated_rows"] == 1
    assert changed["rows"][0]["previous"]["amount"] == "12.3456"
    assert (
        logged_in.post(
            f"/api/imports/{changed['id']}/commit", json={"version": changed["version"]}
        ).status_code
        == 409
    )
    saved = commit(logged_in, changed, True)
    assert reconcile(logged_in, shop)["statements"][0]["amount"] == "13.0001"
    assert (
        logged_in.post(
            f"/api/imports/{second['id']}/commit", json={"version": second["version"]}
        ).status_code
        == 409
    )
    withdraw(logged_in, saved, "revoke")
    restored = reconcile(logged_in, shop)["statements"][0]
    assert restored["amount"] == "12.3456" and restored["source"]["batch_id"] == first["id"]


def test_clear_history_erases_previous_without_touching_independent_fees(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    first = imported(logged_in, shop, file(), "statements")
    second = imported(logged_in, shop, file(line(amount="13")), "statements")
    fee = write(logged_in, shop, body())
    old_ref = logged_in.get(f"/api/imports/{first['id']}").json()["rows"][0]
    assert old_ref["normalized"]["amount"] == "12.3456"
    withdraw(logged_in, first, "clear")
    result = reconcile(logged_in, shop)
    assert result["comparisons"][0]["status"] == "amount_difference"
    assert logged_in.get(f"/api/imports/{second['id']}").json()["rows"][0]["previous"] is None
    current = logged_in.get(f"/api/imports/{second['id']}").json()
    row_id = result["statements"][0]["source"]["row_id"]
    withdraw(logged_in, current, "clear")
    assert reconcile(logged_in, shop)["comparisons"][0]["status"] == "expense_only"
    assert logged_in.get(f"/api/shops/{shop}/analytics/sources/{row_id}").status_code == 404
    assert logged_in.get(f"{root(shop)}/{fee['id']}").json()["snapshot"]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StatementLine)) == 0
        assert session.scalar(select(func.count()).select_from(ImportRow)) == 0


def test_window_scope_isolation_and_current_expense_versions(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    for identity, channel in [
        ("synthetic", "generic"),
        ("user_import", "generic"),
        ("synthetic", "other"),
    ]:
        response = logged_in.post(
            f"/api/shops/{shop}/imports",
            params={
                "filename": "scope.csv",
                "kind": "statements",
                "data_identity": identity,
                "source_channel": channel,
                "timezone": "Asia/Shanghai",
            },
            content=file().encode(),
        )
        commit(logged_in, preview(logged_in, response.json()))
    write(logged_in, shop, body() | {"data_identity": "user_import"})
    fee = write(logged_in, shop, body())
    write(logged_in, shop, body(amount="10") | {"version": fee["version"]}, fee["id"])
    assert reconcile(logged_in, shop)["comparisons"][0]["difference"] == "2.3456"
    assert len(reconcile(logged_in, shop)["statements"]) == 1
    assert (
        reconcile(logged_in, shop, data_identity="user_import")["comparisons"][0]["status"]
        == "matched"
    )
    assert (
        reconcile(logged_in, shop, channel="other")["comparisons"][0]["status"] == "statement_only"
    )
    assert reconcile(logged_in, shop, end_at="2026-10-07T00:30:00.123456Z")["statements"] == []
    assert (
        len(reconcile(logged_in, shop, start_at="2026-10-07T00:30:00.123456Z")["statements"]) == 1
    )
    assert (
        reconcile(logged_in, shop, start_at="2026-10-07T00:30:00.123456Z")["comparisons"][0][
            "status"
        ]
        == "statement_only"
    )
    assert reconcile(logged_in, create_shop(logged_in, "other"))["comparisons"] == []


def test_source_restore_does_not_reactivate_order_fee(logged_in: TestClient) -> None:
    shop, _, _ = setup_data(logged_in)
    fee = write(logged_in, shop, linked(logged_in, shop))
    bill = imported(logged_in, shop, file(), "statements")
    result = reconcile(logged_in, shop)
    assert result["stale_expenses"] == 1 and result["comparisons"][0]["status"] == "statement_only"
    withdraw(logged_in, bill, "revoke")
    assert reconcile(logged_in, shop)["stale_expenses"] == 1
    current = logged_in.get(f"{root(shop)}/{fee['id']}").json()
    control(logged_in, shop, current, "withdraw")
    assert reconcile(logged_in, shop)["withdrawn_expenses"] == 1


@pytest.mark.parametrize("action", ["commit", "revoke", "clear"])
def test_import_audit_failure_rolls_back_statement_projection(
    logged_in: TestClient, action: str
) -> None:
    shop = create_shop(logged_in)
    draft = preview(logged_in, upload(logged_in, shop, file(), "statements"))
    batch = draft if action == "commit" else commit(logged_in, draft)
    with (
        patch.object(UnitOfWork, "record_event", side_effect=RuntimeError("audit unavailable")),
        pytest.raises(RuntimeError),
    ):
        logged_in.post(f"/api/imports/{batch['id']}/{action}", json={"version": batch["version"]})
    assert logged_in.get(f"/api/imports/{batch['id']}").json() == batch
    assert len(reconcile(logged_in, shop)["statements"]) == (0 if action == "commit" else 1)


def test_bounds_csrf_and_foreign_user(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    url = f"/api/shops/{shop}/statements/reconcile"
    for change in (
        {"end_at": SCOPE["start_at"]},
        {"end_at": "2028-01-01T00:00:00Z"},
        {"timezone": "unknown"},
        {"start_at": "2026-10-07T00:00:00"},
    ):
        assert logged_in.post(url, json=SCOPE | change).status_code == 422
    assert logged_in.post(url, json=SCOPE, headers={"X-CSRF-Token": "invalid"}).status_code == 403
    with session_factory() as session:
        session.add(User(username="other", password_hash="unused"))
        session.commit()
        user = session.scalar(select(User).where(User.username == "other"))
        assert user
        from app.core.errors import NotFoundError
        from app.schemas.expenses import ExpenseScope
        from app.services.statements import StatementService

        with pytest.raises(NotFoundError):
            StatementService(UnitOfWork(session)).reconcile(
                user.id, shop, ExpenseScope.model_validate(SCOPE)
            )


@pytest.mark.parametrize("repository", [StatementRepository, ExpenseRepository])
def test_over_limit_is_rejected_without_partial_result(
    logged_in: TestClient, repository: Any
) -> None:
    shop = create_shop(logged_in)
    with patch.object(repository, "period", return_value=[None] * 1001):
        response = logged_in.post(f"/api/shops/{shop}/statements/reconcile", json=SCOPE)
    assert response.status_code == 422 and response.json()["error"]["code"] == "range_too_large"


def test_concurrent_commit_only_applies_once(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    draft = preview(logged_in, upload(logged_in, shop, file(), "statements"))
    with session_factory() as session:
        user = session.scalar(select(User).where(User.username == "seller"))
        assert user
        owner = user.id
    barrier = Barrier(2)

    def run() -> int:
        with session_factory() as session:
            barrier.wait()
            return (
                ImportService(UnitOfWork(session))
                .commit(owner, draft["id"], CommitInput(version=draft["version"]))
                .version
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: run(), range(2)))
    assert results[0] == results[1]
    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(StatementLine)) == 1
        assert (
            session.scalar(select(ImportBatch).where(ImportBatch.id == draft["id"])).status
            == "committed"
        )


def test_template_catalog_and_excel_entry(logged_in: TestClient) -> None:
    from io import BytesIO

    from openpyxl import load_workbook

    catalog = logged_in.get("/api/imports/catalog").json()
    assert len(catalog["statements"]) == 11
    response = logged_in.get("/api/imports/templates/statements?format=xlsx")
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook.active
    assert sheet
    sheet.append(list(line().values()))
    data = BytesIO()
    workbook.save(data)
    workbook.close()
    shop = create_shop(logged_in)
    saved = commit(
        logged_in,
        preview(logged_in, upload(logged_in, shop, data.getvalue(), "statements", "bill.xlsx")),
    )
    assert saved["valid_rows"] == 1


def test_real_database_bound_rejects_1001_rows(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    rows = [line(line_id=str(i), evidence_ref=f"REF-{i}") for i in range(1001)]
    imported(logged_in, shop, file(*rows), "statements")
    response = logged_in.post(f"/api/shops/{shop}/statements/reconcile", json=SCOPE)
    assert response.status_code == 422 and response.json()["error"]["code"] == "range_too_large"


def test_locked_current_read_refreshes_existing_orm_snapshot(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, file(), "statements")
    fee = write(logged_in, shop, body())
    with session_factory() as session:
        original = session.scalar(select(StatementLine))
        original_fee = session.scalar(select(ExpenseRevision))
        user = session.scalar(select(User).where(User.username == "seller"))
        assert original and original_fee and user
        imported(logged_in, shop, file(line(amount="15.0001")), "statements")
        write(logged_in, shop, body(amount="14.0000") | {"version": fee["version"]}, fee["id"])
        assert original.amount == Decimal("12.3456")
        result = StatementService(UnitOfWork(session)).reconcile(
            user.id, shop, ExpenseScope.model_validate(SCOPE)
        )
        assert result.statements[0].amount == Decimal("15.0001")
        assert result.comparisons[0].difference == Decimal("1.0001")
