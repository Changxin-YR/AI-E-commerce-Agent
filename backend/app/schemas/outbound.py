from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator

from app.schemas.common import InputModel, OutputModel

PositiveId = Annotated[int, Field(gt=0)]


class ConfirmMail(InputModel):
    confirmed: StrictBool

    @field_validator("confirmed")
    @classmethod
    def require_confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("须明确确认此项 R2 操作")
        return value


class VerifyMailbox(InputModel):
    code: Annotated[str, Field(pattern=r"^[0-9]{8}$")]


class ChannelOutput(OutputModel):
    configured: bool
    provider: str = "resend"
    id: int | None = None
    status: str
    sender: str = ""
    recipient: str = ""
    receipt_id: str | None = None
    verified_at: str | None = None
    verification_expires_at: str | None = None
    verification_subject: str = "SoloOps 测试邮箱验证"
    verification_template: str = (
        "SoloOps 测试邮箱验证。验证码：{8 位随机码}。15 分钟内有效。"
        "此邮件仅验证本人测试邮箱，不含经营数据。"
    )


class CreateMail(InputModel):
    run_id: PositiveId
    recipient: (
        Annotated[
            str,
            Field(
                max_length=254,
                pattern=r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$",
            ),
        ]
        | None
    ) = None

    @field_validator("recipient", mode="before")
    @classmethod
    def no_address_controls(cls, value: object) -> object:
        if isinstance(value, str) and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("收件地址不能包含控制字符或换行")
        return value


class MailVersion(InputModel):
    version: PositiveId


class EditMail(MailVersion):
    subject: Annotated[str, Field(min_length=1, max_length=200)]
    body: Annotated[str, Field(min_length=1, max_length=12000)]

    @field_validator("subject")
    @classmethod
    def single_line(cls, value: str) -> str:
        if any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("主题不能包含控制字符或换行")
        return value


class ApproveMail(MailVersion, ConfirmMail):
    mode: Literal["once", "preauthorized"]
    valid_hours: Annotated[int, Field(ge=1, le=24)] = 1


class SendMail(MailVersion):
    approval_id: PositiveId


class ReconcileMail(InputModel):
    receipt_id: UUID | None = None


class ReceiptEvidence(ConfirmMail):
    evidence: Annotated[str, Field(min_length=5, max_length=500)]


class ApprovalOutput(OutputModel):
    id: int
    mode: str
    status: str
    max_uses: Literal[1] = 1
    used_count: int
    expires_at: str
    created_at: str


class MailOutput(OutputModel):
    id: int
    shop_id: int
    channel_id: int
    provider: str = "resend"
    smtp_message_id: str | None = None
    run_id: int
    sender: str
    recipient: str
    subject: str | None
    body: str | None
    content_hash: str
    status: str
    source_status: str
    channel_status: str
    version: int
    risk: Literal["R2"] = "R2"
    max_submissions: Literal[1] = 1
    dispatch_at: str | None
    receipt_id: str | None
    provider_event: str
    checked_at: str | None
    received_at: str | None
    receipt_evidence: str | None
    created_at: str
    approvals: list[ApprovalOutput]


class MailPage(OutputModel):
    items: list[MailOutput]
    next_before_id: int | None
