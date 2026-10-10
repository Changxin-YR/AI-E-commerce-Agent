"""Recheck original objects against bounded, current import projections."""

from datetime import UTC, datetime, timedelta
from decimal import localcontext
from typing import Literal

from app.core.errors import BusinessError
from app.models.imports import (
    CustomerMessage,
    ImportBatch,
    ImportRow,
    InventorySnapshot,
    OrderLine,
    Product,
)
from app.models.operations import OperationTask
from app.repositories.operations import Record
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.analytics import SourceReference
from app.schemas.operations import Finding, OperationScope, TaskRecheck
from app.services.profit_calculation import PAID_STATUSES, calculate, reference, utc_text

RecheckState = Literal["awaiting_source", "resolved", "still_anomalous"]


def normalized_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        stamp = datetime.fromisoformat(value)
        if stamp.utcoffset() is None:
            return None
        return stamp.astimezone(UTC).replace(tzinfo=None)
    except ValueError:
        return None


def message_reply_time(
    row: ImportRow, batch: ImportBatch, now: datetime, hours: int
) -> datetime | None:
    stamp = normalized_time(row.normalized.get("reply_updated_at"))
    exported = batch.exported_at
    if (
        stamp is None
        or exported is None
        or not now - timedelta(hours=hours) < stamp <= exported <= now
    ):
        return None
    if row.normalized.get("reply_status") == "replied" and not row.normalized.get("reply_evidence"):
        return None
    return stamp


