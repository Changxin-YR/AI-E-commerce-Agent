from datetime import datetime

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, defer

from app.models.analytics import AnalysisSource, AnalysisTodo, SavedAnalysis
from app.models.imports import ImportBatch, ImportRow, OrderLine, Product

OrderEvidence = tuple[OrderLine, ImportRow, ImportBatch]
ProductEvidence = tuple[Product, ImportRow, ImportBatch]


class AnalyticsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def orders(
        self, owner_id: int, shop_id: int, start: datetime, end: datetime, data_identity: str
    ) -> list[OrderEvidence]:
        rows = self.session.execute(
            select(OrderLine, ImportRow, ImportBatch)
            .join(ImportRow, OrderLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.status == "committed",
                ImportBatch.data_identity == data_identity,
                OrderLine.shop_id == shop_id,
                OrderLine.ordered_at >= start,
                OrderLine.ordered_at < end,
            )
            .order_by(OrderLine.order_id, OrderLine.line_id)
            .limit(10001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(order, row, batch) for order, row, batch in rows]

    def products(self, owner_id: int, shop_id: int, skus: set[str]) -> list[ProductEvidence]:
        rows = self.session.execute(
            select(Product, ImportRow, ImportBatch)
            .join(ImportRow, Product.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.status == "committed",
                Product.shop_id == shop_id,
                Product.sku.in_(skus),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(product, row, batch) for product, row, batch in rows]

    def source(
        self, owner_id: int, shop_id: int, row_id: int
    ) -> tuple[ImportRow, ImportBatch] | None:
        row = self.session.execute(
            select(ImportRow, ImportBatch)
            .join(ImportBatch)
            .where(
                ImportRow.id == row_id,
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.status.in_(["committed", "revoked"]),
            )
            .with_for_update()
        ).first()
        return (row[0], row[1]) if row else None

    def saved(self, owner_id: int, shop_id: int) -> list[SavedAnalysis]:
        return list(
            self.session.scalars(
                select(SavedAnalysis)
                .where(SavedAnalysis.owner_id == owner_id, SavedAnalysis.shop_id == shop_id)
                .order_by(SavedAnalysis.id.desc())
                .options(defer(SavedAnalysis.snapshot))
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def find_saved(self, owner_id: int, shop_id: int, analysis_id: int) -> SavedAnalysis | None:
        return self.session.scalar(
            select(SavedAnalysis)
            .where(
                SavedAnalysis.owner_id == owner_id,
                SavedAnalysis.shop_id == shop_id,
                SavedAnalysis.id == analysis_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_key(self, owner_id: int, key: str) -> SavedAnalysis | None:
        return self.session.scalar(
            select(SavedAnalysis)
            .where(SavedAnalysis.owner_id == owner_id, SavedAnalysis.request_key == key)
            .with_for_update()
        )

    def todo(self, owner_id: int, analysis_id: int) -> AnalysisTodo | None:
        return self.session.scalar(
            select(AnalysisTodo)
            .join(SavedAnalysis)
            .where(SavedAnalysis.owner_id == owner_id, SavedAnalysis.id == analysis_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def add(self, analysis: SavedAnalysis, batches: set[int]) -> None:
        self.session.add(analysis)
        self.session.flush()
        self.session.add_all(
            [AnalysisSource(analysis_id=analysis.id, batch_id=batch_id) for batch_id in batches]
        )

    def add_todo(self, todo: AnalysisTodo) -> None:
        self.session.add(todo)
        self.session.flush()

    def invalidate(self, owner_id: int, shop_id: int) -> None:
        analyses = select(SavedAnalysis.id).where(
            SavedAnalysis.owner_id == owner_id,
            SavedAnalysis.shop_id == shop_id,
            SavedAnalysis.status != "cleared",
        )
        self.session.execute(
            update(AnalysisTodo)
            .where(AnalysisTodo.analysis_id.in_(analyses))
            .values(status="stale")
        )
        self.session.execute(
            update(SavedAnalysis)
            .where(
                SavedAnalysis.owner_id == owner_id,
                SavedAnalysis.shop_id == shop_id,
                SavedAnalysis.status != "cleared",
            )
            .values(status="stale")
        )

    def purge_batch(self, owner_id: int, shop_id: int, batch_id: int) -> None:
        # Materialize IDs before deleting dependencies; keep only content-free history.
        ids = list(
            self.session.scalars(
                select(SavedAnalysis.id)
                .join(AnalysisSource)
                .where(
                    SavedAnalysis.owner_id == owner_id,
                    SavedAnalysis.shop_id == shop_id,
                    AnalysisSource.batch_id == batch_id,
                )
                .with_for_update()
            )
        )
        if not ids:
            return
        self.session.execute(
            update(AnalysisTodo)
            .where(AnalysisTodo.analysis_id.in_(ids))
            .values(status="cleared", title="来源已清除")
        )
        self.session.execute(
            update(SavedAnalysis)
            .where(SavedAnalysis.id.in_(ids))
            .values(status="cleared", snapshot=None)
        )
        self.session.execute(delete(AnalysisSource).where(AnalysisSource.analysis_id.in_(ids)))
