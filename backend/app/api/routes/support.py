from typing import Annotated

from fastapi import APIRouter, Query

from app.api.dependencies import CurrentSession, UowDependency
from app.schemas.support import (
    EditReply,
    GenerateReply,
    MessageFacts,
    PolicyInput,
    PolicyOutput,
    ReplyAction,
    ReplyOutput,
    SupportWorkspace,
)
from app.schemas.support_delivery import (
    ManualActionOutput,
    RecordManualAction,
    ReviewReply,
    SupportDelivery,
)
from app.services.support import SupportService
from app.services.support_delivery import SupportDeliveryService

router = APIRouter(prefix="/shops/{shop_id}/support", tags=["客服消息与草稿"])
Search = Annotated[str, Query(max_length=120)]
Offset = Annotated[int, Query(ge=0, le=100000)]


@router.get("/messages")
def messages(
    shop_id: int, current: CurrentSession, uow: UowDependency, q: Search = "", offset: Offset = 0
) -> list[MessageFacts]:
    return SupportService(uow).messages(current.user_id, shop_id, q, offset)


@router.get("/messages/{message_id}")
def workspace(
    shop_id: int, message_id: int, current: CurrentSession, uow: UowDependency
) -> SupportWorkspace:
    return SupportService(uow).workspace(current.user_id, shop_id, message_id)


@router.post("/messages/{message_id}/generate", status_code=201)
def generate(
    shop_id: int, message_id: int, data: GenerateReply, current: CurrentSession, uow: UowDependency
) -> ReplyOutput:
    return SupportService(uow).generate(current.user_id, shop_id, message_id, data)


@router.get("/policies")
def policies(
    shop_id: int, current: CurrentSession, uow: UowDependency, q: Search = "", offset: Offset = 0
) -> list[PolicyOutput]:
    return SupportService(uow).policies(current.user_id, shop_id, q, offset)


@router.post("/policies", status_code=201)
def save_policy(
    shop_id: int, data: PolicyInput, current: CurrentSession, uow: UowDependency
) -> PolicyOutput:
    return SupportService(uow).save_policy(current.user_id, shop_id, data)


@router.post("/policies/{policy_id}/clear")
def clear_policy(
    shop_id: int, policy_id: int, current: CurrentSession, uow: UowDependency
) -> PolicyOutput:
    return SupportService(uow).clear_policy(current.user_id, shop_id, policy_id)


@router.get("/drafts")
def history(shop_id: int, current: CurrentSession, uow: UowDependency) -> list[ReplyOutput]:
    return SupportService(uow).history(current.user_id, shop_id)


@router.get("/drafts/{draft_id}")
def get(shop_id: int, draft_id: int, current: CurrentSession, uow: UowDependency) -> ReplyOutput:
    return SupportService(uow).get(current.user_id, shop_id, draft_id)


@router.post("/drafts/{draft_id}/edit")
def edit(
    shop_id: int, draft_id: int, data: EditReply, current: CurrentSession, uow: UowDependency
) -> ReplyOutput:
    return SupportService(uow).edit(current.user_id, shop_id, draft_id, data)


@router.post("/drafts/{draft_id}/action")
def action(
    shop_id: int, draft_id: int, data: ReplyAction, current: CurrentSession, uow: UowDependency
) -> ReplyOutput:
    return SupportService(uow).act(current.user_id, shop_id, draft_id, data)


@router.post("/drafts/{draft_id}/review")
def review(
    shop_id: int, draft_id: int, data: ReviewReply, current: CurrentSession, uow: UowDependency
) -> ReplyOutput:
    return SupportDeliveryService(uow).review(current.user_id, shop_id, draft_id, data)


@router.get("/drafts/{draft_id}/delivery")
def delivery(
    shop_id: int,
    draft_id: int,
    expected_version: Annotated[int, Query(gt=0)],
    current: CurrentSession,
    uow: UowDependency,
) -> SupportDelivery:
    return SupportDeliveryService(uow).delivery(
        current.user_id, shop_id, draft_id, expected_version
    )


@router.get("/drafts/{draft_id}/manual-actions")
def manual_actions(
    shop_id: int,
    draft_id: int,
    current: CurrentSession,
    uow: UowDependency,
    before: Annotated[int | None, Query(gt=0)] = None,
) -> list[ManualActionOutput]:
    return SupportDeliveryService(uow).history(current.user_id, shop_id, draft_id, before)


@router.post("/drafts/{draft_id}/manual-actions", status_code=201)
def record_manual_action(
    shop_id: int,
    draft_id: int,
    data: RecordManualAction,
    current: CurrentSession,
    uow: UowDependency,
) -> ManualActionOutput:
    return SupportDeliveryService(uow).record(current.user_id, shop_id, draft_id, data)
