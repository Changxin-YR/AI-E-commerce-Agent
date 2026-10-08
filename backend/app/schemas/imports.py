from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.schemas.common import Currency, InputModel, OutputModel, Timezone

ImportKind = Literal["products", "orders"]
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


class UploadOptions(InputModel):
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


class CatalogOutput(OutputModel):
    products: list[FieldDefinition]
    orders: list[FieldDefinition]
    max_bytes: int
    max_rows: int
