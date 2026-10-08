from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.business_rules import RuleChange, RuleRevision, RuleScope
from app.schemas.imports import DataIdentity, SourceChannel
from app.services.business_rules import BusinessRulesService

router = APIRouter(prefix="/shops/{shop_id}/business-rules", tags=["经营规则"])


@router.get("")
def current(
    shop_id: int, scope: Annotated[RuleScope, Query()], current: CurrentSession, uow: UowDependency
) -> RuleRevision:
    return BusinessRulesService(uow).current(current.user_id, shop_id, scope)


@router.get("/history")
def history(
    shop_id: int,
    current: CurrentSession,
    uow: UowDependency,
    channel: SourceChannel = "generic",
    data_identity: DataIdentity = "user_import",
    before: Annotated[int | None, Query(gt=0)] = None,
) -> list[RuleRevision]:
    scope = RuleScope.model_validate({"channel": channel, "data_identity": data_identity})
    return BusinessRulesService(uow).history(current.user_id, shop_id, scope, before)


@router.get("/{version}")
def get(shop_id: int, version: int, current: CurrentSession, uow: UowDependency) -> RuleRevision:
    return BusinessRulesService(uow).get(current.user_id, shop_id, version)


@router.post("")
def change(
    shop_id: int, data: RuleChange, current: CurrentSession, uow: UowDependency
) -> RuleRevision:
    return BusinessRulesService(uow).change(current.user_id, shop_id, data)
