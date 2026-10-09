from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow, StatementLine

StatementEvidence = tuple[StatementLine, ImportRow, ImportBatch]


class StatementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def by_statement(
        self, owner: int, shop: int, identity: str, channel: str, statement_id: str
    ) -> list[StatementEvidence]:
        rows = self.session.execute(
            select(StatementLine, ImportRow, ImportBatch)
            .join(ImportRow, StatementLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                StatementLine.shop_id == shop,
                StatementLine.data_identity == identity,
                StatementLine.channel == channel,
                StatementLine.statement_id == statement_id,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == "statements",
                ImportBatch.status == "committed",
                ImportBatch.data_identity == identity,
                ImportBatch.source_channel == channel,
            )
            .order_by(StatementLine.occurred_at, StatementLine.id)
            .limit(1001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(line, row, batch) for line, row, batch in rows]

    def period(
        self, owner: int, shop: int, identity: str, channel: str, start: datetime, end: datetime
    ) -> list[StatementEvidence]:
        rows = self.session.execute(
            select(StatementLine, ImportRow, ImportBatch)
            .join(ImportRow, StatementLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                StatementLine.shop_id == shop,
                StatementLine.data_identity == identity,
                StatementLine.channel == channel,
                StatementLine.occurred_at >= start,
                StatementLine.occurred_at < end,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == "statements",
                ImportBatch.status == "committed",
                ImportBatch.data_identity == identity,
                ImportBatch.source_channel == channel,
            )
            .order_by(StatementLine.occurred_at, StatementLine.id)
            .limit(1001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(line, row, batch) for line, row, batch in rows]
