from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.overview import (
    OverviewClear,
    OverviewPage,
    OverviewResult,
    OverviewSave,
    OverviewSaved,
    OverviewScope,
)
from app.services.overview import OverviewService

router = APIRouter(prefix="/overview", tags=["跨店经营总览"])


@router.post("/calculate")
def calculate(data: OverviewScope, current: CurrentSession, uow: UowDependency) -> OverviewResult:
    return OverviewService(uow).calculate(current.user_id, data)


@router.post("/reports", status_code=201)
def save(data: OverviewSave, current: CurrentSession, uow: UowDependency) -> OverviewSaved:
    return OverviewService(uow).save(current.user_id, data)


@router.get("/reports")
def page(
    current: CurrentSession, uow: UowDependency, before: Annotated[int | None, Query(gt=0)] = None
) -> OverviewPage:
    return OverviewService(uow).page(current.user_id, before)


@router.get("/reports/{report_id}")
def get(report_id: int, current: CurrentSession, uow: UowDependency) -> OverviewSaved:
    return OverviewService(uow).get(current.user_id, report_id)


@router.post("/reports/{report_id}/clear")
def clear(
    report_id: int, data: OverviewClear, current: CurrentSession, uow: UowDependency
) -> OverviewSaved:
    return OverviewService(uow).clear(current.user_id, report_id)
