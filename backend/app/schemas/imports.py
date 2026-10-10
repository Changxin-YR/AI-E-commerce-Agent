from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, field_validator, model_validator

from app.schemas.common import Currency, InputModel, OutputModel, Timezone

ImportKind = Literal["products", "orders", "messages", "inventory", "statements"]
DataIdentity = Literal["user_import", "synthetic"]
SourceChannel = Literal["generic", "shopify", "amazon", "other"]
Money = Annotated[Decimal, Field(ge=0, max_digits=18, decimal_places=4)]
Identifier = Annotated[str, Field(min_length=1, max_length=120)]
OrderStatus = Literal["paid", "pending", "cancelled", "refunded", "partially_refunded", "test"]


class ProductData(InputModel):
    sku: Identifier
    name: Annotated[str, Field(min_length=1, max_length=240)]
    facts: Annotated[str, Field(max_length=2000)] = ""
    price: Money | None = None
    currency: Currency | None = None
    unit_cost: Money | None = None
    cost_currency: Currency | None = None


class OrderData(InputModel):
    order_id: Identifier
    line_id: Identifier
    sku: Identifier
    quantity: Annotated[int, Field(ge=1, le=1000000)]
    unit_price: Money
    currency: Currency
    ordered_at: datetime
    status: OrderStatus
    discount: Money | None = None
    refund: Money | None = None
    fulfillment_status: Literal["unfulfilled", "partial", "fulfilled", "unknown"] = "unknown"


class MessageData(InputModel):
    message_id: Identifier
    sent_at: datetime
    body: Annotated[str, Field(min_length=1, max_length=2000)]
    language: Literal["en", "zh", "und"] = "und"
    order_id: Annotated[str, Field(max_length=120)] = ""
    reply_status: Literal["unknown", "awaiting_reply", "replied"] = "unknown"
    reply_updated_at: datetime | None = None
    reply_evidence: Annotated[str, Field(max_length=500)] = ""

    @model_validator(mode="after")
    def reply_semantics(self) -> Self:
        if self.reply_status != "unknown" and self.reply_updated_at is None:
            raise ValueError("回复状态须提供带时区的更新时间")
        if self.reply_status == "replied" and not self.reply_evidence:
            raise ValueError("已回复状态须提供来源凭据说明")
        if self.reply_updated_at is not None:
            if self.reply_updated_at.utcoffset() is None or self.sent_at.utcoffset() is None:
                raise ValueError("回复时间须有明确时区")
            if self.reply_updated_at < self.sent_at:
                raise ValueError("回复状态时间不能早于消息时间")
        return self


class InventoryData(InputModel):
    sku: Identifier
    available: Annotated[int, Field(ge=0, le=1000000000)]
    snapshot_at: datetime
    safety_threshold: Annotated[int, Field(ge=0, le=1000000000)]


class StatementData(InputModel):
    statement_id: Identifier
    line_id: Identifier
    entry_type: Literal["sale", "refund", "fee", "payout"]
    amount: Money
    currency: Currency
    occurred_at: datetime
    evidence_ref: Annotated[str, Field(max_length=120)] = ""
    fee_name: Annotated[str, Field(max_length=120)] = ""
    settlement_id: Annotated[str, Field(max_length=120)] = ""
    order_id: Annotated[str, Field(max_length=120)] = ""
    note: Annotated[str, Field(max_length=500)] = ""

    @model_validator(mode="after")
    def semantics(self) -> Self:
        if self.amount <= 0:
            raise ValueError("账单金额须为正数绝对金额，由收支类型明确含义")
        if self.occurred_at.utcoffset() is None or not 2000 <= self.occurred_at.year <= 2100:
            raise ValueError("账单发生时间须在 2000—2100 年并具有明确时区")
        if self.entry_type == "fee" and (not self.evidence_ref or not self.fee_name):
            raise ValueError("费用行须提供凭据费用行编号及原始收费项名称")
        if self.entry_type != "fee" and self.fee_name:
            raise ValueError("原始收费项名称仅用于费用行")
        return self


class UploadOptions(InputModel):
    group_id: Annotated[int, Field(ge=1)] | None = None
    group_part: Annotated[int, Field(ge=1, le=20)] | None = None
    filename: Annotated[str, Field(min_length=1, max_length=240)]
    kind: ImportKind
    source_channel: SourceChannel = "generic"
    data_identity: DataIdentity
    timezone: Timezone
    exported_at: datetime | None = None

    @field_validator("exported_at")
    @classmethod
    def aware_export(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("导出时间须包含时区偏移")
        return value


class PreviewInput(InputModel):
    version: Annotated[int, Field(ge=1)]
    mapping: dict[str, str] = Field(max_length=20)
    corrections: dict[int, dict[str, str]] = Field(default_factory=dict, max_length=2000)


class VersionInput(InputModel):
    version: Annotated[int, Field(ge=1)]


class CommitInput(VersionInput):
    allow_updates: bool = False
    reviewed_fields: list[Annotated[str, Field(max_length=40)]] = Field(
        default_factory=list, max_length=20
    )


class MappingTemplateInput(InputModel):
    name: Annotated[str, Field(min_length=1, max_length=80)]
    kind: ImportKind
    source_channel: SourceChannel
    mapping: dict[str, str] = Field(max_length=20)


class MappingTemplateOutput(MappingTemplateInput, OutputModel):
    id: int


class RowIssue(OutputModel):
    field: str
    message: str


class ParsedRow(OutputModel):
    row_number: int
    values: list[str]
    unsafe_columns: list[int] = Field(default_factory=list)


class FieldDefinition(OutputModel):
    key: str
    label: str
    data_type: str
    required: bool
    help: str
    aliases: list[str]


class MappingSuggestion(OutputModel):
    field: str
    column: str
    confidence: Literal["exact", "candidate"]


class MappingReview(OutputModel):
    field: str
    column: str
    label: str
    meaning: str


class ImportPreset(OutputModel):
    id: str
    name: str
    kind: ImportKind
    source_channel: SourceChannel
    verified_on: str
    reference_url: str
    mapping: dict[str, str]
    notes: list[str]


class RowOutput(OutputModel):
    row_number: int
    raw: dict[str, str]
    corrections: dict[str, str]
    normalized: dict[str, str | int | None]
    previous: dict[str, str | int | None] | None
    errors: list[RowIssue]
    warnings: list[str]
    action: str


class BatchSummary(OutputModel):
    group_id: int | None = None
    group_part: int | None = None
    origin: str
    id: int
    shop_id: int
    kind: str
    source_channel: str
    data_identity: str
    filename: str
    sheet_name: str
    timezone: str
    exported_at: datetime | None
    created_at: datetime
    expires_at: datetime
    committed_at: datetime | None
    status: str
    version: int
    total_rows: int
    valid_rows: int
    error_rows: int
    new_rows: int
    updated_rows: int
    unchanged_rows: int
    currencies: list[str]
    coverage_start: str | None
    coverage_end: str | None


class BatchOutput(BatchSummary):
    headers: list[str]
    examples: dict[str, str]
    mapping: dict[str, str]
    suggestions: list[MappingSuggestion]
    suggested_kind: ImportKind
    errors: list[str]
    rows: list[RowOutput]
    required_reviews: list[MappingReview] = Field(default_factory=list)
    duplicate_rows: int = 0
    presets: list[ImportPreset] = Field(default_factory=list)


class CatalogOutput(OutputModel):
    products: list[FieldDefinition]
    orders: list[FieldDefinition]
    messages: list[FieldDefinition]
    inventory: list[FieldDefinition]
    statements: list[FieldDefinition]
    max_bytes: int
    max_rows: int