class OperationRechecks:
    def __init__(self, uow: UnitOfWork, task: OperationTask, revision: int, now: datetime) -> None:
        self.uow = uow
        self.task = task
        self.revision = revision
        self.now = now
        self.sources: list[SourceReference] = []
        self.facts: dict[str, str] = {"渠道": task.channel, "数据身份": task.data_identity}
        self.finding = Finding.model_validate(task.snapshot)
        self.scope = self.finding.scope
        self.original: list[tuple[ImportRow, ImportBatch]] = []
        self.floor = task.created_at
        manual = (task.review or {}).get("evidence")
        if manual:
            stamp = normalized_time(manual.get("occurred_at"))
            if stamp:
                self.floor = max(self.floor, stamp)

    def result(
        self, state: RecheckState, reason: str, stamps: list[datetime] | None = None
    ) -> TaskRecheck:
        if len(self.sources) > 1000:
            raise BusinessError(
                "too_many_review_sources", "同对象复检证据超过1000行，请缩小范围重新检查", 422
            )
        return TaskRecheck(
            state=state,
            reason=reason,
            source_revision=self.revision,
            checked_at=utc_text(self.now),
            valid_until=utc_text(min(stamps) + timedelta(hours=self.scope.max_age_hours))
            if stamps and self.scope
            else None,
            sources=self.sources,
            facts=self.facts,
        )

    def records(
        self, model: type[Record], scope: OperationScope, channel: str | None = None
    ) -> list[tuple[Record, ImportRow, ImportBatch]]:
        result = self.uow.operations.records(
            model,
            self.task.owner_id,
            self.task.shop_id,
            scope.data_identity,
            channel,
            scope.start_at.replace(tzinfo=None) if model is OrderLine else None,
            scope.end_at.replace(tzinfo=None) if model is OrderLine else None,
        )
        if len(result) > 10000:
            raise BusinessError("range_too_large", "单项复检超过10000行，请缩小范围重新检查", 422)
        return result

    def fresh(self, stamps: list[datetime | None], scope: OperationScope) -> bool:
        return bool(stamps) and all(
            stamp is not None
            and max(self.floor, self.now - timedelta(hours=scope.max_age_hours)) < stamp <= self.now
            for stamp in stamps
        )

    def run(self) -> TaskRecheck:
        scope = self.scope
        if scope is None:
            return self.result(
                "awaiting_source", "旧事项缺完整检查范围；保留历史，请按明确范围重新检查。"
            )
        if scope.channel != self.task.channel or scope.data_identity != self.task.data_identity:
            return self.result("awaiting_source", "原事项范围与来源身份不一致，请重新检查。")
        ids = list({ref.row_id for ref in self.finding.sources})
        if len(ids) > 1000:
            raise BusinessError(
                "too_many_review_sources", "原事项证据超过1000行，请缩小范围重新检查", 422
            )
        self.original = self.uow.operations.original_rows(self.task, ids)
        if not ids or len(self.original) != len(ids):
            return self.result("awaiting_source", "原对象来源不完整，无法证明新数据对应此异常。")
        kinds = {batch.kind for _, batch in self.original}
        # Products can have their own original channel; inspect coverage for every used channel.
        for kind, channel in {(batch.kind, batch.source_channel) for _, batch in self.original}:
            if self.uow.import_groups.incomplete(
                self.task.owner_id, self.task.shop_id, scope.data_identity, {kind}, channel
            ):
                return self.result(
                    "awaiting_source", "对应来源存在未完成导入组，须补齐或撤销整组后复检。"
                )
        if any(
            batch.source_channel != scope.channel
            for _, batch in self.original
            if batch.kind != "products"
        ):
            return self.result("awaiting_source", "原对象渠道不匹配，无法复检。")
        if self.task.kind == "low_inventory" and kinds == {"inventory"}:
            return self.inventory(scope)
        if self.task.kind == "order_review" and kinds == {"orders"}:
            return self.order(scope)
        if self.task.kind == "message_review" and kinds == {"messages"}:
            return self.message(scope)
        if self.task.kind == "low_margin" and kinds == {"orders", "products"}:
            return self.margin(scope)
        return self.result("awaiting_source", "原异常类型或来源不完整，需重新检查。")

    def inventory(self, scope: OperationScope) -> TaskRecheck:
        original, _ = self.original[0]
        matches = [
            item
            for item in self.records(InventorySnapshot, scope, scope.channel)
            if item[0].sku == original.normalized.get("sku")
        ]
        if len(matches) != 1:
            return self.result("awaiting_source", "当前来源缺少原渠道同SKU库存快照。")
        stock, row, batch = matches[0]
        self.sources = [reference(row, batch)]
        self.facts.update(
            {
                "SKU": stock.sku,
                "快照可售": str(stock.available),
                "安全阈值": str(stock.safety_threshold),
                "快照时间": utc_text(stock.snapshot_at),
            }
        )
        if stock.safety_threshold != original.normalized.get("safety_threshold"):
            return self.result(
                "awaiting_source", "安全阈值已改变，不能按新阈值解除原异常；请重新检查。"
            )
        if row.id == original.id or not self.fresh([stock.snapshot_at], scope):
            return self.result(
                "awaiting_source", "需要晚于异常发现和人工操作、且仍有效的新库存快照。"
            )
        state: RecheckState = (
            "resolved" if stock.available >= stock.safety_threshold else "still_anomalous"
        )
        return self.result(
            state,
            "新快照支持库存已达到原安全阈值。"
            if state == "resolved"
            else "新快照仍低于原安全阈值。",
            [stock.snapshot_at],
        )

    def order(self, scope: OperationScope) -> TaskRecheck:
        original, _ = self.original[0]
        matches = [
            item
            for item in self.records(OrderLine, scope, scope.channel)
            if (item[0].order_id, item[0].line_id)
            == (original.normalized.get("order_id"), original.normalized.get("line_id"))
        ]
        if len(matches) != 1:
            return self.result(
                "awaiting_source", "原时间窗缺同订单号和行号的当前来源，缺行不能证明已履约。"
            )
        order, row, batch = matches[0]
        self.sources = [reference(row, batch)]
        self.facts.update(
            {
                "订单号": order.order_id,
                "行号": order.line_id,
                "SKU": order.sku,
                "文件履约状态": order.fulfillment_status,
                "文件订单状态": order.status,
            }
        )
        if order.sku != original.normalized.get("sku"):
            return self.result("awaiting_source", "订单行SKU改变，不能确定仍为原异常对象。")
        if row.id == original.id or not self.fresh([batch.exported_at], scope):
            return self.result(
                "awaiting_source", "需要新订单来源和晚于异常发现及人工操作的有效导出时间。"
            )
        if order.status not in PAID_STATUSES or order.fulfillment_status == "unknown":
            return self.result("awaiting_source", "当前付款或履约状态不足以证明原订单行已履约。")
        state: RecheckState = (
            "resolved" if order.fulfillment_status == "fulfilled" else "still_anomalous"
        )
        assert batch.exported_at is not None
        return self.result(
            state,
            "新文件明确记录原订单行已履约；系统未执行外部发货。"
            if state == "resolved"
            else "新文件仍记录未履约或部分履约。",
            [batch.exported_at],
        )

    def message(self, scope: OperationScope) -> TaskRecheck:
        original, _ = self.original[0]
        matches = [
            item
            for item in self.records(CustomerMessage, scope, scope.channel)
            if item[0].message_id == original.normalized.get("message_id")
        ]
        if len(matches) != 1:
            return self.result("awaiting_source", "当前渠道缺原消息来源。")
        _, row, batch = matches[0]
        self.sources = [reference(row, batch)]
        self.facts.update(
            {
                "消息标识": str(row.normalized.get("message_id")),
                "来源回复状态": str(row.normalized.get("reply_status", "unknown")),
            }
        )
        if any(
            row.normalized.get(key) != original.normalized.get(key)
            for key in ("body", "sent_at", "order_id")
        ):
            return self.result(
                "awaiting_source",
                "同标识消息的原文、时间或关联订单发生变化，不能证明原消息已回复。",
            )
        stamp = message_reply_time(row, batch, self.now, scope.max_age_hours)
        if row.id == original.id or not self.fresh([stamp, batch.exported_at], scope):
            return self.result(
                "awaiting_source",
                "需要新的消息来源、有效回复状态时间和导出时间；本地草稿不作为已发送证据。",
            )
        status = row.normalized.get("reply_status", "unknown")
        if status not in {"replied", "awaiting_reply"}:
            return self.result("awaiting_source", "来源未明确是否已回复。")
        self.facts["回复凭据（来源自报）"] = str(row.normalized.get("reply_evidence", ""))
        assert stamp is not None
        state: RecheckState = "resolved" if status == "replied" else "still_anomalous"
        return self.result(
            state,
            "新来源声明已回复并提供凭据；外部发送未经系统核验。"
            if state == "resolved"
            else "新来源仍明确待回复。",
            [stamp],
        )

    def margin(self, scope: OperationScope) -> TaskRecheck:
        original_orders = [(r, b) for r, b in self.original if b.kind == "orders"]
        original_products = [(r, b) for r, b in self.original if b.kind == "products"]
        skus = {row.normalized.get("sku") for row, _ in self.original}
        if len(skus) != 1 or len(original_products) != 1:
            return self.result("awaiting_source", "原SKU或成本依据不完整。")
        sku = next(iter(skus))
        orders = [
            item for item in self.records(OrderLine, scope, scope.channel) if item[0].sku == sku
        ]
        products = [item for item in self.records(Product, scope) if item[0].sku == sku]
        self.sources = [reference(row, batch) for _, row, batch in [*orders, *products]]
        original_keys = {
            (row.normalized.get("order_id"), row.normalized.get("line_id"))
            for row, _ in original_orders
        }
        current_keys = {
            (order.order_id, order.line_id)
            for order, _, _ in orders
            if order.status in PAID_STATUSES and order.currency == scope.currency
        }
        if not original_keys <= current_keys:
            return self.result(
                "awaiting_source",
                "原订单行未完整保留在同窗口、SKU、币种的已支付范围，不能据此解除低毛利。",
            )
        if (
            len(products) != 1
            or products[0][2].source_channel != original_products[0][1].source_channel
        ):
            return self.result("awaiting_source", "当前采购成本缺失或成本来源渠道改变。")
        original_ids = {row.id for row, _ in self.original}
        changes = [
            batch.exported_at
            for _, row, batch in [*orders, *products]
            if row.id not in original_ids
        ]
        if not self.fresh(changes, scope):
            return self.result(
                "awaiting_source",
                "需要同对象的新成本或订单依据；全部变化来源须有晚于异常发现及人工操作的有效导出时间。",
            )
        profit = calculate(orders, products, scope, self.revision, self.now)
        metric = profit.summary
        self.facts.update(
            {
                "SKU": str(sku),
                "币种": scope.currency,
                "订单起点(含)": scope.start_at.isoformat(),
                "订单终点(不含)": scope.end_at.isoformat(),
                "净销售额": str(metric.sales),
                "采购成本估算": str(metric.cost),
                "商品毛利估算": str(metric.gross_profit),
                "原阈值(%)": str(scope.max_margin_percent),
                "费用口径": "平台/广告/物流/税费未完整归集，净利润未知。",
            }
        )
        if (
            not profit.ranking_available
            or metric.purchased_quantity < scope.min_quantity
            or metric.sales is None
            or metric.sales <= 0
            or metric.gross_profit is None
        ):
            return self.result(
                "awaiting_source", "金额、币种、购买量或毛利口径不完整，无法判定原低毛利已解除。"
            )
        with localcontext() as context:
            context.prec = 40
            resolved = metric.gross_profit * 100 > scope.max_margin_percent * metric.sales
        return self.result(
            "resolved" if resolved else "still_anomalous",
            "新来源下未舍入的商品毛利率高于原阈值；仍属当前成本回推估算。"
            if resolved
            else "新来源下未舍入商品毛利率仍不高于原阈值。",
            [stamp for stamp in changes if stamp is not None],
        )
