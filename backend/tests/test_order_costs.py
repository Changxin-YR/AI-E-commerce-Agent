from decimal import Decimal
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select

from app.models.analytics import SavedAnalysis
from app.models.order_costs import OrderCostRevision
from tests.test_analytics import ROWS, calculate, imported, save, setup_data
from tests.test_expenses import body
from tests.test_expenses import write as write_expense
from tests.test_imports import ORDER_HEADER, PRODUCTS, create_shop
from tests.test_statements import file, line, reconcile


def endpoint(shop, row):
    return f"/api/shops/{shop}/analytics/order-costs/{row}"


def order_rows(client, shop):
    return [line["source"]["row_id"] for line in calculate(client, shop)["lines"]]


def payload(client, shop, row, **content):
    response = client.get(endpoint(shop, row))
    assert response.status_code == 200, response.text
    page = response.json()
    return {
        "request_id": str(uuid4()),
        "expected_revision": page["source_revision"],
        "expected_version": page["version"],
        "content": {
            "unit_cost": "3.2500",
            "currency": "USD",
            "evidence_ref": "Synthetic receipt 001",
            "evidence_at": "2026-10-06T08:00:00+08:00",
            "confirmed": True,
            **content,
        },
    }


def record(client, shop, row, **content):
    response = client.post(endpoint(shop, row), json=payload(client, shop, row, **content))
    assert response.status_code == 200, response.text
    return response.json()


def revoke(client, shop, row):
    data = payload(client, shop, row)
    data.pop("content")
    data["action"] = "revoke"
    response = client.post(endpoint(shop, row), json=data)
    assert response.status_code == 200, response.text
    return response.json()


def test_two_order_times_cost_versions_refund_and_stable_old_reports(logged_in):
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    imported(logged_in, shop, ROWS.replace("O1,2", "O2,1"), "orders")
    a, b = order_rows(logged_in, shop)
    original = save(logged_in, shop)
    history_mode = {"cost_mode": "seller_history"}
    assert calculate(logged_in, shop, **history_mode)["summary"]["cost"] is None
    record(logged_in, shop, a)
    record(logged_in, shop, b, unit_cost="4.5000", evidence_ref="Synthetic receipt 002")
    result = calculate(logged_in, shop, **history_mode)
    assert result["calculation_version"] == 2
    assert Decimal(result["summary"]["sales"]) == Decimal("48.9700")
    assert Decimal(result["summary"]["cost"]) == 11
    assert Decimal(result["summary"]["gross_profit"]) == Decimal("37.9700")
    assert result["lines"][1]["refund"] == "10.0000"
    assert "缺退货数量" in result["lines"][1]["gaps"][0]
    proof = result["lines"][0]["historical_cost"]
    assert proof["evidence_at"] == "2026-10-06T00:00:00+00:00"
    assert proof["version"] == 1 and result["lines"][0]["cost_source"] is None
    saved = save(logged_in, shop, **history_mode)
    imported(logged_in, shop, PRODUCTS.replace("7.125", "9"), "products")
    assert calculate(logged_in, shop, **history_mode)["summary"] == result["summary"]
    assert Decimal(calculate(logged_in, shop)["summary"]["cost"]) == 27
    changed = record(logged_in, shop, a, unit_cost="5")
    assert [r["status"] for r in changed["history"]] == ["active", "superseded"]
    assert changed["history"][1]["unit_cost"] == "3.2500"
    old = logged_in.get(f"/api/shops/{shop}/analytics/saved/{saved['id']}").json()
    assert old["status"] == "stale" and old["snapshot"] == saved["snapshot"]
    estimate = logged_in.get(f"/api/shops/{shop}/analytics/saved/{original['id']}").json()
    assert estimate["snapshot"] == original["snapshot"]
    assert Decimal(calculate(logged_in, shop, **history_mode)["summary"]["cost"]) == Decimal("14.5")
    revoke(logged_in, shop, a)
    result = calculate(logged_in, shop, **history_mode)
    assert result["summary"]["cost"] is None and result["ranking_available"] is False
    assert result["summary"]["cost_known_lines"] == 1
    source = logged_in.get(f"/api/shops/{shop}/analytics/sources/{a}").json()
    assert "unit_cost" not in source["normalized"] and source["corrections"] == {}


