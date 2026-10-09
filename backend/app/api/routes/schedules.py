from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, SettingsDependency, UowDependency
from app.schemas.schedules import (
    CreateSchedule,
    ManualCheck,
    OccurrenceOutput,
    ScheduleAction,
    ScheduleOutput,
)
from app.services.schedules import SchedulesService

router = APIRouter(prefix="/shops/{shop_id}/schedules", tags=["定时运营"])


@router.get("/status")
def status(
    shop_id: int, current: CurrentSession, uow: UowDependency, settings: SettingsDependency
) -> dict[str, bool]:
    SchedulesService(uow).schedules(current.user_id, shop_id)
    return {"worker_enabled": settings.scheduler_enabled}


@router.get("")
def schedules(shop_id: int, current: CurrentSession, uow: UowDependency) -> list[ScheduleOutput]:
    return SchedulesService(uow).schedules(current.user_id, shop_id)


@router.post("")
def create(
    shop_id: int, data: CreateSchedule, current: CurrentSession, uow: UowDependency
) -> ScheduleOutput:
    return SchedulesService(uow).create(current.user_id, shop_id, data)


@router.get("/history")
def history(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before: int | None = Query(default=None, ge=1),
    unread: bool = False,
) -> list[OccurrenceOutput]:
    return SchedulesService(uow).history(current.user_id, shop_id, before, unread=unread)


@router.post("/history/{item_id}/read")
def read(
    shop_id: int, item_id: int, current: CurrentSession, uow: UowDependency
) -> OccurrenceOutput:
    return SchedulesService(uow).mark_read(current.user_id, shop_id, item_id)


@router.post("/{schedule_id}")
def act(
    shop_id: int,
    schedule_id: int,
    data: ScheduleAction,
    current: CurrentSession,
    uow: UowDependency,
) -> ScheduleOutput:
    return SchedulesService(uow).act(current.user_id, shop_id, schedule_id, data)


@router.post("/{schedule_id}/check")
def check(
    shop_id: int, schedule_id: int, data: ManualCheck, current: CurrentSession, uow: UowDependency
) -> OccurrenceOutput:
    return SchedulesService(uow).manual(current.user_id, shop_id, schedule_id, data)
