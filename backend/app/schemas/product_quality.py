from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel


class QualityScope(InputModel):
    data_identity: DataIdentity = "user_import"
    channel: SourceChannel | None = None
    sku_prefix: Annotated[str, Field(max_length=120)] = ""


class QualityIssue(OutputModel):
    code: str
    field: str
    status: Literal["missing", "review"]
    reason: str
    suggestion: str


class QualityProduct(OutputModel):
    product_id: int
    sku: str
    name: str
    facts: str
    price: Decimal | None
    currency: str | None
    unit_cost: Decimal | None
    cost_currency: str | None
    channel: str
    source: SourceReference
    issues: list[QualityIssue]
    similar_skus: list[str]
    similar_sku_count: int


class QualityCoverage(OutputModel):
    code: str
    label: str
    status: Literal["checked", "not_checked"]
    reason: str


class QualityResult(OutputModel):
    shop_id: int
    scope: QualityScope
    source_revision: int
    checked_at: str
    rule_version: str
    preview_hash: str
    product_count: int
    affected_products: int
    missing_count: int
    review_count: int
    coverage: list[QualityCoverage]
    limitations: list[str]
    products: list[QualityProduct]


class QualitySave(InputModel):
    scope: QualityScope
    expected_revision: Annotated[int, Field(ge=0)]
    expected_preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    request_id: UUID
    confirm: Literal[True]


class QualityClear(InputModel):
    confirm: Literal[True]


class QualitySaved(OutputModel):
    id: int
    shop_id: int
    status: Literal["current", "stale", "cleared"]
    created_at: str
    scope: QualityScope
    snapshot: QualityResult | None


class QualityPage(OutputModel):
    items: list[QualitySaved]
    next_cursor: int | None
