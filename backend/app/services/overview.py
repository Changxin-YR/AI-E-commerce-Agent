import hashlib
import json
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.imports import CustomerMessage, InventorySnapshot
from app.models.overview import OverviewReport
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.overview import (
    CurrencyGroup,
    MessageEvidence,
    OverviewPage,
    OverviewResult,
    OverviewSave,
    OverviewSaved,
    OverviewScope,
    ShopOverview,
    TaskLink,
)
from app.services.import_groups import require_import_coverage
from app.services.inventory import assess_snapshot
from app.services.overview_calculation import change, midnight, period, totals
from app.services.profit_calculation import reference, utc_text

LIMITATIONS = [
    "仅覆盖所选店铺、数据身份、币种和时间窗的当前导入投影；不是实时或全渠道统计。",
    "按各店铺登记的平台与市场分组；市场是店铺设置，不是订单收件国家。",
    "日期按所选时区计算，含起点、不含终点；退款归原订单时间，不是退款发生日。",
    "采购成本取当前商品记录，历史成本生效日未知；平台、广告、物流、税费等未归集，净利润未结算。",
    "库存为分析当时的当前快照，不是历史区间库存；不同渠道独立核验，不合计库存数量。",
    "消息按发送日期筛选，当前没有可靠的回复状态，消息条数不等于待回复条数。",
    "待办只展示当时最近 50 条未结事项的状态，打开工作台后重新核验；本页不创建异常或自动执行。",
    "低毛利与库存阈值为本页独立检查口径；经营规则页约束仍用于今日运营与 Agent。",
]


