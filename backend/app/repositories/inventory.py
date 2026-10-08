from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow, InventorySnapshot
from app.schemas.inventory import InventoryQuery

InventoryEvidence = tuple[InventorySnapshot, ImportRow, ImportBatch]


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def snapshots(
        self, owner_id: int, shop_id: int, scope: InventoryQuery
    ) -> list[InventoryEvidence]:
        query = (
            select(InventorySnapshot, ImportRow, ImportBatch)
            .join(ImportRow, InventorySnapshot.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                InventorySnapshot.shop_id == shop_id,
                InventorySnapshot.channel == scope.channel,
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.data_identity == scope.data_identity,
                ImportBatch.status == "committed",
            )
        )
        if scope.search:
            query = query.where(InventorySnapshot.sku.contains(scope.search, autoescape=True))
        rows = self.session.execute(
            query.order_by(InventorySnapshot.sku, InventorySnapshot.id)
            .offset(scope.offset)
            .limit(51)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(item, row, batch) for item, row, batch in rows]
