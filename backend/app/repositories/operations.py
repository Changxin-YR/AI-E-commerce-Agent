from datetime import datetime
from typing import TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, defer
from sqlalchemy.sql.elements import ColumnElement

from app.models.imports import (
    CustomerMessage,
    ImportBatch,
    ImportRow,
    InventorySnapshot,
    OrderLine,
    Product,
)
from app.models.operations import (
    OperationRun,
    OperationRunSource,
    OperationTask,
    OperationTaskEvent,
    OperationTaskSource,
)

Record = TypeVar("Record", Product, OrderLine, CustomerMessage, InventorySnapshot)


class OperationsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def records(
        self,
        model: type[Record],
        owner_id: int,
        shop_id: int,
        identity: str,
        channel: str | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[tuple[Record, ImportRow, ImportBatch]]:
        query = (
            select(model, ImportRow, ImportBatch)
            .join(ImportRow, model.source_row_id == ImportRow.id)
            .join(ImportBatch, ImportRow.batch_id == ImportBatch.id)
            .where(
                model.shop_id == shop_id,
                ImportBatch.owner_id == owner_id,
                ImportBatch.shop_id == shop_id,
                ImportBatch.data_identity == identity,
                ImportBatch.status == "committed",
            )
        )
        if channel is not None:
            query = query.where(ImportBatch.source_channel == channel)
        if start is not None and end is not None:
            query = query.where(OrderLine.ordered_at >= start, OrderLine.ordered_at < end)
        rows = self.session.execute(
            query.order_by(model.id)
            .limit(10001)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        return [(item, row, batch) for item, row, batch in rows]

    def add(self, item: OperationRun | OperationTask | OperationTaskEvent) -> None:
        self.session.add(item)
        self.session.flush()

    def run_sources(self, run_id: int, batches: set[int]) -> None:
        self.session.add_all([OperationRunSource(run_id=run_id, batch_id=b) for b in batches])

    def task_sources(self, task_id: int, sources: dict[int, int]) -> None:
        self.session.add_all(
            [OperationTaskSource(task_id=task_id, row_id=r, batch_id=b) for r, b in sources.items()]
        )

    def task_by_key(self, owner: int, key: str) -> OperationTask | None:
        return self.session.scalar(
            select(OperationTask)
            .where(OperationTask.owner_id == owner, OperationTask.dedupe_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def task(self, owner: int, shop: int, task: int) -> OperationTask | None:
        return self.session.scalar(
            select(OperationTask)
            .where(
                OperationTask.owner_id == owner,
                OperationTask.shop_id == shop,
                OperationTask.id == task,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def tasks(
        self, owner: int, shop: int, identity: str, channel: str, offset: int
    ) -> list[OperationTask]:
        return list(
            self.session.scalars(
                select(OperationTask)
                .where(
                    OperationTask.owner_id == owner,
                    OperationTask.shop_id == shop,
                    OperationTask.data_identity == identity,
                    OperationTask.channel == channel,
                )
                .order_by(OperationTask.id.desc())
                .offset(offset)
                .limit(51)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def history(self, task_id: int) -> list[OperationTaskEvent]:
        return list(
            self.session.scalars(
                select(OperationTaskEvent)
                .where(OperationTaskEvent.task_id == task_id)
                .order_by(OperationTaskEvent.id.desc())
                .limit(50)
                .with_for_update()
            )
        )

    def run_by_request(self, owner: int, request: str) -> OperationRun | None:
        return self.session.scalar(
            select(OperationRun)
            .where(OperationRun.owner_id == owner, OperationRun.request_id == request)
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def run(self, owner: int, shop: int, run_id: int) -> OperationRun | None:
        return self.session.scalar(
            select(OperationRun)
            .where(
                OperationRun.owner_id == owner,
                OperationRun.shop_id == shop,
                OperationRun.id == run_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def runs(self, owner: int, shop: int, identity: str, channel: str) -> list[OperationRun]:
        return list(
            self.session.scalars(
                select(OperationRun)
                .where(
                    OperationRun.owner_id == owner,
                    OperationRun.shop_id == shop,
                    OperationRun.scope["data_identity"].as_string() == identity,
                    OperationRun.scope["channel"].as_string() == channel,
                )
                .options(defer(OperationRun.snapshot))
                .order_by(OperationRun.id.desc())
                .limit(50)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def expire(self, owner: int, shop: int, now: datetime) -> None:
        self.session.execute(
            update(OperationRun)
            .where(
                OperationRun.owner_id == owner,
                OperationRun.shop_id == shop,
                OperationRun.source_status == "current",
                OperationRun.valid_until <= now,
            )
            .values(source_status="stale")
        )
        self.session.execute(
            update(OperationTask)
            .where(
                OperationTask.owner_id == owner,
                OperationTask.shop_id == shop,
                OperationTask.source_status == "current",
                OperationTask.valid_until <= now,
            )
            .values(source_status="stale", version=OperationTask.version + 1)
        )

    def invalidate(self, owner: int, shop: int, kind: str) -> None:
        self.session.execute(
            update(OperationRun)
            .where(
                OperationRun.owner_id == owner,
                OperationRun.shop_id == shop,
                OperationRun.source_status == "current",
            )
            .values(source_status="stale")
        )
        # A source row must still be the current projection. Restoring a prior row does
        # not revalidate history; a new check must do so, preserving task disposition.
        models: dict[
            str, type[OrderLine] | type[InventorySnapshot] | type[CustomerMessage] | type[Product]
        ] = {
            "orders": OrderLine,
            "inventory": InventorySnapshot,
            "messages": CustomerMessage,
            "products": Product,
        }
        # Statements change the shop revision, but the four daily findings do not consume them.
        if kind == "statements":
            return
        model = models[kind]
        invalid = (
            select(OperationTaskSource.task_id)
            .join(ImportBatch, OperationTaskSource.batch_id == ImportBatch.id)
            .where(
                ImportBatch.owner_id == owner,
                ImportBatch.shop_id == shop,
                ImportBatch.kind == kind,
                OperationTaskSource.row_id.not_in(
                    select(model.source_row_id).where(model.shop_id == shop)
                ),
            )
        )
        conditions: ColumnElement[bool] = OperationTask.id.in_(invalid)
        if kind in {"orders", "products"}:
            conditions = conditions | (OperationTask.kind == "low_margin")
        self.session.execute(
            update(OperationTask)
            .where(
                OperationTask.owner_id == owner,
                OperationTask.shop_id == shop,
                OperationTask.source_status == "current",
                conditions,
            )
            .values(source_status="stale", version=OperationTask.version + 1)
        )

    def purge_batch(self, owner: int, shop: int, batch: int) -> None:
        runs = list(
            self.session.scalars(
                select(OperationRun.id)
                .join(OperationRunSource)
                .where(
                    OperationRun.owner_id == owner,
                    OperationRun.shop_id == shop,
                    OperationRunSource.batch_id == batch,
                )
                .with_for_update()
            )
        )
        tasks = list(
            self.session.scalars(
                select(OperationTask.id)
                .join(OperationTaskSource)
                .where(
                    OperationTask.owner_id == owner,
                    OperationTask.shop_id == shop,
                    OperationTaskSource.batch_id == batch,
                )
                .with_for_update()
            )
        )
        if runs:
            self.session.execute(
                update(OperationRun)
                .where(OperationRun.id.in_(runs))
                .values(snapshot=None, source_status="cleared", valid_until=None)
            )
            self.session.execute(
                delete(OperationRunSource).where(OperationRunSource.run_id.in_(runs))
            )
        if tasks:
            self.session.execute(
                update(OperationTask)
                .where(OperationTask.id.in_(tasks))
                .values(
                    snapshot=None,
                    source_status="cleared",
                    note="",
                    due_at=None,
                    valid_until=None,
                    version=OperationTask.version + 1,
                )
            )
            self.session.execute(
                update(OperationTaskEvent)
                .where(OperationTaskEvent.task_id.in_(tasks))
                .values(details=None)
            )
            self.session.execute(
                delete(OperationTaskSource).where(OperationTaskSource.task_id.in_(tasks))
            )