def test_idempotent_replay_conflicts_and_explicit_reconfirmation(logged_in):
    shop, _, orders = setup_data(logged_in)
    row = order_rows(logged_in, shop)[0]
    data = payload(logged_in, shop, row)
    first = logged_in.post(endpoint(shop, row), json=data)
    assert first.status_code == 200, first.text
    assert logged_in.post(endpoint(shop, row), json=data).json() == first.json()
    changed = {**data, "content": {**data["content"], "unit_cost": "99"}}
    assert logged_in.post(endpoint(shop, row), json=changed).status_code == 409
    stale = {**data, "request_id": str(uuid4())}
    assert logged_in.post(endpoint(shop, row), json=stale).status_code == 409
    data2 = payload(logged_in, shop, row)
    data2["expected_version"] = 0
    assert logged_in.post(endpoint(shop, row), json=data2).status_code == 409
    assert len(logged_in.get(endpoint(shop, row)).json()["history"]) == 1
    revoke(logged_in, shop, row)
    assert record(logged_in, shop, row)["version"] == 3


@pytest.mark.parametrize(
    "content",
    [
        {"unit_cost": "-1"},
        {"unit_cost": "NaN"},
        {"unit_cost": "1.12345"},
        {"unit_cost": "100000000000000"},
        {"currency": "ZZZ"},
        {"evidence_ref": " "},
        {"evidence_at": "2026-10-01T00:00:00"},
        {"evidence_at": "2100-01-01T00:00:00Z"},
        {"confirmed": False},
        {"confirmed": "true"},
    ],
)
def test_invalid_cost_evidence_cannot_be_saved(logged_in, content):
    shop, _, orders = setup_data(logged_in)
    row = order_rows(logged_in, shop)[0]
    response = logged_in.post(endpoint(shop, row), json=payload(logged_in, shop, row, **content))
    assert response.status_code == 422, response.text
    assert logged_in.get(endpoint(shop, row)).json()["history"] == []


def test_currency_missing_discount_zero_cost_and_scope_isolation(logged_in):
    shop, products, orders = setup_data(logged_in)
    a, b = order_rows(logged_in, shop)
    record(logged_in, shop, a, currency="EUR")
    record(logged_in, shop, b, unit_cost="0")
    result = calculate(logged_in, shop, cost_mode="seller_history")
    assert result["summary"]["cost"] is None
    assert "历史成本币种不同" in "".join(result["lines"][0]["gaps"])
    assert Decimal(result["lines"][1]["cost"]) == 0
    assert calculate(logged_in, shop, cost_mode="seller_history", channel="shopify")["lines"] == []
    assert (
        calculate(logged_in, shop, cost_mode="seller_history", data_identity="user_import")["lines"]
        == []
    )
    other = create_shop(logged_in, code="other")
    assert logged_in.get(endpoint(other, a)).status_code == 404
    assert logged_in.post(endpoint(other, a), json=payload(logged_in, shop, a)).status_code == 409
    assert (
        logged_in.get(
            endpoint(shop, calculate(logged_in, shop)["lines"][0]["cost_source"]["row_id"])
        ).status_code
        == 404
    )
    imported(
        logged_in, shop, ORDER_HEADER + "M,1,001,1,10,USD,2026-10-07 09:00:00,paid,,0\n", "orders"
    )
    record(logged_in, shop, order_rows(logged_in, shop)[0])
    result = calculate(logged_in, shop, cost_mode="seller_history")
    item = next(r for r in result["lines"] if r["order_id"] == "M")
    assert item["sales"] is None and item["gross_profit"] is None


def test_source_replacement_rollback_and_purge_never_revive_cost(logged_in, session_factory):
    shop, _, orders = setup_data(logged_in)
    row = order_rows(logged_in, shop)[0]
    record(logged_in, shop, row)
    saved = save(logged_in, shop, cost_mode="seller_history")
    updated = imported(logged_in, shop, ROWS.replace("19.99", "20"), "orders")
    old = logged_in.get(endpoint(shop, row)).json()
    assert old["source_current"] is False and old["history"][0]["status"] == "stale"
    assert (
        calculate(logged_in, shop, cost_mode="seller_history")["summary"]["cost_known_lines"] == 0
    )
    assert (
        logged_in.post(
            f"/api/imports/{updated['id']}/revoke", json={"version": updated["version"]}
        ).status_code
        == 200
    )
    assert logged_in.get(endpoint(shop, row)).json()["source_current"] is True
    assert (
        calculate(logged_in, shop, cost_mode="seller_history")["summary"]["cost_known_lines"] == 0
    )
    record(logged_in, shop, row)
    assert (
        logged_in.post(
            f"/api/imports/{orders['id']}/clear", json={"version": orders["version"]}
        ).status_code
        == 200
    )
    assert logged_in.get(endpoint(shop, row)).status_code == 404
    assert (
        logged_in.get(f"/api/shops/{shop}/analytics/saved/{saved['id']}").json()["snapshot"] is None
    )
    with session_factory() as session:
        records = list(session.scalars(select(OrderCostRevision)))
        assert len(records) == 2
        for cost in records:
            assert cost.status == "cleared" and cost.source_row_id is None
            assert cost.unit_cost is cost.evidence_ref is cost.evidence_at is cost.currency is None


