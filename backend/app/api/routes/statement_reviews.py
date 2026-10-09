from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import ExpenseControl
from app.schemas.imports import DataIdentity, SourceChannel
from app.schemas.statement_reviews import (
    ReviewCurrent,
    ReviewDraft,
    ReviewPage,
    ReviewPreview,
    ReviewSaved,
    ReviewWrite,
)
from app.services.statement_reviews import StatementReviewService

router = APIRouter(prefix="/shops/{shop_id}/statement-reviews", tags=["人工核对结论"])


@router.post("/preview")
def preview(
    shop_id: int, data: ReviewDraft, current: CurrentSession, uow: UowDependency
) -> ReviewPreview:
    return StatementReviewService(uow).preview(current.user_id, shop_id, data)


@router.post("")
def write(
    shop_id: int, data: ReviewWrite, current: CurrentSession, uow: UowDependency
) -> ReviewSaved:
    return StatementReviewService(uow).write(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> ReviewPage:
    return StatementReviewService(uow).page(
        current.user_id, shop_id, data_identity, channel, before
    )


@router.get("/{review_id}")
def get(
    shop_id: int,
    review_id: int,
    current: CurrentSession,
    uow: UowDependency,
    version: Annotated[int | None, Query(gt=0)] = None,
) -> ReviewSaved:
    return StatementReviewService(uow).get(current.user_id, shop_id, review_id, version)


@router.get("/{review_id}/current")
def read_current(
    shop_id: int, review_id: int, current: CurrentSession, uow: UowDependency
) -> ReviewCurrent:
    return StatementReviewService(uow).current(current.user_id, shop_id, review_id)


@router.post("/{review_id}/{action}")
def control(
    shop_id: int,
    review_id: int,
    action: Literal["withdraw", "clear"],
    data: ExpenseControl,
    current: CurrentSession,
    uow: UowDependency,
) -> ReviewSaved:
    return StatementReviewService(uow).control(current.user_id, shop_id, review_id, action, data)
