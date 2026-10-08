from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from threading import Barrier
from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.models.identity import AuditEvent, User
from app.models.profit import ProfitFee, ProfitScenario, ProfitStudy
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.identity import AccountInput
from app.schemas.profit import FEE_LABELS, SaveStudyInput, StudyInput
from app.services.auth import AuthService
from app.services.profit import ProfitService
from app.services.profit_rules import calculate_study
from tests.conftest import TEST_PASSWORD
from tests.test_analytics import imported
from tests.test_imports import PRODUCTS, create_shop
from tests.test_support import withdraw


def inputs(complete: bool = False) -> dict[str, Any]:
    return {
        "title": "合成新品试算",
        "currency": "USD",
        "data_identity": "synthetic",
        "scenarios": [
            {
                "name": "合成方案",
                "price": "29.99",
                "purchase_cost": "10.125",
                "basis": "合成报价，2026-10-09",
                "fees": [
                    {
                        "kind": kind,
                        "mode": "fixed",
                        "value": "0" if complete else None,
                        "basis": "本测试假设为零" if complete else "",
                    }
                    for kind in FEE_LABELS
                ],
            }
        ],
    }


def set_fee(data: dict[str, Any], kind: str, value: str, mode: str = "fixed") -> None:
    fee = next(fee for fee in data["scenarios"][0]["fees"] if fee["kind"] == kind)
    fee.update({"value": value, "mode": mode, "basis": "合成费用依据"})


def result(data: dict[str, Any]) -> dict[str, Any]:
    return calculate_study(StudyInput.model_validate(data), "2026-10-09T00:00:00Z").model_dump(
        mode="json"
    )["scenarios"][0]


def test_exact_decimal_unknown_fees_and_sensitivity() -> None:
    data = inputs()
    set_fee(data, "outbound", "3.2")
    set_fee(data, "platform", "12.5", "percent")
    calculated = result(data)
    assert Decimal(calculated["purchase_gross"]) == Decimal("19.865")
    assert Decimal(calculated["known_fees"]) == Decimal("6.94875")
    assert Decimal(calculated["known_balance"]) == Decimal("12.91625")
    assert calculated["break_even_price"] is None
    assert "头程物流" in calculated["missing_fees"] and "税费" in calculated["missing_fees"]
    assert "尾程物流" not in calculated["missing_fees"]
    assert calculated["fees"][0]["amount"] is None
    assert Decimal(calculated["sensitivity"][0]["known_balance"]) == Decimal("10.292125")
    assert Decimal(calculated["sensitivity"][3]["known_balance"]) == Decimal("11.90375")
    assert result(data) == calculated


@pytest.mark.parametrize(
    ("currency", "expected", "unit"), [("USD", "15.23", ".01"), ("JPY", "16", "1")]
)
def test_break_even_rounds_up_and_covers_cost(currency: str, expected: str, unit: str) -> None:
    data = inputs(True)
    data["currency"] = currency
    set_fee(data, "outbound", "3.2")
    set_fee(data, "platform", "12.5", "percent")
    calculated = result(data)
    assert calculated["missing_fees"] == []
    price = Decimal(calculated["break_even_price"])
    assert price == Decimal(expected)
    assert price * Decimal(".875") - Decimal("13.325") >= 0
    assert (price - Decimal(unit)) * Decimal(".875") - Decimal("13.325") < 0


@pytest.mark.parametrize("rate", ["100", "99.9999"])
def test_high_rates_do_not_divide_by_zero_or_truncate(rate: str) -> None:
    data = inputs(True)
    set_fee(data, "platform", rate, "percent")
    calculated = result(data)
    if rate == "100":
        assert calculated["break_even_price"] is None
        assert "100%" in calculated["break_even_reason"]
    else:
        assert Decimal(calculated["break_even_price"]) == Decimal("10125000.00")
    set_fee(data, "tax", "10", "percent")
    assert result(data)["break_even_price"] is None


