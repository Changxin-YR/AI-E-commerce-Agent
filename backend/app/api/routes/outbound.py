from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import CurrentSession, SettingsDependency, UowDependency
from app.schemas.outbound import (
    ApproveMail,
    ChannelOutput,
    ConfirmMail,
    CreateMail,
    EditMail,
    MailOutput,
    MailPage,
    MailVersion,
    ReceiptEvidence,
    ReconcileMail,
    SendMail,
    VerifyMailbox,
)
from app.services.outbound import OutboundService
from app.services.outbound_channels import OutboundChannels
from app.services.outbound_provider import MailProvider, ResendMailProvider

router = APIRouter(prefix="/shops/{shop_id}/outbound", tags=["R2 测试外发"])


def get_provider(settings: SettingsDependency) -> MailProvider:
    return ResendMailProvider(settings)


Provider = Annotated[MailProvider, Depends(get_provider)]


def service(
    uow: UowDependency, settings: SettingsDependency, provider: Provider
) -> OutboundService:
    return OutboundService(uow, settings, provider)


def channels(
    uow: UowDependency, settings: SettingsDependency, provider: Provider
) -> OutboundChannels:
    return OutboundChannels(uow, settings, provider)


Service = Annotated[OutboundService, Depends(service)]
Channels = Annotated[OutboundChannels, Depends(channels)]


@router.get("/channel")
def channel(shop_id: int, current: CurrentSession, svc: Channels) -> ChannelOutput:
    return svc.current(current.user_id, shop_id)


@router.post("/channel/connect")
def connect(
    shop_id: int, data: ConfirmMail, current: CurrentSession, svc: Channels
) -> ChannelOutput:
    return svc.connect(current.user_id, shop_id)


@router.post("/channel/{channel_id}/verify")
def verify(
    shop_id: int, channel_id: int, data: VerifyMailbox, current: CurrentSession, svc: Channels
) -> ChannelOutput:
    return svc.verify(current.user_id, shop_id, channel_id, data.code)


@router.post("/channel/{channel_id}/revoke")
def revoke_channel(
    shop_id: int, channel_id: int, current: CurrentSession, svc: Channels
) -> ChannelOutput:
    return svc.revoke(current.user_id, shop_id, channel_id)


@router.get("/messages")
def messages(
    shop_id: int,
    current: CurrentSession,
    svc: Service,
    before_id: Annotated[int | None, Query(gt=0)] = None,
) -> MailPage:
    return svc.list(current.user_id, shop_id, before_id)


@router.post("/messages")
def create(shop_id: int, data: CreateMail, current: CurrentSession, svc: Service) -> MailOutput:
    return svc.create(current.user_id, shop_id, data.run_id)


@router.get("/messages/{message_id}")
def get(shop_id: int, message_id: int, current: CurrentSession, svc: Service) -> MailOutput:
    return svc.get(current.user_id, shop_id, message_id)


@router.patch("/messages/{message_id}")
def edit(
    shop_id: int, message_id: int, data: EditMail, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.edit(current.user_id, shop_id, message_id, data)


@router.post("/messages/{message_id}/approve")
def approve(
    shop_id: int, message_id: int, data: ApproveMail, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.approve(current.user_id, shop_id, message_id, data)


@router.post("/messages/{message_id}/approvals/{approval_id}/revoke")
def revoke(
    shop_id: int, message_id: int, approval_id: int, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.revoke(current.user_id, shop_id, message_id, approval_id)


@router.post("/messages/{message_id}/reject")
def reject(
    shop_id: int, message_id: int, data: MailVersion, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.reject(current.user_id, shop_id, message_id, data.version)


@router.post("/messages/{message_id}/send")
def send(
    shop_id: int, message_id: int, data: SendMail, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.send(current.user_id, shop_id, message_id, data)


@router.post("/messages/{message_id}/reconcile")
def reconcile(
    shop_id: int, message_id: int, data: ReconcileMail, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.reconcile(
        current.user_id, shop_id, message_id, str(data.receipt_id) if data.receipt_id else None
    )


@router.post("/messages/{message_id}/receipt")
def receipt(
    shop_id: int, message_id: int, data: ReceiptEvidence, current: CurrentSession, svc: Service
) -> MailOutput:
    return svc.receipt(current.user_id, shop_id, message_id, data.evidence)
