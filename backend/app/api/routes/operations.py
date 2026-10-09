from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.operations import (
    OperationContext,
    OperationScope,
    RunInput,
    RunOutput,
    TaskInput,
    TaskOutput,
    TaskPage,
    TaskQuery,
)
from app.services.operations import OperationsService

router = APIRouter(prefix="/shops/{shop_id}/operations", tags=["今日运营"])


@router.post("/preview")
def preview(
    shop_id: int, data: OperationScope, current: CurrentSession, uow: UowDependency
) -> OperationContext:
    return OperationsService(uow).model_context(current.user_id, shop_id, data)


@router.post("/runs")
def run(shop_id: int, data: RunInput, current: CurrentSession, uow: UowDependency) -> RunOutput:
    return OperationsService(uow).run(current.user_id, shop_id, data)


@router.get("/runs")
def runs(
    shop_id: int, scope: Annotated[TaskQuery, Query()], current: CurrentSession, uow: UowDependency
) -> list[RunOutput]:
    return OperationsService(uow).runs(current.user_id, shop_id, scope)


@router.get("/runs/{run_id}")
def get_run(shop_id: int, run_id: int, current: CurrentSession, uow: UowDependency) -> RunOutput:
    return OperationsService(uow).get_run(current.user_id, shop_id, run_id)


@router.get("/tasks")
def tasks(
    shop_id: int, scope: Annotated[TaskQuery, Query()], current: CurrentSession, uow: UowDependency
) -> TaskPage:
    return OperationsService(uow).tasks(current.user_id, shop_id, scope)


@router.get("/tasks/{task_id}")
def get_task(shop_id: int, task_id: int, current: CurrentSession, uow: UowDependency) -> TaskOutput:
    return OperationsService(uow).get_task(current.user_id, shop_id, task_id)


@router.post("/tasks/{task_id}")
def change_task(
    shop_id: int, task_id: int, data: TaskInput, current: CurrentSession, uow: UowDependency
) -> TaskOutput:
    return OperationsService(uow).change_task(current.user_id, shop_id, task_id, data)
