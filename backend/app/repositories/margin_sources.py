"""One read-only Listing baseline predicate for B1 gates and inbox projections."""

from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import InstrumentedAttribute
from sqlalchemy.sql import ColumnElement

from app.models.agent import AgentExecution, AgentStep
from app.models.imports import ImportBatch, ImportRow, Product
from app.models.listings import ListingVersion

Expr = ColumnElement[Any] | InstrumentedAttribute[Any]


def listing_current(owner: Expr, shop: Expr, target: Expr) -> ColumnElement[bool]:
    product = target["product"]
    source = product["source"]
    listing = ListingVersion
    # Source reference metadata is immutable: a row/batch identity change is a
    # source change. Approved content is immutable; replacement supersedes it.
    return exists(
        select(listing.id)
        .select_from(listing)
        .join(Product, Product.id == product["product_id"].as_integer())
        .join(ImportRow, ImportRow.id == Product.source_row_id)
        .join(ImportBatch, ImportBatch.id == ImportRow.batch_id)
        .where(
            listing.id == target["active_id"].as_integer(),
            listing.owner_id == owner,
            listing.shop_id == shop,
            listing.status == "approved",
            listing.source_status == "current",
            listing.snapshot["product"]["sku"].as_string() == Product.sku,
            listing.snapshot["proposed"]["title"].as_string()
            == target["before"]["title"].as_string(),
            listing.snapshot["proposed"]["description"].as_string()
            == target["before"]["description"].as_string(),
            Product.shop_id == shop,
            Product.sku == product["sku"].as_string(),
            Product.name == product["name"].as_string(),
            Product.facts == product["facts"].as_string(),
            ImportRow.id == source["row_id"].as_integer(),
            ImportBatch.id == source["batch_id"].as_integer(),
            ImportBatch.owner_id == owner,
            ImportBatch.shop_id == shop,
            ImportBatch.status == "committed",
        )
        .correlate_except(listing, Product, ImportRow, ImportBatch)
    )


def margin_listing_changed() -> ColumnElement[bool]:
    step = AgentStep
    target = step.output["listing"]
    return exists(
        select(step.id)
        .where(
            step.execution_id == AgentExecution.id,
            step.skill == "margin_evidence",
            step.status == "completed",
            target["active_id"].as_integer().is_not(None),
            ~listing_current(AgentExecution.owner_id, AgentExecution.shop_id, target),
        )
        .correlate_except(step)
    )
