from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, defer

from app.models.imports import ImportBatch, ImportRow, Product
from app.models.product_quality import ProductQualityReport, ProductQualitySource
from app.repositories.analytics import ProductEvidence
from app.schemas.product_quality import QualityScope

MAX_PRODUCTS = 1000


class ProductQualityRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def products(self, owner: int, shop: int, scope: QualityScope) -> list[ProductEvidence]:
        query = (
            select(Product, ImportRow, ImportBatch)
            .join(ImportRow, Product.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                Product.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
                ImportBatch.data_identity == scope.data_identity,
            )
        )
        if scope.channel is not None:
            query = query.where(ImportBatch.source_channel == scope.channel)
        if scope.sku_prefix:
            query = query.where(Product.sku.startswith(scope.sku_prefix, autoescape=True))
        rows = self.session.execute(
            query.order_by(Product.id)
            .limit(MAX_PRODUCTS + 1)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(product, row, batch) for product, row, batch in rows]

    def by_request(self, owner: int, request: str) -> ProductQualityReport | None:
        return self.session.scalar(
            select(ProductQualityReport)
            .where(
                ProductQualityReport.owner_id == owner,
                ProductQualityReport.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def get(self, owner: int, shop: int, report_id: int) -> ProductQualityReport | None:
        return self.session.scalar(
            select(ProductQualityReport)
            .where(
                ProductQualityReport.owner_id == owner,
                ProductQualityReport.shop_id == shop,
                ProductQualityReport.id == report_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(self, owner: int, shop: int, before: int | None) -> list[ProductQualityReport]:
        query = select(ProductQualityReport).where(
            ProductQualityReport.owner_id == owner, ProductQualityReport.shop_id == shop
        )
        if before is not None:
            query = query.where(ProductQualityReport.id < before)
        return list(
            self.session.scalars(
                query.order_by(ProductQualityReport.id.desc())
                .limit(21)
                .options(defer(ProductQualityReport.snapshot))
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, report: ProductQualityReport, batches: set[int]) -> None:
        self.session.add(report)
        self.session.flush()
        self.session.add_all(
            [ProductQualitySource(report_id=report.id, batch_id=b) for b in sorted(batches)]
        )

    def invalidate(self, owner: int, shop: int) -> None:
        self.session.execute(
            update(ProductQualityReport)
            .where(
                ProductQualityReport.owner_id == owner,
                ProductQualityReport.shop_id == shop,
                ProductQualityReport.status == "current",
            )
            .values(status="stale")
        )

    def clear(self, report: ProductQualityReport) -> None:
        report.snapshot = None
        report.status = "cleared"
        report.scope = {**report.scope, "sku_prefix": ""}
        self.session.execute(
            delete(ProductQualitySource).where(ProductQualitySource.report_id == report.id)
        )

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        reports = self.session.scalars(
            select(ProductQualityReport)
            .join(ProductQualitySource)
            .where(
                ProductQualityReport.owner_id == owner,
                ProductQualityReport.shop_id == shop,
                ProductQualitySource.batch_id == batch,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).all()
        for report in reports:
            self.clear(report)
