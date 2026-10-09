import runpy
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from tests.test_analytics import calculate, imported, save
from tests.test_imports import PRODUCTS, commit, create_shop, preview
from tests.test_inventory import csv
from tests.test_operations import ORDERS, root, run, tasks
from tests.test_support import MESSAGES, withdraw
from tests.test_workbench import page


def channel_import(client: TestClient, shop: int, text: str, channel: str) -> dict[str, Any]:
    uploaded = client.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic-foundation.csv",
            "kind": "orders",
            "source_channel": channel,
            "data_identity": "synthetic",
            "timezone": "UTC",
        },
        content=text.encode(),
    )
    assert uploaded.status_code == 201, uploaded.text
    return commit(client, preview(client, uploaded.json()))


def test_channel_scope_calculation_saved_record_and_workbench(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    imported(logged_in, shop, PRODUCTS, "products")
    channel_import(logged_in, shop, ORDERS, "generic")
    channel_import(
        logged_in, shop, ORDERS.replace("O1,", "O2,").replace(",2,8,", ",1,100,"), "amazon"
    )
    all_channels = calculate(logged_in, shop)
    generic = calculate(logged_in, shop, channel="generic")
    amazon = calculate(logged_in, shop, channel="amazon")
    assert Decimal(all_channels["summary"]["sales"]) == Decimal("116")
    assert Decimal(generic["summary"]["sales"]) == Decimal("16")
    assert Decimal(amazon["summary"]["sales"]) == Decimal("100")
    assert [line["order_id"] for line in amazon["lines"]] == ["O2"]
    saved = save(logged_in, shop, channel="amazon")
    response = logged_in.post(f"/api/shops/{shop}/analytics/saved/{saved['id']}/todo")
    assert response.status_code == 200, response.text
    scoped = page(logged_in, shop_id=shop, channel="amazon")
    assert {item["kind"] for item in scoped["items"]} == {"analysis", "analysis_todo"}
    assert all(item["channel"] == "amazon" for item in scoped["items"])
    assert page(logged_in, shop_id=shop, channel="generic")["items"] == []
    assert saved["scope"]["channel"] == "amazon"


def test_task_destinations_resolve_current_objects_and_hide_stale_sources(
    logged_in: TestClient,
) -> None:
    shop = create_shop(logged_in)
    other = create_shop(logged_in, "foundation-other")
    imported(logged_in, other, MESSAGES, "messages")
    batches = {}
    for kind, text in [
        ("products", PRODUCTS),
        ("orders", ORDERS),
        ("inventory", csv()),
        ("messages", MESSAGES),
    ]:
        batches[kind] = imported(logged_in, shop, text, kind)
    run(logged_in, shop, max_age_hours=48)
    items = tasks(logged_in, shop)
    targets = {}
    for item in items:
        detail = logged_in.get(root(shop) + f"/tasks/{item['id']}").json()
        assert detail["data_identity"] == "synthetic" and detail["channel"] == "generic"
        assert detail["destinations"]
        targets[item["kind"]] = detail["destinations"]
        for destination in detail["destinations"]:
            query = destination["query"]
            assert query["shop"] == str(shop)
            assert query["identity"] == "synthetic" and query["channel"] == "generic"
            assert query["return_task"] == str(item["id"])
    low = next(link for link in targets["low_margin"] if link["path"] == "/analytics")
    assert low["query"]["start_at"] == "2026-10-06T16:00:00+00:00"
    assert low["query"]["end_at"] == "2026-10-07T16:00:00+00:00"
    assert targets["low_inventory"][0]["query"]["max_age_hours"] == "48"
    message = next(link for link in targets["message_review"] if link["path"] == "/support")
    message_id = message["query"]["message"]
    assert logged_in.get(f"/api/shops/{shop}/support/messages/{message_id}").status_code == 200
    assert logged_in.get(f"/api/shops/{other}/support/messages/{message_id}").status_code == 404
    withdraw(logged_in, batches["messages"], "revoke")
    task = next(item for item in items if item["kind"] == "message_review")
    stale = logged_in.get(root(shop) + f"/tasks/{task['id']}").json()
    assert stale["source_status"] == "stale" and stale["destinations"] == []


def test_shared_foundation_samples_amounts_channels_and_invalid_duplicate(
    logged_in: TestClient,
) -> None:
    generator = Path(__file__).resolve().parents[2] / "scripts" / "foundation_samples.py"
    sample = runpy.run_path(str(generator))["samples"](datetime.now(UTC))
    shop = create_shop(logged_in, "foundation-shared")
    for file in sample["files"]:
        uploaded = logged_in.post(
            f"/api/shops/{shop}/imports",
            params={
                "filename": file["filename"],
                "kind": file["kind"],
                "source_channel": file["channel"],
                "data_identity": "synthetic",
                "timezone": "UTC",
            },
            content=file["text"].encode(),
        )
        assert uploaded.status_code == 201, uploaded.text
        commit(logged_in, preview(logged_in, uploaded.json()))
    scope = {key: value for key, value in sample["scope"].items() if key != "max_age_hours"}
    for channel, expected in [("amazon", "amazon_usd"), (None, "all_channels_usd")]:
        response = logged_in.post(
            f"/api/shops/{shop}/analytics/calculate", json={**scope, "channel": channel}
        )
        assert response.status_code == 200, response.text
        data = response.json()
        for field in ["sales", "cost", "gross_profit"]:
            amount = sample["expected"][expected][field]
            assert (
                Decimal(data["summary"][field]) if data["summary"][field] is not None else None
            ) == (Decimal(amount) if amount is not None else None)
        assert data["ranking_available"] is (channel == "amazon")
        if channel == "amazon":
            assert data["candidates"] == ["SYN-CUP"]
            assert len(data["lines"]) == 3
            assert data["summary"]["purchased_quantity"] == 4
        else:
            assert len(data["lines"]) == 5
            assert (
                next(line for line in data["lines"] if line["order_id"] == "SYN-EUR")["included"]
                is False
            )
    run(logged_in, shop, **sample["scope"])
    response = logged_in.get(
        root(shop) + "/tasks", params={"data_identity": "synthetic", "channel": "amazon"}
    )
    items = response.json()["items"]
    assert len(items) == sample["expected"]["task_count"]
    stocks = [task["snapshot"]["object_label"] for task in items if task["kind"] == "low_inventory"]
    assert stocks == ["SYN-CUP"]
    duplicate = logged_in.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic-duplicate.csv",
            "kind": "orders",
            "source_channel": "amazon",
            "data_identity": "synthetic",
            "timezone": "UTC",
        },
        content=sample["boundaries"]["duplicate_orders"].encode(),
    ).json()
    checked = preview(logged_in, duplicate)
    assert checked["error_rows"] == 2
    assert (
        logged_in.post(
            f"/api/imports/{checked['id']}/commit", json={"version": checked["version"]}
        ).status_code
        == 409
    )