def test_duplicate_fees_are_not_deducted_from_merchandise_profit(logged_in):
    shop, _, orders = setup_data(logged_in)
    for row in order_rows(logged_in, shop):
        record(logged_in, shop, row)
    before = calculate(logged_in, shop, cost_mode="seller_history")
    imported(
        logged_in,
        shop,
        file(line(evidence_ref="DUP"), line(line_id="2", evidence_ref="dup")),
        "statements",
    )
    write_expense(logged_in, shop, body(evidence_ref="DUP"))
    assert reconcile(logged_in, shop)["comparisons"][0]["status"] == "ambiguous"
    after = calculate(logged_in, shop, cost_mode="seller_history")
    assert after["summary"] == before["summary"]
    assert "未扣费用" in "".join(after["warnings"]) and after["fee_gaps"]


def test_old_snapshot_contract_and_migration_protection(
    logged_in, session_factory, settings, monkeypatch
):
    shop, _, orders = setup_data(logged_in)
    saved = save(logged_in, shop)
    with session_factory() as session:
        stored = session.get(SavedAnalysis, saved["id"])
        snapshot = dict(stored.snapshot)
        snapshot.pop("calculation_version")
        snapshot["scope"].pop("cost_mode")
        for item in snapshot["lines"]:
            item.pop("unit_cost")
            item.pop("historical_cost")
        stored.snapshot = snapshot
        session.commit()
    old = logged_in.get(f"/api/shops/{shop}/analytics/saved/{saved['id']}").json()["snapshot"]
    assert old["calculation_version"] == 1 and old["scope"]["cost_mode"] == "current_estimate"
    assert old["summary"] == saved["snapshot"]["summary"]
    monkeypatch.setenv("SOLOOPS_DATABASE_URL", settings.database_url.get_secret_value())
    try:
        command.downgrade(Config("alembic.ini"), "a12c4b907e61")
    finally:
        command.upgrade(Config("alembic.ini"), "head")
    assert calculate(logged_in, shop)["summary"] == old["summary"]
    command.check(Config("alembic.ini"))
    record(logged_in, shop, order_rows(logged_in, shop)[0])
    with pytest.raises(RuntimeError, match="成本凭据历史"):
        command.downgrade(Config("alembic.ini"), "a12c4b907e61")
    assert logged_in.get(endpoint(shop, order_rows(logged_in, shop)[0])).json()["history"]


def test_concurrent_requests_and_other_user_cannot_write(logged_in, session_factory, settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from app.models.identity import User
    from app.repositories.unit_of_work import UnitOfWork
    from app.schemas.identity import AccountInput
    from app.schemas.order_costs import CostWrite
    from app.services.auth import AuthService
    from app.services.order_costs import OrderCostService
    from tests.conftest import TEST_PASSWORD

    shop, _, _ = setup_data(logged_in)
    row = order_rows(logged_in, shop)[0]
    data = payload(logged_in, shop, row)
    barrier = Barrier(2)
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))

    def submit():
        with session_factory() as session:
            session.scalar(select(OrderCostRevision.id).limit(1))
            barrier.wait(timeout=10)
            return OrderCostService(UnitOfWork(session)).write(
                owner, shop, row, CostWrite.model_validate(data)
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: submit(), range(2)))
    assert results[0] == results[1]
    assert len(results[0].history) == 1
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="cost-other", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "cost-other", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert logged_in.get(endpoint(shop, row)).status_code == 404
    assert logged_in.post(endpoint(shop, row), json=data).status_code == 404
