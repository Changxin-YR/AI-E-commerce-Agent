from typing import Annotated, Literal

from pydantic import Field, StrictBool

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, OutputModel

PositiveId = Annotated[int, Field(gt=0)]


class ListingContent(InputModel):
    title: Annotated[str, Field(min_length=1, max_length=240)]
    description: Annotated[str, Field(max_length=4000)]


class ProductFacts(OutputModel):
    product_id: int
    sku: str
    name: str
    facts: str
    source: SourceReference


class GenerateInput(InputModel):
    product_id: PositiveId
    expected_source_row_id: PositiveId
    expected_active_id: PositiveId | None


class ReviseInput(InputModel):
    expected_version: PositiveId
    expected_active_id: PositiveId | None
    content: ListingContent


class DecisionInput(InputModel):
    expected_version: PositiveId
    decision: Literal["approve", "reject"]
    facts_confirmed: StrictBool = False


class ListingSnapshot(OutputModel):
    product: ProductFacts
    before: ListingContent
    proposed: ListingContent
    missing: list[str]
    blockers: list[str]


class ListingOutput(OutputModel):
    id: int
    shop_id: int
    number: int
    version: int
    status: str
    source_status: str
    base_version_id: int | None
    engine: str
    snapshot: ListingSnapshot | None
    created_at: str
    decided_at: str | None
    external_status: Literal["not_submitted"] = "not_submitted"
    risk: Literal["R1"] = "R1"


class ProductWorkspace(OutputModel):
    product: ProductFacts
    active_id: int | None
    active_version: ListingOutput | None
    versions: list[ListingOutput]
