from sqlalchemy import JSON, delete, exists, func, literal, select, update
from sqlalchemy.orm import Session

from app.models.imports import ImportBatch, ImportRow, Product
from app.models.listings import ListingSource, ListingVersion
from app.repositories.analytics import ProductEvidence
from app.repositories.margin_sources import listing_current
from app.schemas.margin_review import MarginListing


class ListingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def margin_current(self, owner: int, shop: int, target: MarginListing) -> bool:
        return bool(
            self.session.scalar(
                select(
                    listing_current(
                        literal(owner), literal(shop), literal(target.model_dump(mode="json"), JSON)
                    )
                )
            )
        )

    def products(self, owner: int, shop: int, query: str, offset: int) -> list[ProductEvidence]:
        statement = (
            select(Product, ImportRow, ImportBatch)
            .join(ImportRow, Product.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                Product.shop_id == shop,
                ImportBatch.status == "committed",
            )
        )
        if query:
            statement = statement.where(
                Product.sku.contains(query, autoescape=True)
                | Product.name.contains(query, autoescape=True)
            )
        rows = self.session.execute(
            statement.order_by(Product.id)
            .offset(offset)
            .limit(50)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(p, r, b) for p, r, b in rows]

    def product(self, owner: int, shop: int, product_id: int) -> ProductEvidence | None:
        row = self.session.execute(
            select(Product, ImportRow, ImportBatch)
            .join(ImportRow, Product.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                Product.id == product_id,
                Product.shop_id == shop,
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.status == "committed",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        ).first()
        return (row[0], row[1], row[2]) if row else None

    def versions(self, owner: int, shop: int, key: str | None = None) -> list[ListingVersion]:
        statement = select(ListingVersion).where(
            ListingVersion.owner_id == owner, ListingVersion.shop_id == shop
        )
        if key:
            statement = statement.where(ListingVersion.product_key == key)
        return list(
            self.session.scalars(
                statement.order_by(ListingVersion.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def find(self, owner: int, shop: int, listing_id: int) -> ListingVersion | None:
        return self.session.scalar(
            select(ListingVersion)
            .where(
                ListingVersion.owner_id == owner,
                ListingVersion.shop_id == shop,
                ListingVersion.id == listing_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_key(self, owner: int, key: str) -> ListingVersion | None:
        return self.session.scalar(
            select(ListingVersion)
            .where(ListingVersion.owner_id == owner, ListingVersion.request_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def active(self, owner: int, shop: int, key: str) -> ListingVersion | None:
        return self.session.scalar(
            select(ListingVersion)
            .where(
                ListingVersion.owner_id == owner,
                ListingVersion.shop_id == shop,
                ListingVersion.product_key == key,
                ListingVersion.status == "approved",
                ListingVersion.source_status != "cleared",
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def next_number(self, owner: int, shop: int, key: str) -> int:
        value = self.session.scalar(
            select(func.max(ListingVersion.number))
            .where(
                ListingVersion.owner_id == owner,
                ListingVersion.shop_id == shop,
                ListingVersion.product_key == key,
            )
            .with_for_update()
        )
        return (value or 0) + 1

    def invalidation_epoch(self, owner: int, shop: int, key: str) -> int:
        # A restored source row permits a fresh draft without reviving stale history.
        return (
            self.session.scalar(
                select(func.max(ListingVersion.id))
                .where(
                    ListingVersion.owner_id == owner,
                    ListingVersion.shop_id == shop,
                    ListingVersion.product_key == key,
                    ListingVersion.source_status != "current",
                )
                .with_for_update()
            )
            or 0
        )

    def batches(self, owner: int, shop: int, listing_id: int) -> set[int]:
        return set(
            self.session.scalars(
                select(ListingSource.batch_id)
                .join(ListingVersion)
                .where(
                    ListingVersion.owner_id == owner,
                    ListingVersion.shop_id == shop,
                    ListingVersion.id == listing_id,
                )
                .with_for_update()
            )
        )

    def add(self, item: ListingVersion, batches: set[int]) -> None:
        self.session.add(item)
        self.session.flush()
        self.session.add_all([ListingSource(listing_id=item.id, batch_id=b) for b in batches])

    def invalidate(self, owner: int, shop: int) -> None:
        self.session.flush()
        still_current = exists(
            select(Product.id).where(
                Product.shop_id == shop, Product.source_row_id == ListingVersion.source_row_id
            )
        )
        self.session.execute(
            update(ListingVersion)
            .where(
                ListingVersion.owner_id == owner,
                ListingVersion.shop_id == shop,
                ListingVersion.source_status == "current",
                ~still_current,
            )
            .values(source_status="stale", version=ListingVersion.version + 1)
        )

    def purge_batch(self, owner: int, shop: int, batch_id: int) -> None:
        ids = list(
            self.session.scalars(
                select(ListingVersion.id)
                .join(ListingSource)
                .where(
                    ListingVersion.owner_id == owner,
                    ListingVersion.shop_id == shop,
                    ListingSource.batch_id == batch_id,
                )
                .with_for_update()
            )
        )
        if not ids:
            return
        self.session.execute(
            update(ListingVersion)
            .where(ListingVersion.id.in_(ids))
            .values(
                snapshot=None,
                source_row_id=None,
                source_status="cleared",
                version=ListingVersion.version + 1,
            )
        )
        self.session.execute(delete(ListingSource).where(ListingSource.listing_id.in_(ids)))
