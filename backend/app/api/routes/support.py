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
from app.services.support import SupportService

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
