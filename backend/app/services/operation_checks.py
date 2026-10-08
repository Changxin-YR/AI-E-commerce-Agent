from dataclasses import dataclass
from datetime import datetime

from app.models.imports import CustomerMessage, ImportBatch, ImportRow
from app.repositories.analytics import OrderEvidence, ProductEvidence
from app.repositories.inventory import InventoryEvidence
from app.schemas.analytics import SourceReference
from app.schemas.operations import Branch, Finding, OperationScope
from app.services.inventory import assess_snapshot
from app.services.profit_calculation import PAID_STATUSES, calculate, reference, utc_text


@dataclass
class CheckResult:
    branches: list[Branch]
    findings: list[Finding]
    sources: list[SourceReference]
    valid_until: datetime | None


@dataclass
class BranchResult:
    branch: Branch
    findings: list[Finding]
    valid_until: datetime | None = None


def check_products(products: list[ProductEvidence]) -> Branch:
    missing_facts = sum(not p.facts.strip() for p, _, _ in products)
    branch = Branch(
        name="商品事实",
        status="checked" if products else "not_checked",
        count=len(products),
        reason=f"已读取 {len(products)} 个商品；缺参数 {missing_facts} 个。"
        if products
        else "缺商品，请先导入；Listing 质量未检查。",
    )
    return branch


def check_orders(orders: list[OrderEvidence]) -> BranchResult:
    findings: list[Finding] = []
    unknown = sum(o.fulfillment_status == "unknown" for o, _, _ in orders)
    for order, row, batch in orders:
        if order.status in PAID_STATUSES and order.fulfillment_status in {"unfulfilled", "partial"}:
            findings.append(
                Finding(
                    kind="order_review",
                    object_label=f"{order.order_id} / {order.line_id}",
                    title="核对来源订单的履约状态",
                    severity="review",
                    basis="所选订单时间窗内，文件记录已支付订单未履约或部分履约；当前平台状态待核对。",
                    advice="查看来源后到原平台核对，并在本地记录处理结果。",
                    impact="可能仍需履约；订单时间和文件状态不能证明当前超时或物流延误。",
                    facts={
                        "SKU": order.sku,
                        "文件订单状态": order.status,
                        "文件履约状态": order.fulfillment_status,
                        "订单时间": utc_text(order.ordered_at),
                    },
                    sources=[reference(row, batch)],
                )
            )
    branch = Branch(
        name="订单履约核对",
        status=("partial" if unknown else "checked") if orders else "not_checked",
        count=len(orders),
        reason=(
            f"已读取 {len(orders)} 行；履约状态未知 {unknown} 行。仅核对来源状态，不判当前超时。"
        )
        if orders
        else "所选渠道、身份和时间窗没有订单。",
    )
    return BranchResult(branch, findings)


def check_inventory(
    inventory: list[InventoryEvidence], scope: OperationScope, now: datetime
) -> BranchResult:
    findings: list[Finding] = []
    stocks = [assess_snapshot(item, now, scope.max_age_hours) for item in inventory]
    expiries: list[datetime] = []
    for stock in stocks:
        if stock.status != "unknown":
            expiries.append(datetime.fromisoformat(stock.valid_until).replace(tzinfo=None))
        if stock.status == "low":
            findings.append(
                Finding(
                    kind="low_inventory",
                    object_label=stock.sku,
                    title="核对低于安全阈值的库存",
                    severity="attention",
                    basis=stock.reason,
                    advice="核对实际库存与补货需求；不同渠道可能共用库存。",
                    impact="快照提示可售偏低，需在有效期内核对；未执行采购或库存调整。",
                    facts={
                        "快照可售": str(stock.available),
                        "安全阈值": str(stock.safety_threshold),
                        "快照时间": stock.snapshot_at,
                        "渠道": stock.channel,
                    },
                    sources=[stock.source],
                    valid_until=stock.valid_until,
                )
            )
    unknown_stock = sum(s.status == "unknown" for s in stocks)
    branch = Branch(
        name="库存阈值",
        status=("partial" if unknown_stock else "checked") if stocks else "not_checked",
        count=len(stocks),
        reason=(
            f"读取 {len(stocks)} 个快照；过期或未知 {unknown_stock} 个。"
            f"时效 {scope.max_age_hours} 小时。"
        )
        if stocks
        else "库存未知 / 未检查；此渠道没有库存快照。",
    )
    return BranchResult(branch, findings, min(expiries) if expiries else None)


