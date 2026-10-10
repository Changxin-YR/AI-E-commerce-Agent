from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow, OrderLine
from app.models.order_costs import OrderCostRevision
from app.repositories.analytics import OrderEvidence


class OrderCostRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def order(self, owner: int, shop: int, row_id: int) -> OrderEvidence | None:
        result = self.session.execute(
            select(OrderLine, ImportRow, ImportBatch)
            .join(ImportRow, OrderLine.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                OrderLine.shop_id == shop,
                ImportRow.id == row_id,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == "orders",
                ImportBatch.status == "committed",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        return (result[0], result[1], result[2]) if result else None

    def history(self, owner: int, shop: int, row_id: int) -> list[OrderCostRevision]:
        return list(
            self.session.scalars(
                select(OrderCostRevision)
                .where(
                    OrderCostRevision.owner_id == owner,
                    OrderCostRevision.shop_id == shop,
                    OrderCostRevision.source_row_id == row_id,
                )
                .order_by(OrderCostRevision.version.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def by_request(self, owner: int, request: str) -> OrderCostRevision | None:
        return self.session.scalar(
            select(OrderCostRevision)
            .where(OrderCostRevision.owner_id == owner, OrderCostRevision.request_id == request)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def active(self, owner: int, shop: int, row_ids: set[int]) -> dict[int, OrderCostRevision]:
        if not row_ids:
            return {}
        rows = self.session.scalars(
            select(OrderCostRevision)
            .where(
                OrderCostRevision.owner_id == owner,
                OrderCostRevision.shop_id == shop,
                OrderCostRevision.source_row_id.in_(row_ids),
                OrderCostRevision.status == "active",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return {r.source_row_id: r for r in rows if r.source_row_id is not None}

    def add(self, revision: OrderCostRevision) -> None:
        self.session.add(revision)
        self.session.flush()

    def invalidate(self, owner: int, shop: int) -> None:
        current = exists().where(
            OrderLine.shop_id == shop, OrderLine.source_row_id == OrderCostRevision.source_row_id
        )
        self.session.execute(
            update(OrderCostRevision)
            .where(
                OrderCostRevision.owner_id == owner,
                OrderCostRevision.shop_id == shop,
                OrderCostRevision.status == "active",
                ~current,
            )
            .values(status="stale")
        )

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        self.session.execute(
            update(OrderCostRevision)
            .where(
                OrderCostRevision.owner_id == owner,
                OrderCostRevision.shop_id == shop,
                OrderCostRevision.source_batch_id == batch,
            )
            .values(
                status="cleared",
                source_row_id=None,
                unit_cost=None,
                currency=None,
                evidence_ref=None,
                evidence_at=None,
                request_hash="",
            )
        )
