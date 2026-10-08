from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.inventory import InventoryOutput, InventoryQuery
from app.services.inventory import InventoryService

router = APIRouter(tags=["库存快照"])


@router.get("/shops/{shop_id}/inventory")
def inventory(
    shop_id: int,
    scope: Annotated[InventoryQuery, Query()],
    current: CurrentSession,
    uow: UowDependency,
) -> InventoryOutput:
    return InventoryService(uow).list(current.user_id, shop_id, scope)
