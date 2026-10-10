from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, defer

from app.models.import_groups import ImportGroup
from app.models.imports import ImportBatch, ImportRow


class ImportGroupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, owner: int, group_id: int) -> ImportGroup | None:
        return self.session.scalar(
            select(ImportGroup)
            .where(ImportGroup.owner_id == owner, ImportGroup.id == group_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def by_key(self, owner: int, shop: int, key: str) -> ImportGroup | None:
        return self.session.scalar(
            select(ImportGroup)
            .where(
                ImportGroup.owner_id == owner,
                ImportGroup.shop_id == shop,
                ImportGroup.request_key == key,
                ImportGroup.status == "active",
            )
            .limit(1)
        )

    def groups(self, owner: int, shop: int, before: int | None = None) -> list[ImportGroup]:
        query = select(ImportGroup).where(
            ImportGroup.owner_id == owner, ImportGroup.shop_id == shop
        )
        if before is not None:
            query = query.where(ImportGroup.id < before)
        return list(self.session.scalars(query.order_by(ImportGroup.id.desc()).limit(20)))

    def add(self, group: ImportGroup) -> None:
        self.session.add(group)
        self.session.flush()

    def batches(self, owner: int, group_id: int) -> list[ImportBatch]:
        return list(
            self.session.scalars(
                select(ImportBatch)
                .options(defer(ImportBatch.raw_data))
                .where(ImportBatch.owner_id == owner, ImportBatch.group_id == group_id)
                .order_by(ImportBatch.id)
            )
        )

    def committed_rows(self, owner: int, group_id: int) -> list[ImportRow]:
        return list(
            self.session.scalars(
                select(ImportRow)
                .join(ImportBatch)
                .where(
                    ImportBatch.owner_id == owner,
                    ImportBatch.group_id == group_id,
                    ImportBatch.status == "committed",
                )
            )
        )

    def incomplete(
        self, owner: int, shop: int, identity: str, kinds: set[str], channel: str | None
    ) -> bool:
        query = select(ImportGroup.id).where(
            ImportGroup.owner_id == owner,
            ImportGroup.shop_id == shop,
            ImportGroup.data_identity == identity,
            ImportGroup.kind.in_(kinds),
            ImportGroup.status == "active",
            ImportGroup.complete.is_(False),
        )
        if channel:
            query = query.where(
                or_(ImportGroup.source_channel == channel, ImportGroup.kind == "products")
            )
        return self.session.scalar(query.limit(1)) is not None

    def counts(self, owner: int, group_id: int) -> tuple[int, int]:
        result = self.session.execute(
            select(func.count(ImportRow.id), func.count(func.distinct(ImportRow.business_key)))
            .join(ImportBatch)
            .where(
                ImportBatch.owner_id == owner,
                ImportBatch.group_id == group_id,
                ImportBatch.status == "committed",
            )
        ).one()
        return int(result[0]), int(result[1])
