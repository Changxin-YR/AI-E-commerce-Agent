from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.schemas.analytics import SourceReference
from app.schemas.common import InputModel, OutputModel
from app.schemas.expenses import Category, ExpenseScope
from app.schemas.imports import DataIdentity, SourceChannel


class FeeRuleContent(InputModel):
    fee_name: Annotated[str, Field(min_length=1, max_length=120)]
    category: Category
    reason: Annotated[str, Field(min_length=1, max_length=500)]


class FeeRuleDraft(InputModel):
    scope: ExpenseScope
    rule_id: Annotated[int | None, Field(gt=0)] = None
    version: Annotated[int, Field(ge=0)] = 0
    content: FeeRuleContent


class FeeRuleWrite(FeeRuleDraft):
    preview_hash: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    request_id: UUID
    confirm: Literal[True]


class FeeRuleHistory(OutputModel):
    version: int
    action: str
    content: FeeRuleContent | None
    created_at: str


class FeeRuleSaved(OutputModel):
    id: int
    shop_id: int
    data_identity: DataIdentity
    channel: SourceChannel
    status: Literal["active", "withdrawn", "cleared"]
    version: int
    content: FeeRuleContent | None
    created_at: str
    history: list[FeeRuleHistory] = Field(default_factory=list)


class FeeRulePage(OutputModel):
    items: list[FeeRuleSaved]
    next_cursor: int | None


class FeeMapping(OutputModel):
    statement_id: int
    status: Literal["mapped", "unmapped", "ambiguous", "currency_mismatch", "category_conflict"]
    category: Category | None = None
    rule_id: int | None = None
    rule_version: int | None = None


class FeeRuleChange(OutputModel):
    statement_id: int
    fee_name: str
    source: SourceReference
    before: FeeMapping
    after: FeeMapping


class FeeRulePreview(OutputModel):
    preview_hash: str
    source_revision: int
    calculated_at: str
    previous: FeeRuleContent | None
    proposed: FeeRuleContent
    changes: list[FeeRuleChange]
    statement_count: int
    scope: ExpenseScope
