from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.schemas.common import Currency, InputModel, OutputModel, Timezone
from app.schemas.imports import DataIdentity

Intent = Literal["sales", "low_margin", "summary"]


class AnalysisInput(InputModel):
    start_at: datetime
    end_at: datetime
    timezone: Timezone
    currency: Currency
    data_identity: DataIdentity
    intent: Intent = "summary"
    min_quantity: Annotated[int, Field(ge=1, le=1000000)] = 1
    max_margin_percent: Annotated[Decimal, Field(ge=-1000, le=100, decimal_places=2)] = Decimal(20)

    @field_validator("start_at", "end_at")
    @classmethod
    def aware_time(cls, value: datetime) -> datetime:
        if value.utcoffset() is None:
            raise ValueError("分析起止时间必须包含时区偏移")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def ordered_window(self) -> Self:
        if not timedelta(0) < self.end_at - self.start_at <= timedelta(days=366):
            raise ValueError("时间窗须为正且不超过 366 天；结束时间不包含在范围内")
        return self


class QuestionInput(InputModel):
    scope: AnalysisInput
    question: Annotated[str, Field(min_length=1, max_length=200)]


class SaveInput(InputModel):
    scope: AnalysisInput
    expected_revision: Annotated[int, Field(ge=0)]


class SourceReference(OutputModel):
    origin: str = "file_import"
    batch_id: int
    row_id: int
    row_number: int
    filename: str
    sheet_name: str
    exported_at: str | None
    imported_at: str
    data_identity: str


class LineResult(OutputModel):
    order_id: str
    line_id: str
    sku: str
    status: str
    ordered_at: str
    currency: str
    quantity: int
    included: bool
    unit_price: Decimal
    discount: Decimal | None
    refund: Decimal | None
    sales: Decimal | None
    cost: Decimal | None
    gross_profit: Decimal | None
    gaps: list[str]
    source: SourceReference
    cost_source: SourceReference | None


class MetricSummary(OutputModel):
    sku: str | None = None
    line_count: int
    purchased_quantity: int
    sales: Decimal | None
    known_sales_subtotal: Decimal
    sales_known_lines: int
    cost: Decimal | None
    known_cost_subtotal: Decimal
    cost_known_lines: int
    gross_profit: Decimal | None
    known_gross_subtotal: Decimal
    gross_known_lines: int
    margin_percent: Decimal | None


class AnalysisResult(OutputModel):
    scope: AnalysisInput
    source_revision: int
    calculated_at: str
    engine: Literal["local_rules"] = "local_rules"
    formula: str
    cost_basis: str
    fee_gaps: list[str]
    warnings: list[str]
    summary: MetricSummary
    skus: list[MetricSummary]
    lines: list[LineResult]
    ranking_available: bool
    answer: str
    candidates: list[str]


class TodoOutput(OutputModel):
    id: int
    title: str
    status: str
    version: int


class TodoAction(InputModel):
    expected_version: Annotated[int, Field(ge=1)]
    action: Literal["complete", "reopen"]


class SavedOutput(OutputModel):
    id: int
    shop_id: int
    source_revision: int
    status: str
    created_at: str
    scope: AnalysisInput
    snapshot: AnalysisResult | None
    todo: TodoOutput | None


class SourceOutput(OutputModel):
    reference: SourceReference
    batch_status: str
    raw: dict[str, Any]
    corrections: dict[str, Any]
    normalized: dict[str, Any]
