from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.imports import Product
from app.services.import_presets import SHOPIFY_PRODUCTS, matching_presets
from tests.test_imports import commit, create_shop, preview

SAMPLE = (
    Path(__file__).resolve().parents[2]
    / "examples/imports/shopify-products-2026-10-10-synthetic.csv"
).read_text(encoding="utf-8")
HEADERS = SAMPLE.splitlines()[0].split(",")


def upload_preset(client: TestClient, shop: int, contents: str = SAMPLE) -> dict[str, Any]:
    response = client.post(
        f"/api/shops/{shop}/imports",
        params={
            "filename": "synthetic-shopify.csv",
            "kind": "products",
            "source_channel": "shopify",
            "data_identity": "synthetic",
            "timezone": "Asia/Shanghai",
        },
        content=contents.encode(),
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.parametrize(
    ("kind", "channel", "headers"),
    [
        ("orders", "shopify", HEADERS),
        ("products", "amazon", HEADERS),
        ("products", "generic", HEADERS),
        ("products", "shopify", [h.replace("SKU", "Variant SKU") for h in HEADERS]),
        ("products", "shopify", [h.replace("Price", "Price / International") for h in HEADERS]),
    ],
)
def test_unverified_format_has_no_preset(kind: str, channel: str, headers: list[str]) -> None:
    assert matching_presets(kind, channel, headers) == []


def test_preset_retires_without_mutating_definition() -> None:
    candidate = matching_presets("products", "shopify", HEADERS)[0]
    assert candidate.verified_on == "2026-10-10"
    assert candidate.reference_url.startswith("https://help.shopify.com/")
    candidate.mapping["price"] = "Price / International"
    assert matching_presets("products", "shopify", HEADERS)[0].mapping["price"] == "Price"
    with patch("app.services.import_presets.ACTIVE_PRESET_IDS", frozenset()):
        assert matching_presets("products", "shopify", HEADERS) == []


def test_preset_correction_review_save_readback_retire_and_revoke(
    logged_in: TestClient, session_factory: sessionmaker[Session]
) -> None:
    shop = create_shop(logged_in)
    batch = upload_preset(logged_in, shop)
    candidate = batch["presets"][0]
    assert candidate["mapping"] == SHOPIFY_PRODUCTS.mapping
    assert batch["mapping"] == {item["field"]: item["column"] for item in batch["suggestions"]}
    batch = preview(logged_in, batch, mapping=candidate["mapping"])
    assert batch["error_rows"] == 2
    assert {item["field"] for item in batch["rows"][0]["errors"]} == {"currency", "cost_currency"}
    assert any(item["field"] == "name" for item in batch["rows"][1]["errors"])
    assert (
        logged_in.post(
            f"/api/imports/{batch['id']}/commit", json={"version": batch["version"]}
        ).status_code
        == 409
    )
    batch = preview(
        logged_in,
        batch,
        corrections={
            2: {"currency": "USD", "cost_currency": "USD"},
            3: {"currency": "USD", "cost_currency": "USD", "name": "Synthetic cup large"},
        },
    )
    assert batch["valid_rows"] == 2
    assert (
        logged_in.post(
            f"/api/imports/{batch['id']}/commit", json={"version": batch["version"]}
        ).status_code
        == 409
    )
    saved = commit(logged_in, batch)
    assert saved["rows"][1]["raw"]["name"] == ""
    assert saved["rows"][1]["normalized"]["name"] == "Synthetic cup large"
    assert [row["normalized"]["unit_cost"] for row in saved["rows"]] == ["3.2500", "4.5000"]
    with session_factory() as session:
        products = list(session.scalars(select(Product).where(Product.shop_id == shop)))
        assert {p.sku for p in products} == {"SYN-S", "SYN-L"}
    with patch("app.services.import_presets.ACTIVE_PRESET_IDS", frozenset()):
        readback = logged_in.get(f"/api/imports/{saved['id']}").json()
        assert readback["presets"] == []
        assert readback["mapping"] == saved["mapping"]
        assert readback["rows"] == saved["rows"]
        second = upload_preset(logged_in, shop)
        second = preview(
            logged_in,
            second,
            mapping=candidate["mapping"],
            corrections={row["row_number"]: row["corrections"] for row in saved["rows"]},
        )
        assert second["unchanged_rows"] == 2
    assert (
        logged_in.post(
            f"/api/imports/{saved['id']}/revoke", json={"version": saved["version"]}
        ).status_code
        == 200
    )
    with session_factory() as session:
        assert list(session.scalars(select(Product).where(Product.shop_id == shop))) == []


def test_preset_unknown_cost_and_formula_stay_guarded(logged_in: TestClient) -> None:
    shop = create_shop(logged_in)
    sample = "URL handle,Title,SKU,Price,Cost per item,Description\nsynthetic,Cup,A,10,,plain\n"
    batch = upload_preset(logged_in, shop, sample)
    batch = preview(
        logged_in,
        batch,
        mapping=batch["presets"][0]["mapping"],
        corrections={2: {"currency": "USD"}},
    )
    assert batch["error_rows"] == 0
    assert batch["rows"][0]["normalized"]["unit_cost"] is None
    assert batch["rows"][0]["normalized"]["facts"] == ""
    malicious = upload_preset(logged_in, shop, sample.replace(",plain", ",=1+1"))
    malicious = preview(
        logged_in,
        malicious,
        mapping=malicious["presets"][0]["mapping"],
        corrections={2: {"currency": "USD"}},
    )
    assert malicious["error_rows"] == 1
    assert any(item["field"] == "Description" for item in malicious["rows"][0]["errors"])