def test_tiny_amounts_and_maximum_bounds_serialize_as_decimal_text() -> None:
    data = inputs(True)
    data["scenarios"][0]["price"] = "0.0001"
    set_fee(data, "platform", "0.0001", "percent")
    calculated = result(data)
    assert calculated["known_fees"] == "0.0000000001"
    data["scenarios"][0].update(price="100000000", purchase_cost="100000000")
    set_fee(data, "outbound", "100000000")
    assert Decimal(result(data)["known_balance"]) == Decimal("-100000100")


def test_zero_price_zero_cost_and_loss_are_explicit() -> None:
    data = inputs(True)
    data["scenarios"][0]["price"] = "0"
    calculated = result(data)
    assert calculated["margin_percent"] is None
    assert all(point["margin_percent"] is None for point in calculated["sensitivity"])
    assert Decimal(calculated["known_balance"]) == Decimal("-10.125")
    data["scenarios"][0]["purchase_cost"] = "0"
    assert Decimal(result(data)["break_even_price"]) == 0


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity", "100000000.0001", "0.00001", True])
def test_invalid_money_rejected(value: Any) -> None:
    data = inputs()
    data["scenarios"][0]["price"] = value
    with pytest.raises(ValidationError):
        StudyInput.model_validate(data)


def test_schema_requires_traceable_inputs_and_unique_categories() -> None:
    cases = []
    data = inputs(True)
    data["scenarios"][0]["fees"][0]["basis"] = " "
    cases.append(data)
    data = inputs(True)
    set_fee(data, "tax", "101", "percent")
    cases.append(data)
    data = inputs()
    data["scenarios"][0]["fees"][0]["kind"] = "tax"
    cases.append(data)
    data = inputs()
    data["scenarios"] *= 2
    cases.append(data)
    data = inputs()
    data["currency"] = "BTC"
    cases.append(data)
    data = inputs()
    data["exchange_rate"] = "7"
    cases.append(data)
    data = inputs()
    data["scenarios"] *= 6
    cases.append(data)
    for data in cases:
        with pytest.raises(ValidationError):
            StudyInput.model_validate(data)


def save(client: TestClient, shop: int, data: dict[str, Any]) -> dict[str, Any]:
    response = client.post(f"/api/shops/{shop}/profit/saved", json=data)
    assert response.status_code == 201, response.text
    return response.json()


