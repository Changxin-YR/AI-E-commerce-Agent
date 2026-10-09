from sqlalchemy import delete, exists, select
from sqlalchemy.orm import Session

from app.models.imports import ImportRow, Product
from app.models.product_edits import ProductEdit, ProductEditSource


class ProductEditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, owner: int, shop: int, edit_id: int) -> ProductEdit | None:
        return self.session.scalar(
            select(ProductEdit)
            .where(
                ProductEdit.owner_id == owner,
                ProductEdit.shop_id == shop,
                ProductEdit.id == edit_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_request(self, owner: int, request_id: str) -> ProductEdit | None:
        return self.session.scalar(
            select(ProductEdit)
            .where(ProductEdit.owner_id == owner, ProductEdit.request_id == request_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(self, owner: int, shop: int, before: int | None) -> list[ProductEdit]:
        statement = select(ProductEdit).where(
            ProductEdit.owner_id == owner, ProductEdit.shop_id == shop
        )
        if before is not None:
            statement = statement.where(ProductEdit.id < before)
        return list(
            self.session.scalars(
                statement.order_by(ProductEdit.id.desc())
                .limit(21)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, edit: ProductEdit, batches: set[int]) -> None:
        self.session.add(edit)
        self.session.flush()
        self.session.add_all(ProductEditSource(edit_id=edit.id, batch_id=b) for b in batches)
        self.session.flush()

    def ancestors(self, owner: int, shop: int, batches: set[int]) -> set[int]:
        return (
            set(
                self.session.scalars(
                    select(ProductEditSource.batch_id)
                    .join(ProductEdit)
                    .where(
                        ProductEdit.owner_id == owner,
                        ProductEdit.shop_id == shop,
                        ProductEdit.output_batch_id.in_(batches),
                    )
                    .with_for_update()
                )
            )
            | batches
        )

    def affected(self, owner: int, shop: int, batch: int) -> list[ProductEdit]:
        dependency = exists(
            select(ProductEditSource.edit_id).where(
                ProductEditSource.edit_id == ProductEdit.id, ProductEditSource.batch_id == batch
            )
        )
        return list(
            self.session.scalars(
                select(ProductEdit)
                .where(
                    ProductEdit.owner_id == owner,
                    ProductEdit.shop_id == shop,
                    (ProductEdit.output_batch_id == batch) | dependency,
                    ProductEdit.status != "cleared",
                )
                .order_by(ProductEdit.id.desc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def clear(self, edit: ProductEdit) -> None:
        edit.snapshot = None
        edit.status = "cleared"
        edit.version += 1
        self.session.execute(delete(ProductEditSource).where(ProductEditSource.edit_id == edit.id))

    def current_count(self, owner: int, shop: int, batch: int) -> int:
        return len(
            list(
                self.session.scalars(
                    select(Product.id)
                    .join(ImportRow, Product.source_row_id == ImportRow.id)
                    .join(ProductEdit, ProductEdit.output_batch_id == ImportRow.batch_id)
                    .where(
                        Product.shop_id == shop,
                        ProductEdit.owner_id == owner,
                        ProductEdit.shop_id == shop,
                        ImportRow.batch_id == batch,
                    )
                    .with_for_update()
                )
            )
        )
