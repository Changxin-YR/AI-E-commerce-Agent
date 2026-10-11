from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import InputModel, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel
from app.schemas.order_reconciliation import OrderReconciliation, OrderReconciliationScope


class OrderReviewConclusion(InputModel):
    outcome: Literal["consistent", "differences_recorded", "pending"]
    note: Annotated[str, Field(min_length=1, max_length=1000)]


class OrderReviewDraft(InputModel):
    scope: OrderReconciliationScope
    review_id: Annotated[int | None, Field(gt=0)] = None
    version: Annotated[int, Field(ge=0)] = 0
    conclusion: OrderReviewConclusion


class OrderReviewSnapshot(OutputModel):
    conclusion: OrderReviewConclusion
    result: OrderReconciliation
    blockers: list[str]


class OrderReviewPreview(OutputModel):
    preview_hash: str
    snapshot: OrderReviewSnapshot


class OrderReviewWrite(OrderReviewDraft):
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    request_id: UUID
    confirm: Literal[True]


class OrderReviewHistory(OutputModel):
    version: int
    action: str
    conclusion: OrderReviewConclusion | None
    created_at: str


class OrderReviewSaved(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    status: Literal["active", "stale", "withdrawn", "cleared"]
    version: int
    content_version: int
    created_at: str
    snapshot: OrderReviewSnapshot | None
    history: list[OrderReviewHistory] = Field(default_factory=list)


class OrderReviewPage(OutputModel):
    items: list[OrderReviewSaved]
    next_cursor: int | None


class OrderReviewCurrent(OutputModel):
    record: OrderReviewSaved
    preview: OrderReviewPreview | None
