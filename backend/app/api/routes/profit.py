from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.profit import (
    SavedStudyOutput,
    SavedStudySummary,
    SaveStudyInput,
    StudyInput,
    StudyResult,
)
from app.services.profit import ProfitService

router = APIRouter(prefix="/shops/{shop_id}/profit", tags=["新品利润计算器"])


@router.post("/calculate")
def calculate(
    shop_id: int,
    data: StudyInput,
    current: CurrentSession,
    uow: UowDependency,
) -> StudyResult:
    return ProfitService(uow).calculate(current.user_id, shop_id, data)


@router.post("/saved", status_code=201)
def save(
    shop_id: int,
    data: SaveStudyInput,
    current: CurrentSession,
    uow: UowDependency,
) -> SavedStudyOutput:
    return ProfitService(uow).save(current.user_id, shop_id, data)


@router.get("/saved")
def list_saved(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
) -> list[SavedStudySummary]:
    return ProfitService(uow).list(current.user_id, shop_id, offset)


@router.get("/saved/{study_id}")
def get_saved(
    shop_id: int,
    study_id: int,
    current: CurrentSession,
    uow: UowDependency,
) -> SavedStudyOutput:
    return ProfitService(uow).get(current.user_id, shop_id, study_id)


@router.delete("/saved/{study_id}", status_code=204)
def clear_saved(
    shop_id: int,
    study_id: int,
    current: CurrentSession,
    uow: UowDependency,
) -> None:
    ProfitService(uow).clear(current.user_id, shop_id, study_id)
