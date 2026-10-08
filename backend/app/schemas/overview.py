from datetime import date, timedelta
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import Field, StrictBool, ValidationInfo, field_validator, model_validator

from app.schemas.analytics import AnalysisResult, SourceReference
from app.schemas.common import Currency, InputModel, OutputModel, Timezone
from app.schemas.imports import DataIdentity
from app.schemas.inventory import InventoryItem


class OverviewScope(InputModel):
    shop_ids: Annotated[list[Annotated[int, Field(gt=0)]], Field(min_length=1, max_length=20)]
    start_date: date
    end_date: date
    timezone: Timezone
    data_identity: DataIdentity
    comparison_start: date | None = None
    comparison_end: date | None = None
    currencies: Annotated[list[Currency], Field(max_length=9)] = []
    max_age_hours: Annotated[int, Field(ge=1, le=720)] = 24
    min_quantity: Annotated[int, Field(ge=1, le=1000000)] = 1
    max_margin_percent: Annotated[Decimal, Field(ge=-1000, le=100, decimal_places=2)] = Decimal(20)

    @field_validator("start_date", "end_date", "comparison_start", "comparison_end")
    @classmethod
    def supported_date(cls, value: date | None, info: ValidationInfo) -> date | None:
        earliest = (
            date(1968, 1, 1)
            if info.field_name in {"comparison_start", "comparison_end"}
            else date(1970, 1, 1)
        )
        if value is not None and not earliest <= value <= date(2100, 12, 31):
            raise ValueError("本期日期须在 1970—2100 年，对比日期须在 1968—2100 年之间")
        return value

    @model_validator(mode="after")
    def windows(self) -> Self:
        duration = self.end_date - self.start_date
        if not timedelta(0) < duration <= timedelta(days=366):
            raise ValueError("日期窗口须为 1—366 天，结束日不计入")
        if (self.comparison_start is None) != (self.comparison_end is None):
            raise ValueError("自选对比须同时提供起止日期")
        if self.comparison_start is None:
            self.comparison_start = self.start_date - duration
            self.comparison_end = self.start_date
        assert self.comparison_end is not None and self.comparison_start is not None
        if not timedelta(0) < self.comparison_end - self.comparison_start <= timedelta(days=366):
            raise ValueError("对比窗口须为 1—366 天")
        self.shop_ids = sorted(set(self.shop_ids))
        self.currencies = sorted(set(self.currencies))
        return self


class OverviewSave(InputModel):
    request_id: UUID
    scope: OverviewScope
    expected_revisions: dict[int, int]


class OverviewClear(InputModel):
    confirm: StrictBool

    @field_validator("confirm")
    @classmethod
    def confirmed(cls, value: bool) -> bool:
        if not value:
            raise ValueError("请明确确认清除摘要正文")
        return value


class PeriodMetrics(OutputModel):
    analysis: AnalysisResult
    orders: int | None
    refunds: Decimal | None
    known_refunds: Decimal
    refund_known_lines: int
    pending_orders: int | None
    unknown_fulfillment_lines: int
    pending_sources: list[SourceReference]
    top_skus: list[str]


class CurrencyGroup(OutputModel):
    currency: str
    current: PeriodMetrics
    comparison: PeriodMetrics
    sales_change: Decimal | None
    sales_change_percent: Decimal | None


class MessageEvidence(OutputModel):
    message_id: str
    channel: str
    sent_at: str
    source: SourceReference


class TaskLink(OutputModel):
    id: int
    kind: str
    status: str
    source_status: str


class ShopOverview(OutputModel):
    shop_id: int
    shop_name: str
    platform: str
    market: str
    source_revision: int
    currencies: list[CurrencyGroup]
    inventory: list[InventoryItem]
    inventory_low: int | None
    inventory_unknown: int
    messages: list[MessageEvidence]
    message_count: int | None
    tasks: list[TaskLink]
    tasks_has_more: bool
    sources: list[SourceReference]


class CurrencyTotal(OutputModel):
    currency: str
    shop_ids: list[int]
    sales: Decimal | None
    known_sales: Decimal
    comparison_sales: Decimal | None
    sales_change: Decimal | None
    sales_change_percent: Decimal | None
    gross_profit: Decimal | None
    known_gross_profit: Decimal
    refunds: Decimal | None
    known_refunds: Decimal
    observed_orders: int
    warnings: list[str]


class OverviewResult(OutputModel):
    scope: OverviewScope
    engine: Literal["local_rules"] = "local_rules"
    calculated_at: str
    valid_until: str | None
    shops: list[ShopOverview]
    totals: list[CurrencyTotal]
    summary: list[str]
    limitations: list[str]


class OverviewSaved(OutputModel):
    id: int
    status: str
    created_at: str
    scope: OverviewScope
    snapshot: OverviewResult | None


class OverviewPage(OutputModel):
    items: list[OverviewSaved]
    next_cursor: int | None