def check_messages(messages: list[tuple[CustomerMessage, ImportRow, ImportBatch]]) -> BranchResult:
    findings: list[Finding] = []
    for msg, row, batch in messages:
        findings.append(
            Finding(
                kind="message_review",
                object_label=msg.message_id,
                title="核对消息是否仍需回复",
                severity="review",
                basis="已导入客户消息；文件没有外部回复状态。",
                advice="在客服工作台查看原文并核对是否需要回复；敏感请求转人工。",
                impact="需要卖家核对回复进度；本地草稿和存档均不能证明已发送。",
                facts={"来源语言": msg.language, "渠道": msg.channel},
                sources=[reference(row, batch)],
            )
        )
    branch = Branch(
        name="消息回复核对",
        status="partial" if messages else "not_checked",
        count=len(messages),
        reason=f"读取 {len(messages)} 条消息；外部是否已回复未知，形成核对候选。"
        if messages
        else "缺消息，未检查；可导入或手工录入。",
    )
    return BranchResult(branch, findings)


def check_profit(
    orders: list[OrderEvidence],
    products: list[ProductEvidence],
    scope: OperationScope,
    revision: int,
    now: datetime,
) -> BranchResult:
    findings: list[Finding] = []
    profit = calculate(orders, products, scope, revision, now)
    metrics = {m.sku: m for m in profit.skus}
    grouped_refs: dict[str, dict[int, SourceReference]] = {}
    for line in profit.lines:
        if line.included:
            for ref in [line.source, line.cost_source]:
                if ref is not None:
                    grouped_refs.setdefault(line.sku, {})[ref.row_id] = ref
    for sku in profit.candidates:
        metric = metrics[sku]
        refs = grouped_refs[sku]
        findings.append(
            Finding(
                kind="low_margin",
                object_label=sku,
                title="核对已知费用下的低毛利商品",
                severity="attention",
                basis=(
                    f"购买量达到 {scope.min_quantity}，"
                    f"未舍入的估算毛利率不高于 {scope.max_margin_percent}%。"
                ),
                advice="展开订单和成本来源，补齐费用并核对采购成本。",
                impact=profit.cost_basis + "平台、广告、物流和税费缺失，不是净利润。",
                facts={
                    "币种": scope.currency,
                    "原购买量": str(metric.purchased_quantity),
                    "净销售额": str(metric.sales),
                    "当前采购成本": str(metric.cost),
                    "估算毛利": str(metric.gross_profit),
                    "估算毛利率(%)": str(metric.margin_percent),
                    "公式": profit.formula,
                    "订单起点(含)": scope.start_at.isoformat(),
                    "订单终点(不含)": scope.end_at.isoformat(),
                },
                sources=list(refs.values()),
            )
        )
    branch = Branch(
        name="已知毛利",
        status="checked" if profit.ranking_available else "not_checked",
        count=profit.summary.line_count,
        reason=profit.answer,
    )
    return BranchResult(branch, findings)


def check_data(
    orders: list[OrderEvidence],
    products: list[ProductEvidence],
    inventory: list[InventoryEvidence],
    messages: list[tuple[CustomerMessage, ImportRow, ImportBatch]],
    scope: OperationScope,
    revision: int,
    now: datetime,
) -> CheckResult:
    stock = check_inventory(inventory, scope, now)
    results = [
        check_orders(orders),
        stock,
        check_messages(messages),
        check_profit(orders, products, scope, revision, now),
    ]
    branches = [check_products(products), *(result.branch for result in results)]
    findings = [finding for result in results for finding in result.findings]
    branches.extend(
        [
            Branch(name=name, status="not_checked", count=0, reason=reason)
            for name, reason in [
                ("实时物流", "无已授权的实时轨迹，未检查。"),
                ("平台同步", "文件模式；平台同步待接入。"),
                ("营销与广告", "无广告和营销数据，未检查。"),
                ("销售变化", "本次仅检查指定时间窗，未执行跨期可比分析。"),
            ]
        ]
    )
    sources = {
        row.id: reference(row, batch)
        for _, row, batch in [*orders, *products, *inventory, *messages]
    }
    return CheckResult(branches, findings, list(sources.values()), stock.valid_until)
