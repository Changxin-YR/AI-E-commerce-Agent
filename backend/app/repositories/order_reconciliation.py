from datetime import UTC

from sqlalchemy import cast, select
from sqlalchemy.dialects.mysql import BINARY
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow, OrderLine, StatementLine
from app.repositories.analytics import OrderEvidence
from app.repositories.statements import StatementEvidence
from app.schemas.order_reconciliation import OrderReconciliationScope


class OrderReconciliationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def orders(
        self, owner: int, shop: int, scope: OrderReconciliationScope, keys: set[str] | None = None
    ) -> list[OrderEvidence]:
        query = (
            select(OrderLine, ImportRow, ImportBatch)
            .join(ImportRow, OrderLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                OrderLine.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == "orders",
                ImportBatch.status == "committed",
                ImportBatch.data_identity == scope.data_identity,
                ImportBatch.source_channel == scope.channel,
            )
        )
        if keys is None:
            query = query.where(
                OrderLine.ordered_at >= scope.start_at.astimezone(UTC).replace(tzinfo=None),
                OrderLine.ordered_at < scope.end_at.astimezone(UTC).replace(tzinfo=None),
            )
        else:
            # Binary equality preserves case, fullwidth characters and trailing spaces.
            query = query.where(cast(OrderLine.order_id, BINARY).in_([k.encode() for k in keys]))
        rows = self.session.execute(
            query.order_by(OrderLine.id)
            .limit(1001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(line, row, batch) for line, row, batch in rows]

    def statements(
        self, owner: int, shop: int, scope: OrderReconciliationScope, keys: set[str] | None = None
    ) -> list[StatementEvidence]:
        query = (
            select(StatementLine, ImportRow, ImportBatch)
            .join(ImportRow, StatementLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                StatementLine.shop_id == shop,
                StatementLine.data_identity == scope.data_identity,
                StatementLine.channel == scope.channel,
                StatementLine.entry_type.in_(["sale", "refund"]),
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == "statements",
                ImportBatch.status == "committed",
                ImportBatch.data_identity == scope.data_identity,
                ImportBatch.source_channel == scope.channel,
            )
        )
        if keys is None:
            query = query.where(
                StatementLine.occurred_at >= scope.start_at.astimezone(UTC).replace(tzinfo=None),
                StatementLine.occurred_at < scope.end_at.astimezone(UTC).replace(tzinfo=None),
            )
        else:
            query = query.where(
                cast(StatementLine.order_id, BINARY).in_([k.encode() for k in keys])
            )
        rows = self.session.execute(
            query.order_by(StatementLine.id)
            .limit(1001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(line, row, batch) for line, row, batch in rows]
