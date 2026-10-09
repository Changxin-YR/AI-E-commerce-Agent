from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.schemas.analytics import SourceReference
from app.schemas.common import Currency, InputModel, OutputModel, Timezone
from app.schemas.imports import DataIdentity, Money, SourceChannel

Category = Literal["shipping", "packaging", "storage", "platform", "advertising", "tax", "other"]


class ExpenseContent(InputModel):
    label: Annotated[str, Field(min_length=1, max_length=100)]
    category: Category
    amount: Money
    currency: Currency
    occurred_at: datetime
    timezone: Timezone
    evidence_ref: Annotated[str, Field(min_length=1, max_length=120)]
    evidence_note: Annotated[str, Field(min_length=1, max_length=1000)]
    allocation: Literal["shop", "order_line"]
    order_line_id: Annotated[int | None, Field(gt=0)] = None
    expected_source_row_id: Annotated[int | None, Field(gt=0)] = None
    expected_source_revision: Annotated[int | None, Field(ge=0)] = None
    reason: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def valid_evidence(self) -> Self:
        if self.amount <= 0:
            raise ValueError("实际费用必须大于零；费用冲正请撤销或修订原记录")
        if self.occurred_at.utcoffset() is None:
            raise ValueError("发生时间必须包含明确时区偏移")
        if not 2000 <= self.occurred_at.year <= 2100:
            raise ValueError("发生年份须在 2000—2100 之间")
        local = self.occurred_at.astimezone(ZoneInfo(self.timezone))
        if local.utcoffset() != self.occurred_at.utcoffset():
            raise ValueError("发生时间偏移与所选 IANA 时区不符")
        if not 2000 <= local.year <= 2100:
            raise ValueError("发生年份须在 2000—2100 之间")
        links = (self.order_line_id, self.expected_source_row_id, self.expected_source_revision)
        if (self.allocation == "order_line" and any(v is None for v in links)) or (
            self.allocation == "shop" and any(v is not None for v in links)
        ):
            raise ValueError("订单行费用须绑定当前来源和版本；店铺费用不关联订单")
        return self


class ExpenseWrite(InputModel):
    request_id: UUID
    confirm: Literal[True]
    data_identity: DataIdentity
    channel: SourceChannel
    version: Annotated[int, Field(ge=0)] = 0
    content: ExpenseContent


class ExpenseControl(InputModel):
    request_id: UUID
    version: Annotated[int, Field(ge=1)]
    confirm: Literal[True]


class ExpenseScope(InputModel):
    data_identity: DataIdentity
    channel: SourceChannel
    start_at: datetime
    end_at: datetime
    timezone: Timezone

    @model_validator(mode="after")
    def window(self) -> Self:
        if self.start_at.utcoffset() is None or self.end_at.utcoffset() is None:
            raise ValueError("费用查询起止时间须包含时区偏移")
        if not all(2000 <= d.year <= 2101 for d in (self.start_at, self.end_at)):
            raise ValueError("费用查询年份须在 2000—2101 之间")
        duration = self.end_at.astimezone(UTC) - self.start_at.astimezone(UTC)
        if not timedelta(0) < duration <= timedelta(days=366):
            raise ValueError("查询区间须大于零且不超过 366 天，包含开始、不含结束")
        return self


class ExpenseSnapshot(OutputModel):
    content: ExpenseContent
    source: SourceReference | None = None
    order_id: str | None = None
    line_id: str | None = None
    sku: str | None = None
    order_status: str | None = None


class ExpenseHistory(OutputModel):
    version: int
    action: str
    created_at: str
    snapshot: ExpenseSnapshot | None


class ExpenseSaved(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    version: int
    status: Literal["active", "stale", "withdrawn", "cleared"]
    created_at: str
    snapshot: ExpenseSnapshot | None
    history: list[ExpenseHistory] = Field(default_factory=list)


class ExpensePage(OutputModel):
    items: list[ExpenseSaved]
    next_cursor: int | None


class ExpenseTotal(OutputModel):
    currency: str
    category: Category
    allocation: str
    amount: Decimal
    count: int


class ExpenseSummary(OutputModel):
    scope: ExpenseScope
    totals: list[ExpenseTotal]
    included_count: int
    stale_count: int
    withdrawn_count: int
    checks: list[str]


class ExpenseOrder(OutputModel):
    id: int
    order_id: str
    line_id: str
    sku: str
    currency: str
    status: str
    source: SourceReference


class ExpenseOrders(OutputModel):
    source_revision: int
    items: list[ExpenseOrder]
