from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.common import InputModel, OutputModel
from app.schemas.expenses import ExpenseScope
from app.schemas.imports import DataIdentity, SourceChannel
from app.schemas.statements import StatementReconciliation


class ReviewConclusion(InputModel):
    outcome: Literal["consistent", "differences_recorded", "pending"]
    note: Annotated[str, Field(min_length=1, max_length=1000)]


class ReviewDraft(InputModel):
    scope: ExpenseScope
    review_id: Annotated[int | None, Field(gt=0)] = None
    version: Annotated[int, Field(ge=0)] = 0
    conclusion: ReviewConclusion


class ReviewSnapshot(OutputModel):
    conclusion: ReviewConclusion
    result: StatementReconciliation
    expense_revision: int
    blockers: list[str]


class ReviewPreview(OutputModel):
    preview_hash: str
    snapshot: ReviewSnapshot


class ReviewWrite(ReviewDraft):
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    request_id: UUID
    confirm: Literal[True]


class ReviewHistory(OutputModel):
    version: int
    action: str
    conclusion: ReviewConclusion | None
    created_at: str


class ReviewSaved(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    status: Literal["active", "stale", "withdrawn", "cleared"]
    version: int
    content_version: int
    created_at: str
    snapshot: ReviewSnapshot | None
    history: list[ReviewHistory] = Field(default_factory=list)


class ReviewPage(OutputModel):
    items: list[ReviewSaved]
    next_cursor: int | None


class ReviewCurrent(OutputModel):
    record: ReviewSaved
    preview: ReviewPreview | None
