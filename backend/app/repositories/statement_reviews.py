from datetime import datetime
from typing import Any

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import InstrumentedAttribute, Session

from app.core.errors import BusinessError
from app.models.expenses import Expense, ExpenseSource
from app.models.statement_reviews import (
    StatementReview,
    StatementReviewExpense,
    StatementReviewRevision,
    StatementReviewRule,
    StatementReviewSource,
)


class StatementReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, owner: int, shop: int, review: int) -> StatementReview | None:
        return self.session.scalar(
            select(StatementReview)
            .where(
                StatementReview.owner_id == owner,
                StatementReview.shop_id == shop,
                StatementReview.id == review,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def revision(self, review: StatementReview, version: int) -> StatementReviewRevision | None:
        return self.session.scalar(
            select(StatementReviewRevision)
            .where(
                StatementReviewRevision.owner_id == review.owner_id,
                StatementReviewRevision.review_id == review.id,
                StatementReviewRevision.version == version,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def history(
        self, review: StatementReview
    ) -> list[tuple[int, str, datetime, dict[str, Any] | None]]:
        rows = self.session.execute(
            select(
                StatementReviewRevision.version,
                StatementReviewRevision.action,
                StatementReviewRevision.created_at,
                StatementReviewRevision.snapshot["conclusion"],
            )
            .where(
                StatementReviewRevision.owner_id == review.owner_id,
                StatementReviewRevision.review_id == review.id,
            )
            .order_by(StatementReviewRevision.version.desc())
            .with_for_update()
        )
        return [(v, a, t, c) for v, a, t, c in rows]

    def by_request(self, owner: int, request: str) -> StatementReviewRevision | None:
        return self.session.scalar(
            select(StatementReviewRevision)
            .where(
                StatementReviewRevision.owner_id == owner,
                StatementReviewRevision.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> list[StatementReview]:
        query = select(StatementReview).where(
            StatementReview.owner_id == owner,
            StatementReview.shop_id == shop,
            StatementReview.data_identity == identity,
            StatementReview.channel == channel,
        )
        if before is not None:
            query = query.where(StatementReview.id < before)
        return list(
            self.session.scalars(
                query.order_by(StatementReview.id.desc())
                .limit(21)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, review: StatementReview) -> None:
        self.session.add(review)
        self.session.flush()

    def revise(self, revision: StatementReviewRevision) -> None:
        self.session.add(revision)
        self.session.flush()

    def dependencies(
        self, review: StatementReview, batches: set[int], expenses: set[int], rules: set[int]
    ) -> None:
        if expenses:
            batches |= set(
                self.session.scalars(
                    select(ExpenseSource.batch_id)
                    .join(
                        Expense,
                        ExpenseSource.expense_id == Expense.id,
                    )
                    .where(
                        Expense.owner_id == review.owner_id,
                        Expense.shop_id == review.shop_id,
                        Expense.id.in_(expenses),
                    )
                    .with_for_update()
                )
            )
        total = 0
        for model, column, values in (
            (StatementReviewSource, StatementReviewSource.batch_id, batches),
            (StatementReviewExpense, StatementReviewExpense.expense_id, expenses),
            (StatementReviewRule, StatementReviewRule.rule_id, rules),
        ):
            previous = set(
                self.session.scalars(
                    select(column).where(model.review_id == review.id).with_for_update()
                )
            )
            total += len(previous | values)
            if total > 10000:
                raise BusinessError(
                    "dependency_limit", "历史依赖超过 10000 项，请新建核对存档。", 422
                )
            for value in values - previous:
                self.session.add(model(**{"review_id": review.id, column.key: value}))
        self.session.flush()

    def invalidate(
        self, owner: int, shop: int, identity: str | None = None, channel: str | None = None
    ) -> None:
        query = select(StatementReview).where(
            StatementReview.owner_id == owner,
            StatementReview.shop_id == shop,
            StatementReview.status == "active",
        )
        if identity is not None:
            query = query.where(
                StatementReview.data_identity == identity, StatementReview.channel == channel
            )
        for review in self.session.scalars(
            query.with_for_update().execution_options(populate_existing=True)
        ):
            review.status = "stale"
            review.version += 1

    def clear(self, review: StatementReview) -> None:
        self.session.execute(
            update(StatementReviewRevision)
            .where(
                StatementReviewRevision.owner_id == review.owner_id,
                StatementReviewRevision.review_id == review.id,
            )
            .values(snapshot=None)
        )
        review.status = "cleared"
        review.version += 1
        self.session.execute(
            delete(StatementReviewSource).where(StatementReviewSource.review_id == review.id)
        )
        self.session.execute(
            delete(StatementReviewExpense).where(StatementReviewExpense.review_id == review.id)
        )
        self.session.execute(
            delete(StatementReviewRule).where(StatementReviewRule.review_id == review.id)
        )

    def purge(self, owner: int, shop: int, kind: str, resource: int) -> None:
        models: dict[
            str,
            tuple[
                type[StatementReviewSource]
                | type[StatementReviewExpense]
                | type[StatementReviewRule],
                InstrumentedAttribute[int],
            ],
        ] = {
            "batch": (StatementReviewSource, StatementReviewSource.batch_id),
            "expense": (StatementReviewExpense, StatementReviewExpense.expense_id),
            "rule": (StatementReviewRule, StatementReviewRule.rule_id),
        }
        model, column = models[kind]
        dependency = exists(
            select(model.review_id).where(model.review_id == StatementReview.id, column == resource)
        )
        reviews = list(
            self.session.scalars(
                select(StatementReview)
                .where(
                    StatementReview.owner_id == owner,
                    StatementReview.shop_id == shop,
                    StatementReview.status != "cleared",
                    dependency,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        for review in reviews:
            self.clear(review)
