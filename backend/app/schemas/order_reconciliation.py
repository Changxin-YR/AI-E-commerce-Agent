from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.schemas.analytics import SourceReference
from app.schemas.common import OutputModel
from app.schemas.expenses import ExpenseScope
from app.schemas.imports import OrderData
from app.schemas.statements import StatementItem


class OrderReconciliationScope(ExpenseScope):
    sale_basis: Literal["unknown", "merchandise_after_discount"] = "unknown"
    basis_note: Annotated[str, Field(max_length=500)] = ""

    @model_validator(mode="after")
    def declared_basis(self) -> Self:
        if self.sale_basis != "unknown" and not self.basis_note:
            raise ValueError("选择可比销售口径时须填写两侧原文件的金额组成依据")
        return self


class ReconciliationOrder(OrderData, OutputModel):
    id: int
    in_window: bool
    source: SourceReference


class ReconciliationStatement(StatementItem):
    in_window: bool


class OrderComparison(OutputModel):
    order_id: str
    entry_type: Literal["sale", "refund"]
    statement_ids: list[int]
    order_line_ids: list[int]
    status: Literal["matched", "amount_difference", "pending"]
    reasons: list[str]
    currency: str | None = None
    order_amount: Decimal | None = None
    difference: Decimal | None = None


class OrderReconciliation(OutputModel):
    scope: OrderReconciliationScope
    source_revision: int
    calculated_at: str
    coverage: Literal["unknown"] = "unknown"
    orders: list[ReconciliationOrder]
    statements: list[ReconciliationStatement]
    comparisons: list[OrderComparison]
    checks: list[str]
