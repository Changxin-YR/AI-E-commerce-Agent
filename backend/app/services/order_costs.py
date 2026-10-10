from datetime import timedelta

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.order_costs import OrderCostRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.order_costs import CostHistory, CostWrite
from app.services.import_groups import require_import_coverage
from app.services.imports import ImportService
from app.services.product_quality import digest
from app.services.profit_calculation import cost_version


class OrderCostService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.order_costs

    def _shop(self, owner: int, shop: int) -> Shop:
        self.uow.identity.lock_user(owner)
        store = self.uow.identity.get_shop(owner, shop, lock=True)
        if store is None:
            raise NotFoundError()
        return store

    def get(self, owner: int, shop: int, row_id: int) -> CostHistory:
        store = self._shop(owner, shop)
        source = self.uow.analytics.source(owner, shop, row_id)
        if source is None or source[1].kind != "orders":
            raise NotFoundError()
        row, batch = source
        records = self.repo.history(owner, shop, row_id)
        return CostHistory(
            source_row_id=row.id,
            source_batch_id=batch.id,
            source_current=self.repo.order(owner, shop, row_id) is not None,
            source_revision=store.data_revision,
            order_id=str(row.normalized["order_id"]),
            line_id=str(row.normalized["line_id"]),
            sku=str(row.normalized["sku"]),
            currency=str(row.normalized["currency"]),
            channel=batch.source_channel,
            data_identity=batch.data_identity,
            version=records[0].version if records else 0,
            history=[cost_version(r) for r in records],
        )

    def write(self, owner: int, shop: int, row_id: int, data: CostWrite) -> CostHistory:
        store = self._shop(owner, shop)
        request_hash = digest(
            {"shop": shop, "row": row_id, **data.model_dump(mode="json", exclude={"request_id"})}
        )
        replay = self.repo.by_request(owner, str(data.request_id))
        if replay:
            if replay.request_hash != request_hash:
                raise ConflictError("请求标识已用于另一项成本操作，或来源已清除")
            output = self.get(owner, shop, row_id)
            self.uow.commit()
            return output
        source = self.repo.order(owner, shop, row_id)
        if source is None or store.data_revision != data.expected_revision:
            raise ConflictError("订单来源或数据版本已变化，请刷新并重新核对凭据")
        _, row, batch = source
        require_import_coverage(
            self.uow, owner, shop, batch.data_identity, {"orders"}, batch.source_channel
        )
        records = self.repo.history(owner, shop, row_id)
        latest = records[0] if records else None
        if data.expected_version != (latest.version if latest else 0):
            raise ConflictError("成本凭据版本已变化，请刷新后重试")
        if len(records) >= 100 and data.action != "revoke":
            raise BusinessError(
                "revision_limit", "该源行已达 100 次成本操作上限，可撤销后核对来源", 422
            )
        content = data.content
        if content and content.evidence_at.replace(tzinfo=None) > utc_now() + timedelta(minutes=5):
            raise BusinessError("future_evidence", "凭据时间不能在未来，请核对时区", 422)
        if data.action == "revoke" and (latest is None or latest.status == "revoked"):
            raise ConflictError("该源行尚无可撤销的成本凭据")
        if latest and latest.status == "active":
            latest.status = "superseded"
        record = OrderCostRevision(
            owner_id=owner,
            shop_id=shop,
            source_key=digest({"shop": shop, "row": row.id}),
            source_row_id=row.id,
            source_batch_id=batch.id,
            version=data.expected_version + 1,
            request_id=str(data.request_id),
            request_hash=request_hash,
            action=data.action,
            status="active" if content else "revoked",
            unit_cost=content.unit_cost if content else None,
            currency=content.currency if content else None,
            evidence_ref=content.evidence_ref if content else None,
            evidence_at=content.evidence_at.replace(tzinfo=None) if content else None,
        )
        self.repo.add(record)
        store.data_revision += 1
        ImportService(self.uow).invalidate(owner, shop, "orders")
        self.uow.record_event(
            owner,
            f"order_cost.{data.action}",
            "order_cost",
            record.id,
            {"version": record.version, "revision": store.data_revision},
        )
        output = self.get(owner, shop, row_id)
        self.uow.commit()
        return output
