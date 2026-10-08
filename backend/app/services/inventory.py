from datetime import datetime, timedelta
from typing import Literal

from app.core.errors import NotFoundError
from app.core.time import utc_now
from app.repositories.inventory import InventoryEvidence
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.inventory import InventoryItem, InventoryOutput, InventoryQuery
from app.services.profit_calculation import reference, utc_text


def assess_snapshot(
    evidence: InventoryEvidence, now: datetime, max_age_hours: int
) -> InventoryItem:
    item, row, batch = evidence
    valid_until = item.snapshot_at + timedelta(hours=max_age_hours)
    status: Literal["low", "above_threshold", "unknown"]
    if item.snapshot_at > now:
        status, reason = "unknown", "快照晚于当前时间，需核对来源"
    elif now >= valid_until:
        status, reason = "unknown", "快照已超过选定时效，当前库存未知；请导入新快照"
    elif item.available < item.safety_threshold:
        status, reason = "low", "快照可售数量严格低于卖家设定阈值，请核对实际库存"
    else:
        status, reason = "above_threshold", "快照可售数量未低于阈值；不保证实时可售"
    return InventoryItem(
        id=item.id,
        sku=item.sku,
        channel=item.channel,
        available=item.available,
        safety_threshold=item.safety_threshold,
        snapshot_at=utc_text(item.snapshot_at),
        valid_until=utc_text(valid_until),
        status=status,
        reason=reason,
        source=reference(row, batch),
    )


class InventoryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def list(self, owner_id: int, shop_id: int, scope: InventoryQuery) -> InventoryOutput:
        self.uow.identity.lock_user(owner_id)
        shop = self.uow.identity.get_shop(owner_id, shop_id, lock=True)
        if shop is None:
            raise NotFoundError()
        now = utc_now()
        rows = self.uow.inventory.snapshots(owner_id, shop_id, scope)
        result = InventoryOutput(
            shop_id=shop.id,
            source_revision=shop.data_revision,
            checked_at=utc_text(now),
            scope=scope,
            items=[assess_snapshot(row, now, scope.max_age_hours) for row in rows[:50]],
            has_more=len(rows) > 50,
        )
        self.uow.commit()
        return result
