from datetime import datetime

from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models.expenses import Expense, ExpenseRevision, ExpenseSource
from app.models.imports import ImportBatch, ImportRow, OrderLine
from app.repositories.analytics import OrderEvidence
from app.repositories.statement_reviews import StatementReviewRepository


class ExpenseRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def scope_revision(self, owner: int, shop: int, identity: str, channel: str) -> int:
        return (
            self.session.scalar(
                select(ExpenseRevision.id)
                .join(Expense, ExpenseRevision.expense_id == Expense.id)
                .where(
                    Expense.owner_id == owner,
                    Expense.shop_id == shop,
                    Expense.data_identity == identity,
                    Expense.channel == channel,
                    ExpenseRevision.owner_id == owner,
                )
                .order_by(ExpenseRevision.id.desc())
                .limit(1)
                .with_for_update()
            )
            or 0
        )

    def get(self, owner: int, shop: int, expense: int) -> Expense | None:
        return self.session.scalar(
            select(Expense)
            .where(Expense.owner_id == owner, Expense.shop_id == shop, Expense.id == expense)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner: int, request: str) -> ExpenseRevision | None:
        return self.session.scalar(
            select(ExpenseRevision)
            .where(ExpenseRevision.owner_id == owner, ExpenseRevision.request_id == request)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def duplicate(self, expense: Expense, key: str) -> bool:
        return (
            self.session.scalar(
                select(Expense.id)
                .where(
                    Expense.owner_id == expense.owner_id,
                    Expense.shop_id == expense.shop_id,
                    Expense.data_identity == expense.data_identity,
                    Expense.channel == expense.channel,
                    Expense.evidence_key == key,
                    Expense.id != (expense.id or 0),
                )
                .with_for_update()
            )
            is not None
        )

    def revisions(self, expense: Expense) -> list[ExpenseRevision]:
        return list(
            self.session.scalars(
                select(ExpenseRevision)
                .where(
                    ExpenseRevision.expense_id == expense.id,
                    ExpenseRevision.owner_id == expense.owner_id,
                )
                .order_by(ExpenseRevision.version.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> list[Expense]:
        statement = select(Expense).where(
            Expense.owner_id == owner,
            Expense.shop_id == shop,
            Expense.data_identity == identity,
            Expense.channel == channel,
        )
        if before is not None:
            statement = statement.where(Expense.id < before)
        return list(
            self.session.scalars(
                statement.order_by(Expense.id.desc())
                .limit(21)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def period(
        self, owner: int, shop: int, identity: str, channel: str, start: datetime, end: datetime
    ) -> list[tuple[Expense, ExpenseRevision]]:
        rows = self.session.execute(
            select(Expense, ExpenseRevision)
            .join(
                ExpenseRevision,
                (ExpenseRevision.expense_id == Expense.id)
                & (ExpenseRevision.version == Expense.content_version),
            )
            .where(
                Expense.owner_id == owner,
                Expense.shop_id == shop,
                Expense.data_identity == identity,
                Expense.channel == channel,
                Expense.status != "cleared",
                ExpenseRevision.occurred_at >= start,
                ExpenseRevision.occurred_at < end,
            )
            .limit(1001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(e, r) for e, r in rows]

    def orders(
        self,
        owner: int,
        shop: int,
        identity: str,
        channel: str,
        order_id: str | None = None,
        line: int | None = None,
    ) -> list[OrderEvidence]:
        statement = (
            select(OrderLine, ImportRow, ImportBatch)
            .join(ImportRow, OrderLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                OrderLine.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
                ImportBatch.data_identity == identity,
                ImportBatch.source_channel == channel,
            )
        )
        if order_id is not None:
            statement = statement.where(OrderLine.order_id == order_id)
        if line is not None:
            statement = statement.where(OrderLine.id == line)
        rows = self.session.execute(
            statement.order_by(OrderLine.id)
            .limit(101)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(o, r, b) for o, r, b in rows]

    def add(self, expense: Expense) -> None:
        self.session.add(expense)
        self.session.flush()

    def add_revision(self, revision: ExpenseRevision, batch: int | None = None) -> None:
        self.session.add(revision)
        if (
            batch is not None
            and self.session.get(ExpenseSource, (revision.expense_id, batch)) is None
        ):
            self.session.add(ExpenseSource(expense_id=revision.expense_id, batch_id=batch))
        self.session.flush()

    def invalidate(self, owner: int, shop: int) -> None:
        # A restored projection must not silently reactivate an old allocation confirmation.
        rows = self.session.scalars(
            select(Expense)
            .where(
                Expense.owner_id == owner,
                Expense.shop_id == shop,
                Expense.status == "active",
                Expense.allocation == "order_line",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        for expense in rows:
            expense.status = "stale"
            expense.version += 1

    def clear(self, expense: Expense) -> None:
        StatementReviewRepository(self.session).purge(
            expense.owner_id, expense.shop_id, "expense", expense.id
        )
        for revision in self.revisions(expense):
            revision.snapshot = None
            revision.amount = None
            revision.occurred_at = None
        expense.evidence_key = None
        expense.status = "cleared"
        expense.version += 1
        self.session.execute(delete(ExpenseSource).where(ExpenseSource.expense_id == expense.id))

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        dependent = exists(
            select(ExpenseSource.expense_id).where(
                ExpenseSource.expense_id == Expense.id, ExpenseSource.batch_id == batch
            )
        )
        rows = list(
            self.session.scalars(
                select(Expense)
                .where(
                    Expense.owner_id == owner,
                    Expense.shop_id == shop,
                    Expense.status != "cleared",
                    dependent,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        for expense in rows:
            self.clear(expense)
