from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import ExpenseControl
from app.schemas.imports import DataIdentity, SourceChannel
from app.schemas.settlements import (
    SettlementCurrent,
    SettlementDraft,
    SettlementPage,
    SettlementPreview,
    SettlementSaved,
    SettlementWrite,
)
from app.services.settlements import SettlementService

router = APIRouter(prefix="/shops/{shop_id}/settlements", tags=["人工结算周期与回款"])


@router.post("/preview")
def preview(
    shop_id: int, data: SettlementDraft, current: CurrentSession, uow: UowDependency
) -> SettlementPreview:
    return SettlementService(uow).preview(current.user_id, shop_id, data)


@router.post("")
def write(
    shop_id: int, data: SettlementWrite, current: CurrentSession, uow: UowDependency
) -> SettlementSaved:
    return SettlementService(uow).write(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> SettlementPage:
    return SettlementService(uow).page(current.user_id, shop_id, data_identity, channel, before)


@router.get("/{settlement_id}")
def get(
    shop_id: int,
    settlement_id: int,
    current: CurrentSession,
    uow: UowDependency,
    version: Annotated[int | None, Query(gt=0)] = None,
) -> SettlementSaved:
    return SettlementService(uow).get(current.user_id, shop_id, settlement_id, version)


@router.get("/{settlement_id}/current")
def read_current(
    shop_id: int, settlement_id: int, current: CurrentSession, uow: UowDependency
) -> SettlementCurrent:
    return SettlementService(uow).current(current.user_id, shop_id, settlement_id)


@router.post("/{settlement_id}/{action}")
def control(
    shop_id: int,
    settlement_id: int,
    action: Literal["withdraw", "clear"],
    data: ExpenseControl,
    current: CurrentSession,
    uow: UowDependency,
) -> SettlementSaved:
    return SettlementService(uow).control(current.user_id, shop_id, settlement_id, action, data)
