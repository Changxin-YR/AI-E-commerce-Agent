from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, Market, OutputModel
from app.schemas.imports import DataIdentity, SourceChannel

PositiveId = Annotated[int, Field(gt=0)]


class PolicyData(InputModel):
    code: Annotated[str, Field(min_length=1, max_length=80)]
    title: Annotated[str, Field(min_length=1, max_length=120)]
    topic: Literal["faq", "shipping", "refund", "warranty"]
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    market: Market
    channel: SourceChannel
    language: Literal["en", "zh"]
    data_identity: DataIdentity
    source: Annotated[str, Field(min_length=1, max_length=400)]
    source_version: Annotated[str, Field(min_length=1, max_length=80)]
    source_confirmed: StrictBool = False
    valid_from: datetime
    valid_until: datetime | None = None

    @field_validator("valid_from", "valid_until")
    @classmethod
    def aware_time(cls, value: datetime | None) -> datetime | None:
        if value is not None:
            if value.utcoffset() is None or value.year < 1000:
                raise ValueError("政策日期须包含时区偏移，年份不小于 1000")
            return value.astimezone(UTC)
        return value

    @model_validator(mode="after")
    def date_order(self) -> Self:
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            raise ValueError("政策结束时间须晚于生效时间（结束时间不包含在有效区间）")
        return self


class PolicyInput(InputModel):
    expected_policy_id: PositiveId | None
    data: PolicyData


class PolicyOutput(OutputModel):
    id: int
    number: int
    status: str
    availability: str
    data: PolicyData | None
    created_at: str


class MessageFacts(OutputModel):
    id: int
    message_id: str
    body: str
    language: str
    channel: str
    sent_at: str
    order_id: str
    source: SourceReference


class OrderFact(OutputModel):
    order_id: str
    line_id: str
    sku: str
    status: str
    fulfillment_status: str
    source: SourceReference


class GenerateReply(InputModel):
    expected_source_row_id: PositiveId
    expected_order_row_ids: list[PositiveId] = Field(default_factory=list, max_length=100)
    order_verified: StrictBool = False
    policy_ids: list[PositiveId] = Field(default_factory=list, max_length=10)


class ReplySnapshot(OutputModel):
    message: MessageFacts
    orders: list[OrderFact]
    order_verified: bool
    policies: list[PolicyOutput]
    intents: list[str]
    reasons: list[str]
    handoff_summary: str
    reply: str


class ReplyOutput(OutputModel):
    id: int
    version: int
    status: str
    source_status: str
    engine: str
    snapshot: ReplySnapshot | None
    created_at: str
    updated_at: str
    external_status: Literal["not_submitted"] = "not_submitted"


class EditReply(InputModel):
    expected_version: PositiveId
    reply: Annotated[str, Field(min_length=1, max_length=6000)]


class ReplyAction(InputModel):
    expected_version: PositiveId
    action: Literal["handoff", "archive", "reopen"]


class SupportWorkspace(OutputModel):
    message: MessageFacts
    orders: list[OrderFact]
    policies: list[PolicyOutput]
    drafts: list[ReplyOutput]
    market: str
