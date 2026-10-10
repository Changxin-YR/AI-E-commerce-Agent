from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.models.identity import Shop
from app.models.imports import (
    CustomerMessage,
    ImportBatch,
    ImportRow,
    InventorySnapshot,
    MappingTemplate,
    OrderLine,
    Product,
    StatementLine,
)
from app.schemas.imports import InventoryData, MessageData, OrderData, ProductData, StatementData

ImportedRecord = Product | OrderLine | CustomerMessage | InventorySnapshot | StatementLine
ImportedModel = (
    type[Product]
    | type[OrderLine]
    | type[CustomerMessage]
    | type[InventorySnapshot]
    | type[StatementLine]
)


class ImportRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_batch(self, owner_id: int, batch_id: int) -> ImportBatch | None:
        return self.session.scalar(
            select(ImportBatch)
            .where(
                ImportBatch.id == batch_id,
                ImportBatch.owner_id == owner_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def list_batches(self, owner_id: int, shop_id: int) -> list[ImportBatch]:
        return list(
            self.session.scalars(
                select(ImportBatch)
                .where(
                    ImportBatch.owner_id == owner_id,
                    ImportBatch.shop_id == shop_id,
                )
                .order_by(ImportBatch.id.desc())
                .limit(100)
            )
        )

    def add_batch(self, batch: ImportBatch) -> None:
        self.session.add(batch)
        self.session.flush()

    def rows(self, owner_id: int, batch_id: int) -> list[ImportRow]:
        return list(
            self.session.scalars(
                select(ImportRow)
                .join(ImportBatch)
                .where(
                    ImportBatch.owner_id == owner_id,
                    ImportBatch.id == batch_id,
                )
                .order_by(ImportRow.row_number)
                .with_for_update()
            )
        )

    def replace_rows(self, owner_id: int, batch_id: int, rows: list[ImportRow]) -> None:
        owned = select(ImportBatch.id).where(
            ImportBatch.owner_id == owner_id, ImportBatch.id == batch_id
        )
        self.session.execute(delete(ImportRow).where(ImportRow.batch_id.in_(owned)))
        self.session.add_all(rows)
        self.session.flush()

    def current_entries(
        self,
        owner_id: int,
        shop_id: int,
        kind: str,
    ) -> dict[str, tuple[ImportedRecord, ImportRow]]:
        models: dict[str, ImportedModel] = {
            "products": Product,
            "orders": OrderLine,
            "messages": CustomerMessage,
            "inventory": InventorySnapshot,
            "statements": StatementLine,
        }
        model = models[kind]
        entries = self.session.execute(
            select(model, ImportRow)
            .join(
                ImportRow,
                model.source_row_id == ImportRow.id,
            )
            .join(Shop, Shop.id == model.shop_id)
            .where(Shop.owner_id == owner_id, Shop.id == shop_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return {row.business_key: (record, row) for record, row in entries if row.business_key}

    def apply_row(
        self,
        shop_id: int,
        kind: str,
        row: ImportRow,
        existing: ImportedRecord | None,
    ) -> None:
        values: dict[str, Any]
        if kind == "products":
            values = ProductData.model_validate(row.normalized).model_dump()
            model: ImportedModel = Product
        elif kind == "orders":
            values = OrderData.model_validate(row.normalized).model_dump()
            values["ordered_at"] = values["ordered_at"].astimezone(UTC).replace(tzinfo=None)
            model = OrderLine
        elif kind == "statements":
            values = StatementData.model_validate(row.normalized).model_dump()
            values["occurred_at"] = values["occurred_at"].astimezone(UTC).replace(tzinfo=None)
            batch = self.session.get(ImportBatch, row.batch_id)
            assert batch is not None
            values["channel"] = batch.source_channel
            values["data_identity"] = batch.data_identity
            model = StatementLine
        elif kind == "inventory":
            values = InventoryData.model_validate(row.normalized).model_dump()
            values["snapshot_at"] = values["snapshot_at"].astimezone(UTC).replace(tzinfo=None)
            batch = self.session.get(ImportBatch, row.batch_id)
            assert batch is not None
            values["channel"] = batch.source_channel
            model = InventorySnapshot
        else:
            values = MessageData.model_validate(row.normalized).model_dump(
                exclude={"reply_status", "reply_updated_at", "reply_evidence"}
            )
            values["sent_at"] = values["sent_at"].astimezone(UTC).replace(tzinfo=None)
            batch = self.session.get(ImportBatch, row.batch_id)
            assert batch is not None
            values["channel"] = batch.source_channel
            model = CustomerMessage
        if existing is None:
            self.session.add(model(shop_id=shop_id, source_row_id=row.id, **values))
        else:
            for key, value in values.items():
                setattr(existing, key, value)
            existing.source_row_id = row.id

    def active_versions(
        self,
        owner_id: int,
        shop_id: int,
        kind: str,
        keys: set[str],
    ) -> dict[str, ImportRow]:
        rows = self.session.scalars(
            select(ImportRow)
            .join(ImportBatch)
            .where(
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.kind == kind,
                ImportBatch.status == "committed",
                ImportRow.business_key.in_(keys),
            )
            .order_by(ImportBatch.applied_revision.desc())
            .with_for_update()
        )
        winners: dict[str, ImportRow] = {}
        for row in rows:
            if row.business_key:
                winners.setdefault(row.business_key, row)
        return winners

    def delete_record(self, record: ImportedRecord) -> None:
        self.session.delete(record)

    def flush(self) -> None:
        self.session.flush()

    def clear_previous(self, owner_id: int, shop_id: int, keys: set[str]) -> None:
        batches = select(ImportBatch.id).where(
            ImportBatch.owner_id == owner_id, ImportBatch.shop_id == shop_id
        )
        self.session.execute(
            update(ImportRow)
            .where(
                ImportRow.batch_id.in_(batches),
                ImportRow.business_key.in_(keys),
            )
            .values(previous=None)
        )

    def expired_drafts(self, owner_id: int, now: datetime) -> list[ImportBatch]:
        return list(
            self.session.scalars(
                select(ImportBatch)
                .where(
                    ImportBatch.owner_id == owner_id,
                    ImportBatch.status.in_(["draft", "preview"]),
                    ImportBatch.expires_at < now,
                )
                .with_for_update()
            )
        )

    def templates(self, owner_id: int) -> list[MappingTemplate]:
        return list(
            self.session.scalars(
                select(MappingTemplate)
                .where(
                    MappingTemplate.owner_id == owner_id,
                )
                .order_by(MappingTemplate.id.desc())
            )
        )

    def save_template(self, owner_id: int, values: dict[str, Any]) -> MappingTemplate:
        template = self.session.scalar(
            select(MappingTemplate)
            .where(
                MappingTemplate.owner_id == owner_id,
                MappingTemplate.name == values["name"],
            )
            .with_for_update()
        )
        if template:
            for key, value in values.items():
                setattr(template, key, value)
        else:
            template = MappingTemplate(owner_id=owner_id, **values)
            self.session.add(template)
        self.session.flush()
        return template