class OverviewService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.overview

    def _shops(self, owner: int, ids: list[int]) -> list[Shop]:
        self.uow.identity.lock_user(owner)
        shops = [self.uow.identity.get_shop(owner, shop, lock=True) for shop in sorted(ids)]
        if any(shop is None for shop in shops):
            raise NotFoundError()
        return [shop for shop in shops if shop is not None]

    def calculate(self, owner: int, scope: OverviewScope) -> OverviewResult:
        shops = self._shops(owner, scope.shop_ids)
        now = utc_now()
        output: list[ShopOverview] = []
        count = 0
        for shop in shops:
            item, used = self._shop_result(owner, shop, scope, now)
            count += used
            if count > 10000:
                raise BusinessError(
                    "range_too_large", "总览来源合计超过 10000 行，请减少店铺或缩小范围", 422
                )
            output.append(item)
        aggregate = totals(output)
        expiries = [
            datetime.fromisoformat(item.valid_until).replace(tzinfo=None)
            for shop in output
            for item in shop.inventory
            if item.status != "unknown"
        ]
        # A future snapshot becomes eligible at its own timestamp; expire the old unknown result.
        expiries += [
            datetime.fromisoformat(item.snapshot_at).replace(tzinfo=None)
            for shop in output
            for item in shop.inventory
            if datetime.fromisoformat(item.snapshot_at).replace(tzinfo=None) > now
        ]
        days = (scope.end_date - scope.start_date).days
        label = {1: "日报", 7: "七日周报", 30: "三十日月报"}.get(days, "自选区间摘要")
        if scope.start_date.day == scope.end_date.day == 1 and 28 <= days <= 31:
            label = "自然月报"
        elif days == 7 and scope.start_date.weekday() == 0:
            label = "自然周报"
        summary = [
            f"{label} · {scope.start_date} 至 {scope.end_date}（终点不含）· {scope.timezone}",
            f"所选 {len(shops)} 家店铺；数据身份 {scope.data_identity}；本地规则生成。",
        ]
        for total in aggregate:
            sales_text = str(total.sales) if total.sales is not None else "未知/不完整"
            summary.append(
                f"{total.currency}：可核对净销售额 {sales_text}；"
                f"已知子集 {total.known_sales}；已观察订单 {total.observed_orders}。"
            )
        summary.append("实际净利润、营销效果和可靠待回复数未获取；请逐店查看缺口与来源。")
        return OverviewResult(
            scope=scope,
            calculated_at=utc_text(now),
            valid_until=utc_text(min(expiries)) if expiries else None,
            shops=output,
            totals=aggregate,
            summary=summary,
            limitations=LIMITATIONS,
        )

    def _shop_result(
        self, owner: int, shop: Shop, scope: OverviewScope, now: datetime
    ) -> tuple[ShopOverview, int]:
        assert scope.comparison_start is not None and scope.comparison_end is not None
        start, end = (
            midnight(scope.start_date, scope.timezone),
            midnight(scope.end_date, scope.timezone),
        )
        prior_start, prior_end = (
            midnight(scope.comparison_start, scope.timezone),
            midnight(scope.comparison_end, scope.timezone),
        )
        require_import_coverage(
            self.uow,
            owner,
            shop.id,
            scope.data_identity,
            {"orders", "products", "inventory", "messages"},
        )
        orders = self.uow.analytics.orders(
            owner,
            shop.id,
            start.replace(tzinfo=None),
            end.replace(tzinfo=None),
            scope.data_identity,
        )
        previous = self.uow.analytics.orders(
            owner,
            shop.id,
            prior_start.replace(tzinfo=None),
            prior_end.replace(tzinfo=None),
            scope.data_identity,
        )
        products = (
            self.uow.analytics.products(owner, shop.id, {o.sku for o, _, _ in orders + previous})
            if orders or previous
            else []
        )
        inventory = self.uow.operations.records(
            InventorySnapshot, owner, shop.id, scope.data_identity
        )
        messages = self.uow.operations.records(CustomerMessage, owner, shop.id, scope.data_identity)
        used = len(orders) + len(previous) + len(products) + len(inventory) + len(messages)
        if used > 10000:
            raise BusinessError("range_too_large", "总览来源超过 10000 行，请缩小范围", 422)
        currencies: list[str] = list(scope.currencies) or sorted(
            {o.currency for o, _, _ in orders + previous} or {shop.currency}
        )
        groups: list[CurrencyGroup] = []
        refs = {}
        for currency in currencies:
            current = period(
                [o for o in orders if o[0].currency == currency],
                products,
                scope,
                currency,
                scope.start_date,
                scope.end_date,
                shop.data_revision,
                now,
            )
            prior = period(
                [o for o in previous if o[0].currency == currency],
                products,
                scope,
                currency,
                scope.comparison_start,
                scope.comparison_end,
                shop.data_revision,
                now,
            )
            delta, percent = change(current.analysis.summary.sales, prior.analysis.summary.sales)
            groups.append(
                CurrencyGroup(
                    currency=currency,
                    current=current,
                    comparison=prior,
                    sales_change=delta,
                    sales_change_percent=percent,
                )
            )
            for result in [current, prior]:
                for line in result.analysis.lines:
                    for ref in [line.source, line.cost_source]:
                        if ref is not None:
                            refs[ref.row_id] = ref
        snapshots = [assess_snapshot(item, now, scope.max_age_hours) for item in inventory]
        selected_messages = [
            MessageEvidence(
                message_id=m.message_id,
                channel=m.channel,
                sent_at=utc_text(m.sent_at),
                source=reference(row, batch),
            )
            for m, row, batch in messages
            if start.replace(tzinfo=None) <= m.sent_at < end.replace(tzinfo=None)
        ]
        for source in [i.source for i in snapshots] + [m.source for m in selected_messages]:
            refs[source.row_id] = source
        tasks = self.repo.tasks(owner, shop.id, scope.data_identity)
        return ShopOverview(
            shop_id=shop.id,
            shop_name=shop.name,
            platform=shop.platform,
            market=shop.market,
            source_revision=shop.data_revision,
            currencies=groups,
            inventory=snapshots,
            inventory_low=sum(i.status == "low" for i in snapshots)
            if any(i.status != "unknown" for i in snapshots)
            else None,
            inventory_unknown=sum(i.status == "unknown" for i in snapshots),
            messages=selected_messages,
            message_count=len(selected_messages) if selected_messages else None,
            tasks=[
                TaskLink(id=t.id, kind=t.kind, status=t.status, source_status="需打开重新核验")
                for t in tasks[:50]
            ],
            tasks_has_more=len(tasks) > 50,
            sources=sorted(refs.values(), key=lambda r: r.row_id),
        ), used

    def save(self, owner: int, data: OverviewSave) -> OverviewSaved:
        return self._save(owner, data.scope, data.request_id, data.expected_revisions)

    def save_scheduled(self, owner: int, scope: OverviewScope, request_id: UUID) -> OverviewSaved:
        """A confirmed local report schedule authorizes saving the current snapshot."""
        return self._save(owner, scope, request_id, None)

    def _save(
        self,
        owner: int,
        scope: OverviewScope,
        request_id: UUID,
        expected_revisions: dict[int, int] | None,
    ) -> OverviewSaved:
        self._shops(owner, scope.shop_ids)
        content: dict[str, Any] = {
            "scope": scope.model_dump(mode="json"),
            "expected_revisions": {str(key): value for key, value in expected_revisions.items()}
            if expected_revisions is not None
            else None,
        }
        content["scope"]["max_margin_percent"] = format(scope.max_margin_percent.normalize(), "f")
        digest = hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()
        existing = self.repo.by_request(owner, str(request_id))
        if existing:
            if existing.request_hash != digest:
                raise ConflictError("请求标识已用于其他摘要范围")
            return self._output(existing)
        result = self.calculate(owner, scope)
        revisions = {shop.shop_id: shop.source_revision for shop in result.shops}
        if expected_revisions is not None and revisions != expected_revisions:
            raise ConflictError("来源已变化，请重新生成后保存摘要")
        report = OverviewReport(
            owner_id=owner,
            request_id=str(request_id),
            request_hash=digest,
            scope=scope.model_dump(mode="json"),
            snapshot=result.model_dump(mode="json"),
            status="current",
            valid_until=datetime.fromisoformat(result.valid_until).replace(tzinfo=None)
            if result.valid_until
            else None,
        )
        self.repo.add(
            report, scope.shop_ids, {s.batch_id for shop in result.shops for s in shop.sources}
        )
        self.uow.record_event(owner, "overview.saved", "overview", report.id)
        response = self._output(report)
        self.uow.commit()
        return response

    def _output(self, report: OverviewReport, include_snapshot: bool = True) -> OverviewSaved:
        if report.status == "current" and report.valid_until and utc_now() >= report.valid_until:
            report.status = "stale"
        return OverviewSaved(
            id=report.id,
            status=report.status,
            created_at=utc_text(report.created_at),
            scope=OverviewScope.model_validate(report.scope),
            snapshot=OverviewResult.model_validate(report.snapshot)
            if include_snapshot and report.snapshot
            else None,
        )

    def get(self, owner: int, report_id: int) -> OverviewSaved:
        self.uow.identity.lock_user(owner)
        report = self.repo.get(owner, report_id)
        if report is None:
            raise NotFoundError()
        output = self._output(report)
        self.uow.commit()
        return output

    def page(self, owner: int, before: int | None) -> OverviewPage:
        self.uow.identity.lock_user(owner)
        reports = self.repo.page(owner, before)
        output = OverviewPage(
            items=[self._output(r, False) for r in reports[:20]],
            next_cursor=reports[19].id if len(reports) > 20 else None,
        )
        self.uow.commit()
        return output

    def clear(self, owner: int, report_id: int) -> OverviewSaved:
        self.uow.identity.lock_user(owner)
        report = self.repo.get(owner, report_id)
        if report is None:
            raise NotFoundError()
        if report.status != "cleared":
            self.repo.clear(report)
            self.uow.record_event(owner, "overview.cleared", "overview", report.id)
        output = self._output(report)
        self.uow.commit()
        return output
