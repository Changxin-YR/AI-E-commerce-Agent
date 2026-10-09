from datetime import datetime

from sqlalchemy import delete, exists, select, update
from sqlalchemy.orm import Session

from app.core.errors import BusinessError
from app.models.settlements import (
    Settlement,
    SettlementReceipt,
    SettlementRevision,
    SettlementSource,
)


class SettlementRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, owner: int, shop: int, settlement: int) -> Settlement | None:
        return self.session.scalar(
            select(Settlement)
            .where(
                Settlement.owner_id == owner,
                Settlement.shop_id == shop,
                Settlement.id == settlement,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def revision(self, settlement: Settlement, version: int) -> SettlementRevision | None:
        return self.session.scalar(
            select(SettlementRevision)
            .where(
                SettlementRevision.owner_id == settlement.owner_id,
                SettlementRevision.settlement_id == settlement.id,
                SettlementRevision.version == version,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def history(self, settlement: Settlement) -> list[tuple[int, str, datetime, bool]]:
        rows = self.session.execute(
            select(
                SettlementRevision.version,
                SettlementRevision.action,
                SettlementRevision.created_at,
                SettlementRevision.snapshot.is_not(None),
            )
            .where(
                SettlementRevision.owner_id == settlement.owner_id,
                SettlementRevision.settlement_id == settlement.id,
            )
            .order_by(SettlementRevision.version.desc())
            .with_for_update()
        )
        return [(v, a, t, c) for v, a, t, c in rows]

    def by_request(self, owner: int, request: str) -> SettlementRevision | None:
        return self.session.scalar(
            select(SettlementRevision)
            .where(
                SettlementRevision.owner_id == owner,
                SettlementRevision.request_id == request,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> list[Settlement]:
        query = select(Settlement).where(
            Settlement.owner_id == owner,
            Settlement.shop_id == shop,
            Settlement.data_identity == identity,
            Settlement.channel == channel,
        )
        if before is not None:
            query = query.where(Settlement.id < before)
        return list(
            self.session.scalars(
                query.order_by(Settlement.id.desc())
                .limit(21)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )

    def add(self, settlement: Settlement) -> None:
        self.session.add(settlement)
        self.session.flush()

    def revise(self, revision: SettlementRevision) -> None:
        self.session.add(revision)
        self.session.flush()

    def dependencies(self, settlement: Settlement, batches: set[int]) -> None:
        previous = set(
            self.session.scalars(
                select(SettlementSource.batch_id)
                .where(SettlementSource.settlement_id == settlement.id)
                .with_for_update()
            )
        )
        if len(previous | batches) > 10000:
            raise BusinessError("dependency_limit", "历史依赖超过 10000 项，请新建登记。", 422)
        for batch in batches - previous:
            self.session.add(SettlementSource(settlement_id=settlement.id, batch_id=batch))
        self.session.flush()

    def conflicts(
        self,
        owner: int,
        shop: int,
        identity: str,
        channel: str,
        settlement_id: int | None,
        statement_key: str,
        receipt_keys: set[str],
    ) -> bool:
        statement = select(Settlement.id).where(
            Settlement.owner_id == owner,
            Settlement.shop_id == shop,
            Settlement.data_identity == identity,
            Settlement.channel == channel,
            Settlement.statement_key == statement_key,
        )
        receipt = select(SettlementReceipt.id).where(
            SettlementReceipt.owner_id == owner,
            SettlementReceipt.shop_id == shop,
            SettlementReceipt.data_identity == identity,
            SettlementReceipt.channel == channel,
            SettlementReceipt.receipt_key.in_(receipt_keys),
        )
        if settlement_id is not None:
            statement = statement.where(Settlement.id != settlement_id)
            receipt = receipt.where(SettlementReceipt.settlement_id != settlement_id)
        return self.session.scalar(statement.limit(1).with_for_update()) is not None or (
            bool(receipt_keys)
            and self.session.scalar(receipt.limit(1).with_for_update()) is not None
        )

    def release(self, settlement: Settlement) -> None:
        settlement.statement_key = None
        self.session.execute(
            update(SettlementReceipt)
            .where(
                SettlementReceipt.settlement_id == settlement.id,
                SettlementReceipt.owner_id == settlement.owner_id,
            )
            .values(receipt_key=None)
        )
        self.session.flush()

    def receipt(self, receipt: SettlementReceipt) -> None:
        self.session.add(receipt)
        self.session.flush()

    def scope_revision(self, owner: int, shop: int, identity: str, channel: str) -> int:
        return (
            self.session.scalar(
                select(SettlementRevision.id)
                .join(Settlement, SettlementRevision.settlement_id == Settlement.id)
                .where(
                    Settlement.owner_id == owner,
                    Settlement.shop_id == shop,
                    Settlement.data_identity == identity,
                    Settlement.channel == channel,
                )
                .order_by(SettlementRevision.id.desc())
                .limit(1)
                .with_for_update()
            )
            or 0
        )

    def invalidate(
        self, owner: int, shop: int, identity: str | None = None, channel: str | None = None
    ) -> None:
        query = select(Settlement).where(
            Settlement.owner_id == owner,
            Settlement.shop_id == shop,
            Settlement.status == "active",
        )
        if identity is not None:
            query = query.where(Settlement.data_identity == identity, Settlement.channel == channel)
        for settlement in self.session.scalars(
            query.with_for_update().execution_options(populate_existing=True)
        ):
            settlement.status = "stale"
            settlement.version += 1

    def clear(self, settlement: Settlement) -> None:
        self.session.execute(
            update(SettlementRevision)
            .where(
                SettlementRevision.owner_id == settlement.owner_id,
                SettlementRevision.settlement_id == settlement.id,
            )
            .values(snapshot=None)
        )
        self.release(settlement)
        settlement.status = "cleared"
        settlement.version += 1
        self.session.execute(
            delete(SettlementSource).where(SettlementSource.settlement_id == settlement.id)
        )
        self.session.execute(
            delete(SettlementReceipt).where(
                SettlementReceipt.settlement_id == settlement.id,
                SettlementReceipt.owner_id == settlement.owner_id,
            )
        )

    def purge(self, owner: int, shop: int, batch: int) -> None:
        dependency = exists(
            select(SettlementSource.settlement_id).where(
                SettlementSource.settlement_id == Settlement.id, SettlementSource.batch_id == batch
            )
        )
        rows = list(
            self.session.scalars(
                select(Settlement)
                .where(
                    Settlement.owner_id == owner,
                    Settlement.shop_id == shop,
                    Settlement.status != "cleared",
                    dependency,
                )
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        )
        for settlement in rows:
            self.clear(settlement)
