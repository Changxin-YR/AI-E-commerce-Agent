from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.expenses import ExpenseControl
from app.schemas.fee_rules import (
    FeeRuleDraft,
    FeeRulePage,
    FeeRulePreview,
    FeeRuleSaved,
    FeeRuleWrite,
)
from app.schemas.imports import DataIdentity, SourceChannel
from app.services.fee_rules import FeeRuleService

router = APIRouter(prefix="/shops/{shop_id}/fee-rules", tags=["收费映射规则"])


@router.post("/preview")
def preview(
    shop_id: int, data: FeeRuleDraft, current: CurrentSession, uow: UowDependency
) -> FeeRulePreview:
    return FeeRuleService(uow).preview(current.user_id, shop_id, data)


@router.post("")
def write(
    shop_id: int, data: FeeRuleWrite, current: CurrentSession, uow: UowDependency
) -> FeeRuleSaved:
    return FeeRuleService(uow).write(current.user_id, shop_id, data)


@router.get("")
def page(
    shop_id: int,
    data_identity: DataIdentity,
    channel: SourceChannel,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> FeeRulePage:
    return FeeRuleService(uow).page(current.user_id, shop_id, data_identity, channel, before)


@router.get("/{rule_id}")
def get(shop_id: int, rule_id: int, current: CurrentSession, uow: UowDependency) -> FeeRuleSaved:
    return FeeRuleService(uow).get(current.user_id, shop_id, rule_id)


@router.post("/{rule_id}/{action}")
def control(
    shop_id: int,
    rule_id: int,
    action: Literal["withdraw", "clear"],
    data: ExpenseControl,
    current: CurrentSession,
    uow: UowDependency,
) -> FeeRuleSaved:
    return FeeRuleService(uow).control(current.user_id, shop_id, rule_id, action, data)
