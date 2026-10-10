"""R2 A1-1: business meaning, source identity and recoverable synthetic file import."""

import csv
from io import BytesIO, StringIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.core.errors import BusinessError
from app.models.identity import AuditEvent
from app.models.imports import OrderLine
from app.services.import_parser import parse_file
from tests.test_imports import ORDERS, commit, create_shop, preview, upload


def test_nonstandard_mapping_needs_review_and_keeps_line_amounts(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    text = ORDERS.replace("unit_price", "amount").replace("refund", "order_refund")
    batch = upload(logged_in, shop, text, "orders")
    mapping = batch["mapping"] | {"unit_price": "amount", "refund": "order_refund"}
    batch = preview(logged_in, batch, mapping=mapping)
    assert {item["field"] for item in batch["required_reviews"]} == {"unit_price", "refund"}
    for fields in ([], ["unit_price"], ["other"]):
        response = logged_in.post(
            f"/api/imports/{batch['id']}/commit",
            json={"version": batch["version"], "reviewed_fields": fields},
        )
        assert response.status_code == 409
    with session_factory() as session:
        assert not session.scalars(select(OrderLine)).all()
    # A whole-order refund has no reliable allocation: leave each line unknown.
    batch = preview(logged_in, batch, corrections={"2": {"refund": ""}, "3": {"refund": ""}})
    saved = commit(logged_in, batch)
    readback = logged_in.get(f"/api/imports/{saved['id']}").json()
    assert readback["rows"] == saved["rows"]
    assert readback["total_rows"] == readback["valid_rows"] == readback["new_rows"] == 2
    assert [row["normalized"]["unit_price"] for row in readback["rows"]] == ["19.9900", "4.5000"]
    assert all(row["normalized"]["refund"] is None for row in readback["rows"])
    assert all(row["warnings"] for row in readback["rows"])
    with session_factory() as session:
        orders = session.scalars(select(OrderLine).order_by(OrderLine.line_id)).all()
        assert [str(row.unit_price * row.quantity) for row in orders] == ["39.9800", "4.5000"]
        assert all(row.refund is None for row in orders)
        event = session.scalar(select(AuditEvent).where(AuditEvent.action == "import.committed"))
        assert event is not None
        assert event.details["reviewed_fields"] == ["refund", "unit_price"]
        assert event.details["preview_version"] == batch["version"]


def test_mapping_change_requires_current_preview_and_current_fields(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    batch = preview(logged_in, upload(logged_in, shop, ORDERS, "orders"))
    old_version = batch["version"]
    mapping = batch["mapping"] | {"unit_price": "discount", "discount": "unit_price"}
    changed = preview(logged_in, batch, mapping=mapping)
    assert {item["field"] for item in changed["required_reviews"]} == {"discount", "unit_price"}
    response = logged_in.post(
        f"/api/imports/{batch['id']}/commit",
        json={"version": old_version, "reviewed_fields": ["discount", "unit_price"]},
    )
    assert response.status_code == 409
    assert changed["error_rows"] == 2  # swapped amounts are arithmetically impossible


@pytest.mark.parametrize(
    "option,value", [("source_channel", "amazon"), ("data_identity", "user_import")]
)
def test_same_order_key_cannot_overwrite_another_source(
    logged_in: TestClient, session_factory: sessionmaker[Session], option: str, value: str
) -> None:
    shop = create_shop(logged_in)
    original = commit(logged_in, preview(logged_in, upload(logged_in, shop, ORDERS, "orders")))
    response = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic.csv",
            "kind": "orders",
            "source_channel": "generic",
            "data_identity": "synthetic",
            "timezone": "Asia/Shanghai",
            option: value,
        },
        content=ORDERS.replace("19.99", "25").encode(),
    )
    assert response.status_code == 201
    batch = preview(logged_in, response.json())
    assert batch["valid_rows"] == 0 and batch["error_rows"] == 2
    assert all(row["errors"][0]["field"] == "source_scope" for row in batch["rows"])
    response = logged_in.post(
        f"/api/imports/{batch['id']}/commit",
        json={"version": batch["version"], "allow_updates": True},
    )
    assert response.status_code == 409
    assert logged_in.get(f"/api/imports/{original['id']}").json()["rows"] == original["rows"]
    with session_factory() as session:
        assert [
            str(row.unit_price)
            for row in session.scalars(select(OrderLine).order_by(OrderLine.line_id))
        ] == ["19.9900", "4.5000"]


def test_duplicate_and_batch_errors_are_downloadable_without_source_cells(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    duplicate = ORDERS + ORDERS.splitlines()[1] + "\n"
    batch = preview(logged_in, upload(logged_in, shop, duplicate, "orders"))
    assert batch["duplicate_rows"] == batch["error_rows"] == 2
    assert batch["valid_rows"] == batch["new_rows"] == 1
    batch = preview(logged_in, batch, mapping={"sku": "sku"})
    response = logged_in.get(f"/api/imports/{batch['id']}/errors.csv")
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    records = list(csv.reader(StringIO(response.content.decode("utf-8-sig"))))
    assert any(row[1] == "'mapping" and "成交单价" in row[2] for row in records[1:])
    assert all(row[1].startswith("'") and row[2].startswith("'") for row in records[1:])
    assert "19.99" not in response.text


def test_bom_preserves_non_ascii_and_conversion_errors_are_actionable() -> None:
    headers, rows, _ = parse_file("synthetic.csv", "\ufeffsku,name\n001,合成杯子\n".encode())
    assert headers == ["sku", "name"] and rows[0].values == ["001", "合成杯子"]
    with pytest.raises(BusinessError, match="GB18030/GBK"):
        parse_file("legacy.csv", "sku,name\n001,合成杯子\n".encode("gb18030"))
    workbook = Workbook()
    workbook.create_sheet("second")
    output = BytesIO()
    workbook.save(output)
    workbook.close()
    with pytest.raises(BusinessError, match="另存为单工作表"):
        parse_file("multiple.xlsx", output.getvalue())
