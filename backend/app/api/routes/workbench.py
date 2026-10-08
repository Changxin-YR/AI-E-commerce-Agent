from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.workbench import WorkPage, WorkQuery
from app.services.workbench import WorkbenchService

router = APIRouter(prefix="/workbench", tags=["统一任务驾驶舱"])


@router.get("")
def page(
    query: Annotated[WorkQuery, Query()], current: CurrentSession, uow: UowDependency
) -> WorkPage:
    return WorkbenchService(uow).page(current.user_id, query)
