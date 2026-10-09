from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, model_validator

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, ProductData, SourceChannel


class ProductChange(InputModel):
    product_id: Annotated[int, Field(gt=0)]
    expected_source_row_id: Annotated[int, Field(gt=0)]
    name: Annotated[str, Field(min_length=1, max_length=240)]
    facts: Annotated[str, Field(max_length=2000)]

    @model_validator(mode="after")
    def nonblank(self) -> Self:
        if not self.name.strip():
            raise ValueError("商品名称不能为空白")
        return self


class EditContent(InputModel):
    data_identity: DataIdentity
    channel: SourceChannel
    reason: Annotated[str, Field(min_length=1, max_length=500)]
    changes: Annotated[list[ProductChange], Field(min_length=1, max_length=50)]

    @model_validator(mode="after")
    def unique_products(self) -> Self:
        if not self.reason.strip():
            raise ValueError("请填写修订依据")
        if len({c.product_id for c in self.changes}) != len(self.changes):
            raise ValueError("同一商品只能修订一次")
        return self


class EditCreate(EditContent):
    request_id: UUID


class EditDecision(InputModel):
    version: Annotated[int, Field(ge=1)]
    expected_preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    confirm: Literal[True]


class EditControl(InputModel):
    version: Annotated[int, Field(ge=1)]
    confirm: Literal[True]


class EditItem(OutputModel):
    product_id: int
    before: ProductData
    after: ProductData
    source: SourceReference
    result: Literal["pending", "applied", "conflict", "blocked"] = "pending"
    message: str = "等待审批"


class EditSnapshot(OutputModel):
    source_revision: int
    data_identity: DataIdentity
    channel: SourceChannel
    reason: str
    items: list[EditItem]


class EditSaved(OutputModel):
    id: int
    shop_id: int
    version: int
    status: Literal["draft", "applied", "failed", "rejected", "stale", "revoked", "cleared"]
    preview_hash: str
    snapshot: EditSnapshot | None
    output_batch_id: int | None
    created_at: str
    decided_at: str | None
    current_count: int


class EditPage(OutputModel):
    items: list[EditSaved]
    next_cursor: int | None
