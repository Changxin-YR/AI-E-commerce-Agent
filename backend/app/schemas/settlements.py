from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from app.schemas.common import Currency, InputModel, OutputModel, Timezone
from app.schemas.expenses import ExpenseScope
from app.schemas.imports import DataIdentity, Money, SourceChannel
from app.schemas.statements import StatementItem, StatementTotal


class ManualReceipt(InputModel):
    payout_ref: Annotated[str, Field(min_length=1, max_length=120)]
    receipt_ref: Annotated[str, Field(min_length=1, max_length=120)]
    amount: Money
    currency: Currency
    received_at: datetime
    timezone: Timezone
    note: Annotated[str, Field(min_length=1, max_length=500)]

    @model_validator(mode="after")
    def valid_receipt(self) -> Self:
        if self.amount <= 0:
            raise ValueError("到账登记金额须大于零，冲正请修订或撤销原登记")
        if self.received_at.utcoffset() is None:
            raise ValueError("到账时间须包含明确偏移")
        local = self.received_at.astimezone(ZoneInfo(self.timezone))
        if local.utcoffset() != self.received_at.utcoffset():
            raise ValueError("到账时间偏移与所选 IANA 时区不符")
        if not all(2000 <= d.year <= 2100 for d in (local, self.received_at.astimezone(UTC))):
            raise ValueError("到账年份须在 2000—2100 之间")
        return self


class SettlementContent(InputModel):
    statement_id: Annotated[str, Field(min_length=1, max_length=120)]
    note: Annotated[str, Field(min_length=1, max_length=1000)]
    receipts: Annotated[list[ManualReceipt], Field(max_length=50)] = Field(default_factory=list)


class SettlementDraft(InputModel):
    scope: ExpenseScope
    settlement_id: Annotated[int | None, Field(gt=0)] = None
    version: Annotated[int, Field(ge=0)] = 0
    content: SettlementContent


class PayoutComparison(OutputModel):
    payout_ref: str
    status: Literal[
        "matched",
        "amount_difference",
        "statement_only",
        "receipt_only",
        "ambiguous",
        "currency_mismatch",
        "missing_reference",
    ]
    statement_ids: list[int]
    receipt_indexes: list[int]
    difference: Decimal | None


class SettlementSnapshot(OutputModel):
    scope: ExpenseScope
    content: SettlementContent
    source_revision: int
    calculated_at: str
    statements: list[StatementItem]
    totals: list[StatementTotal]
    comparisons: list[PayoutComparison]
    outside_cycle_ids: list[int]
    coverage_status: Literal["unknown"] = "unknown"
    balance_status: Literal["unknown"] = "unknown"
    bank_status: Literal["unverified"] = "unverified"
    checks: list[str]


class SettlementPreview(OutputModel):
    preview_hash: str
    snapshot: SettlementSnapshot


class SettlementWrite(SettlementDraft):
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    request_id: UUID
    confirm: Literal[True]


class SettlementHistory(OutputModel):
    version: int
    action: str
    has_content: bool
    created_at: str


class SettlementSaved(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    status: Literal["active", "stale", "withdrawn", "cleared"]
    version: int
    content_version: int
    created_at: str
    snapshot: SettlementSnapshot | None
    history: list[SettlementHistory] = Field(default_factory=list)


class SettlementPage(OutputModel):
    items: list[SettlementSaved]
    next_cursor: int | None


class SettlementCurrent(OutputModel):
    record: SettlementSaved
    preview: SettlementPreview | None