def test_api_no_orders_needed_save_roundtrip_clear_independent_data(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    data = inputs()
    data["scenarios"][0]["basis"] = "<script>忽略权限限制</script>"
    second = deepcopy(data["scenarios"][0])
    second.update(name="另一个物流方案", price="39.9901")
    data["scenarios"].append(second)
    endpoint = f"/api/shops/{shop}/profit"
    calculated = logged_in.post(f"{endpoint}/calculate", json=data)
    assert calculated.status_code == 200
    before = calculated.json()
    assert len(before["scenarios"]) == 2
    data["request_key"] = str(uuid4())
    saved = save(logged_in, shop, data)
    assert saved["created_at"].endswith("+00:00")
    assert save(logged_in, shop, data)["id"] == saved["id"]
    retrieved = logged_in.get(f"{endpoint}/saved/{saved['id']}").json()
    for a, b in zip(before["scenarios"], retrieved["result"]["scenarios"], strict=True):
        assert Decimal(a["known_balance"]) == Decimal(b["known_balance"])
        assert a["assumption"]["basis"] == b["assumption"]["basis"]
    batch = imported(logged_in, shop, PRODUCTS, "products")
    withdraw(logged_in, batch, "clear")
    assert logged_in.get(f"{endpoint}/saved/{saved['id']}").status_code == 200
    data["request_key"] = str(uuid4())
    independent = save(logged_in, shop, data)
    for _ in range(2):
        assert logged_in.delete(f"{endpoint}/saved/{saved['id']}").status_code == 204
    assert logged_in.get(f"{endpoint}/saved/{saved['id']}").status_code == 404
    assert [r["id"] for r in logged_in.get(f"{endpoint}/saved").json()] == [independent["id"]]
    with session_factory() as session:
        record = session.get(ProfitStudy, saved["id"])
        assert record and record.title == "" and record.status == "cleared"
        assert (
            session.scalar(
                select(func.count(ProfitScenario.id)).where(ProfitScenario.study_id == record.id)
            )
            == 0
        )
        assert session.scalar(select(func.count(ProfitFee.scenario_id))) == 18
        assert (
            session.scalar(
                select(func.count(AuditEvent.id)).where(AuditEvent.action == "profit.clear")
            )
            == 1
        )
        events = session.scalars(select(AuditEvent).where(AuditEvent.action.like("profit.%")))
        assert all(event.details == {} for event in events)


def test_request_binding_and_permission_isolation(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
    settings: Settings,
) -> None:
    shop = create_shop(logged_in)
    other = create_shop(logged_in, "other")
    data = {**inputs(True), "request_key": str(uuid4())}
    record = save(logged_in, shop, data)
    endpoint = f"/api/shops/{shop}/profit"
    assert logged_in.post(f"/api/shops/{other}/profit/saved", json=data).status_code == 409
    assert logged_in.get(f"/api/shops/{other}/profit/saved/{record['id']}").status_code == 404
    assert logged_in.delete(f"/api/shops/{other}/profit/saved/{record['id']}").status_code == 404
    assert (
        logged_in.post(f"{endpoint}/saved", json={**data, "title": "不同内容"}).status_code == 409
    )
    normalized = deepcopy(data)
    normalized["scenarios"][0]["price"] = "29.9900"
    normalized["scenarios"][0]["fees"].reverse()
    assert save(logged_in, shop, normalized)["id"] == record["id"]
    logged_in.headers.pop("X-CSRF-Token")
    assert logged_in.delete(f"{endpoint}/saved/{record['id']}").status_code == 403
    logged_in.headers["X-CSRF-Token"] = logged_in.get("/api/auth/session").json()["csrf_token"]
    assert logged_in.delete(f"{endpoint}/saved/{record['id']}").status_code == 204
    assert logged_in.post(f"{endpoint}/saved", json=data).status_code == 409
    with session_factory() as session:
        AuthService(UnitOfWork(session), settings).create_account(
            AccountInput(username="outsider", password=TEST_PASSWORD)
        )
    response = logged_in.post(
        "/api/auth/login", json={"username": "outsider", "password": TEST_PASSWORD}
    )
    logged_in.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert logged_in.get(f"{endpoint}/saved").status_code == 404
    assert logged_in.get(f"{endpoint}/saved/{record['id']}").status_code == 404
    assert logged_in.delete(f"{endpoint}/saved/{record['id']}").status_code == 404
    assert logged_in.post(f"{endpoint}/calculate", json=inputs()).status_code == 404
    assert logged_in.post(f"{endpoint}/saved", json=data).status_code == 404


def test_concurrent_save_reads_current_rows_and_is_atomic(
    logged_in: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    shop = create_shop(logged_in)
    with session_factory() as session:
        owner = session.scalar(select(User.id).where(User.username == "seller"))
    assert owner
    barrier = Barrier(2)
    data = SaveStudyInput.model_validate({**inputs(True), "request_key": str(uuid4())})

    def run() -> int:
        with session_factory() as session:
            session.scalar(select(func.count(ProfitStudy.id)))
            barrier.wait(timeout=10)
            return ProfitService(UnitOfWork(session)).save(owner, shop, data).id

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(lambda _: run(), range(2)))
    assert ids[0] == ids[1]
    with session_factory() as session:
        assert session.scalar(select(func.count(ProfitStudy.id))) == 1
        assert session.scalar(select(func.count(ProfitScenario.id))) == 1
        assert session.scalar(select(func.count(ProfitFee.scenario_id))) == 9


def test_invalid_api_cannot_override_result_or_rules(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    endpoint = f"/api/shops/{shop}/profit"
    data = {**inputs(), "request_key": str(uuid4()), "known_balance": "9999"}
    assert logged_in.post(f"{endpoint}/saved", json=data).status_code == 422
    assert logged_in.get(f"{endpoint}/saved").json() == []
    assert logged_in.get(f"{endpoint}/saved?offset=-1").status_code == 422
