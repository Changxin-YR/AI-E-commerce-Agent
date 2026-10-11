from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import ExpenseControl
from app.schemas.imports import DataIdentity, SourceChannel
from app.schemas.order_statement_reviews import (
    OrderReviewCurrent,
    OrderReviewDraft,
    OrderReviewPage,
    OrderReviewPreview,
    OrderReviewSaved,
    OrderReviewWrite,
)
from app.services.order_statement_reviews import OrderStatementReviewService

router = APIRouter(prefix="/shops/{shop_id}/order-statement-reviews", tags=["订单账单核对审阅"])


@router.post("/preview")
def preview(
    shop_id: int, data: OrderReviewDraft, current: CurrentSession, uow: UowDependency
) -> OrderReviewPreview:
    return OrderStatementReviewService(uow).preview(current.user_id, shop_id, data)


@router.post("")
def write(
    shop_id: int, data: OrderReviewWrite, current: CurrentSession, uow: UowDependency
) -> OrderReviewSaved:
    return OrderStatementReviewService(uow).write(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> OrderReviewPage:
    return OrderStatementReviewService(uow).page(
        current.user_id, shop_id, data_identity, channel, before
    )


@router.get("/{review_id}")
def get(
    shop_id: int,
    review_id: int,
    current: CurrentSession,
    uow: UowDependency,
    version: Annotated[int | None, Query(gt=0)] = None,
) -> OrderReviewSaved:
    return OrderStatementReviewService(uow).get(current.user_id, shop_id, review_id, version)


@router.get("/{review_id}/current")
def read_current(
    shop_id: int, review_id: int, current: CurrentSession, uow: UowDependency
) -> OrderReviewCurrent:
    return OrderStatementReviewService(uow).current(current.user_id, shop_id, review_id)


@router.post("/{review_id}/{action}")
def control(
    shop_id: int,
    review_id: int,
    action: Literal["withdraw", "clear"],
    data: ExpenseControl,
    current: CurrentSession,
    uow: UowDependency,
) -> OrderReviewSaved:
    return OrderStatementReviewService(uow).control(
        current.user_id, shop_id, review_id, action, data
    )
