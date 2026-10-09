from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.product_edits import EditControl, EditCreate, EditDecision, EditPage, EditSaved
from app.services.product_edits import ProductEditService

router = APIRouter(prefix="/shops/{shop_id}/product-edits", tags=["商品本地修订"])


@router.post("", status_code=201)
def create(
    shop_id: int, data: EditCreate, current: CurrentSession, uow: UowDependency
) -> EditSaved:
    return ProductEditService(uow).create(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> EditPage:
    return ProductEditService(uow).page(current.user_id, shop_id, before)


@router.get("/{edit_id}")
def get(shop_id: int, edit_id: int, current: CurrentSession, uow: UowDependency) -> EditSaved:
    return ProductEditService(uow).get(current.user_id, shop_id, edit_id)


@router.post("/{edit_id}/approve")
def approve(
    shop_id: int, edit_id: int, data: EditDecision, current: CurrentSession, uow: UowDependency
) -> EditSaved:
    return ProductEditService(uow).approve(current.user_id, shop_id, edit_id, data)


@router.post("/{edit_id}/{action}")
def control(
    shop_id: int,
    edit_id: int,
    action: Literal["reject", "withdraw", "clear"],
    data: EditControl,
    current: CurrentSession,
    uow: UowDependency,
) -> EditSaved:
    return ProductEditService(uow).control(current.user_id, shop_id, edit_id, action, data)
