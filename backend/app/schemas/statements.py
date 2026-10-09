from decimal import Decimal
from typing import Literal

from app.schemas.analytics import SourceReference
from app.schemas.common import OutputModel
from app.schemas.expenses import ExpenseScope
from app.schemas.fee_rules import FeeMapping
from app.schemas.imports import StatementData


class StatementItem(StatementData, OutputModel):
    id: int
    source: SourceReference


class StatementTotal(OutputModel):
    currency: str
    entry_type: str
    amount: Decimal
    count: int


class MatchedExpense(OutputModel):
    id: int
    version: int
    label: str
    category: str
    allocation: str
    evidence_ref: str
    amount: Decimal
    currency: str
    occurred_at: str


class FeeComparison(OutputModel):
    evidence_ref: str
    status: Literal[
        "matched",
        "amount_difference",
        "statement_only",
        "expense_only",
        "ambiguous",
        "currency_mismatch",
    ]
    statement_ids: list[int]
    expenses: list[MatchedExpense]
    difference: Decimal | None


class StatementReconciliation(OutputModel):
    scope: ExpenseScope
    source_revision: int
    rule_revision: int
    calculated_at: str
    statements: list[StatementItem]
    totals: list[StatementTotal]
    comparisons: list[FeeComparison]
    mappings: list[FeeMapping]
    stale_expenses: int
    withdrawn_expenses: int
    checks: list[str]
