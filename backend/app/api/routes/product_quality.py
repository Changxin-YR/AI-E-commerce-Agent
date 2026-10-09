from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.product_quality import (
    QualityClear,
    QualityPage,
    QualityResult,
    QualitySave,
    QualitySaved,
    QualityScope,
)
from app.services.product_quality import ProductQualityService

router = APIRouter(prefix="/shops/{shop_id}/product-quality", tags=["商品信息质量"])


@router.post("/preview")
def preview(
    shop_id: int, data: QualityScope, current: CurrentSession, uow: UowDependency
) -> QualityResult:
    return ProductQualityService(uow).preview(current.user_id, shop_id, data)


@router.post("/reports", status_code=201)
def save(
    shop_id: int, data: QualitySave, current: CurrentSession, uow: UowDependency
) -> QualitySaved:
    return ProductQualityService(uow).save(current.user_id, shop_id, data)


@router.get("/reports")
def page(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> QualityPage:
    return ProductQualityService(uow).page(current.user_id, shop_id, before)


@router.get("/reports/{report_id}")
def get(shop_id: int, report_id: int, current: CurrentSession, uow: UowDependency) -> QualitySaved:
    return ProductQualityService(uow).get(current.user_id, shop_id, report_id)


@router.post("/reports/{report_id}/clear")
def clear(
    shop_id: int, report_id: int, data: QualityClear, current: CurrentSession, uow: UowDependency
) -> QualitySaved:
    return ProductQualityService(uow).clear(current.user_id, shop_id, report_id)
