from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, field_validator, model_validator

from app.schemas.common import Currency, InputModel, OutputModel


class CostContent(InputModel):
    unit_cost: Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
    currency: Currency
    evidence_ref: Annotated[str, Field(min_length=1, max_length=500)]
    evidence_at: datetime
    confirmed: StrictBool

    @field_validator("evidence_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("凭据时间须包含时区偏移")
        if value.year < 2000:
            raise ValueError("凭据时间须不早于 2000 年")
        return value.astimezone(UTC)

    @field_validator("confirmed")
    @classmethod
    def confirmation(cls, value: bool) -> bool:
        if not value:
            raise ValueError("请确认这是卖家提供的订单行历史单位采购成本依据")
        return value


class CostWrite(InputModel):
    request_id: UUID
    expected_version: Annotated[int, Field(ge=0)]
    expected_revision: Annotated[int, Field(ge=0)]
    action: Literal["upsert", "revoke"] = "upsert"
    content: CostContent | None = None

    @model_validator(mode="after")
    def content_for_action(self) -> Self:
        if (self.action == "upsert") != (self.content is not None):
            raise ValueError("录入须提供完整凭据；撤销不接受成本内容")
        return self


class CostVersion(OutputModel):
    id: int
    version: int
    action: str
    status: str
    unit_cost: Decimal | None
    currency: str | None
    evidence_ref: str | None
    evidence_at: str | None
    recorded_at: str


class CostHistory(OutputModel):
    source_row_id: int
    source_batch_id: int
    source_current: bool
    source_revision: int
    order_id: str
    line_id: str
    sku: str
    currency: str
    channel: str
    data_identity: str
    version: int
    history: list[CostVersion]
