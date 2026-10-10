from datetime import UTC, datetime
from decimal import Decimal, localcontext

from app.models.imports import ImportBatch, ImportRow
from app.models.order_costs import OrderCostRevision
from app.repositories.analytics import OrderEvidence, ProductEvidence
from app.schemas.analytics import (
    AnalysisInput,
    AnalysisResult,
    LineResult,
    MetricSummary,
    SourceReference,
)
from app.schemas.order_costs import CostVersion

PAID_STATUSES = {"paid", "partially_refunded", "refunded"}
FORMULA = (
    "行净销售额 = 数量 × 折扣前成交单价 − 行折扣 − 行退款；"
    "已知商品毛利 = 行净销售额 − 数量 × 当前单位采购成本。"
)
COST_BASIS = (
    "当前商品采购成本估算历史订单，成本生效日未知；"
    "当前成本回推估算，非订单时点实际采购成本。"
    "来源导入/导出时间不等于成本生效时间。"
    "退款不恢复采购成本或库存，购买数量不是退货后的净销量。"
)
FEE_GAPS = ["平台佣金", "广告", "物流与履约", "税费", "其他费用"]
HISTORICAL_BASIS = (
    "按卖家提供并确认的订单行历史单位成本计算商品毛利；凭据未经系统独立核验。"
    "缺少有效凭据时成本未知；退款不恢复采购成本或库存。"
)


def cost_version(record: OrderCostRevision) -> CostVersion:
    return CostVersion(
        id=record.id,
        version=record.version,
        action=record.action,
        status=record.status,
        unit_cost=record.unit_cost,
        currency=record.currency,
        evidence_ref=record.evidence_ref,
        evidence_at=utc_text(record.evidence_at) if record.evidence_at else None,
        recorded_at=utc_text(record.created_at),
    )


def utc_text(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat()


def reference(row: ImportRow, batch: ImportBatch) -> SourceReference:
    return SourceReference(
        origin=batch.origin,
        batch_id=batch.id,
        row_id=row.id,
        row_number=row.row_number,
        filename=batch.filename,
        sheet_name=batch.sheet_name,
        exported_at=utc_text(batch.exported_at) if batch.exported_at else None,
        imported_at=utc_text(batch.created_at),
        data_identity=batch.data_identity,
    )


def calculate_line(
    evidence: OrderEvidence,
    product: ProductEvidence | None,
    scope: AnalysisInput,
    historical: OrderCostRevision | None = None,
) -> LineResult:
    order, row, batch = evidence
    included = order.status in PAID_STATUSES and order.currency == scope.currency
    gaps: list[str] = []
    sales = cost = gross = None
    cost_source = None
    unit_cost = None
    history = None
    if order.status not in PAID_STATUSES:
        gaps.append("取消、未付款或测试订单不计入已支付销售")
    if order.currency != scope.currency:
        gaps.append("非所选币种，不加总且未换汇")
    if included:
        if order.discount is None:
            gaps.append("缺行折扣")
        if order.refund is None:
            gaps.append("缺行退款")
        if order.discount is not None and order.refund is not None:
            sales = order.quantity * order.unit_price - order.discount - order.refund
        if scope.cost_mode == "seller_history":
            if historical is None or historical.status != "active":
                gaps.append("缺卖家确认的有效订单行历史成本凭据")
            else:
                history = cost_version(historical)
                unit_cost = historical.unit_cost
                if historical.currency != scope.currency:
                    gaps.append("历史成本币种不同，缺已确认汇率")
                elif unit_cost is not None:
                    cost = order.quantity * unit_cost
        elif product is None:
            gaps.append("缺商品采购成本")
        else:
            item, cost_row, cost_batch = product
            cost_source = reference(cost_row, cost_batch)
            unit_cost = item.unit_cost
            if cost_batch.data_identity != scope.data_identity:
                gaps.append("商品成本与订单数据身份不同")
            elif item.unit_cost is None:
                gaps.append("缺单位采购成本")
            elif item.cost_currency != scope.currency:
                gaps.append("采购成本币种不同，缺已确认汇率")
            else:
                cost = order.quantity * item.unit_cost
        if sales is not None and cost is not None:
            gross = sales - cost
        if order.status in {"refunded", "partially_refunded"} or order.refund:
            gaps.append("缺退货数量：数量为原购买量，采购成本不恢复")
    return LineResult(
        order_id=order.order_id,
        line_id=order.line_id,
        sku=order.sku,
        status=order.status,
        ordered_at=utc_text(order.ordered_at),
        currency=order.currency,
        quantity=order.quantity,
        included=included,
        unit_price=order.unit_price,
        discount=order.discount,
        refund=order.refund,
        sales=sales,
        cost=cost,
        gross_profit=gross,
        gaps=gaps,
        source=reference(row, batch),
        cost_source=cost_source,
        unit_cost=unit_cost,
        historical_cost=history,
    )


def aggregate(lines: list[LineResult], sku: str | None = None) -> MetricSummary:
    sales = [line.sales for line in lines if line.sales is not None]
    costs = [line.cost for line in lines if line.cost is not None]
    profits = [line.gross_profit for line in lines if line.gross_profit is not None]
    zero = Decimal(0)
    sales_sum, cost_sum, gross_sum = sum(sales, zero), sum(costs, zero), sum(profits, zero)
    complete_sales = sales_sum if lines and len(sales) == len(lines) else None
    complete_cost = cost_sum if lines and len(costs) == len(lines) else None
    complete_gross = gross_sum if lines and len(profits) == len(lines) else None
    margin = None
    if complete_gross is not None and complete_sales is not None and complete_sales > 0:
        margin = (100 * complete_gross / complete_sales).quantize(Decimal("0.01"))
    return MetricSummary(
        sku=sku,
        line_count=len(lines),
        purchased_quantity=sum(line.quantity for line in lines),
        sales=complete_sales,
        known_sales_subtotal=sales_sum,
        sales_known_lines=len(sales),
        cost=complete_cost,
        known_cost_subtotal=cost_sum,
        cost_known_lines=len(costs),
        gross_profit=complete_gross,
        known_gross_subtotal=gross_sum,
        gross_known_lines=len(profits),
        margin_percent=margin,
    )


def calculate(
    orders: list[OrderEvidence],
    products: list[ProductEvidence],
    scope: AnalysisInput,
    revision: int,
    calculated_at: datetime,
    historical_costs: dict[int, OrderCostRevision] | None = None,
) -> AnalysisResult:
    # Numeric(18,4) × quantity up to 1e6, summed across <=10000 lines; 40 digits is ample.
    with localcontext() as context:
        context.prec = 40
        return _calculate(orders, products, scope, revision, calculated_at, historical_costs or {})


def _calculate(
    orders: list[OrderEvidence],
    products: list[ProductEvidence],
    scope: AnalysisInput,
    revision: int,
    calculated_at: datetime,
    historical_costs: dict[int, OrderCostRevision],
) -> AnalysisResult:
    items = {item.sku: (item, row, batch) for item, row, batch in products}
    matching = [entry for entry in orders if entry[2].data_identity == scope.data_identity]
    lines = [
        calculate_line(entry, items.get(entry[0].sku), scope, historical_costs.get(entry[1].id))
        for entry in matching
    ]
    included = [line for line in lines if line.included]
    summary = aggregate(included)
    groups: dict[str, list[LineResult]] = {}
    for line in included:
        groups.setdefault(line.sku, []).append(line)
    skus = [aggregate(group, sku) for sku, group in sorted(groups.items())]
    mixed_currency = any(
        line.currency != scope.currency and line.status in PAID_STATUSES for line in lines
    )
    complete = bool(included) and summary.gross_profit is not None and not mixed_currency
    warnings = [
        "费用未完整归集，不能推断精确净利润。",
        "费用待核：人工费用与平台账单须先核对重复凭据；商品毛利未扣费用，店铺费用未分摊。",
        "时间窗按订单时间筛选，包含起点、不含终点；退款归原订单时间。",
    ]
    if not included:
        warnings.append("没有符合所选口径的已支付订单行，请导入数据或调整范围。")
    if len(matching) != len(orders):
        warnings.append(f"已排除其他数据身份的 {len(orders) - len(matching)} 行。")
    if mixed_currency:
        warnings.append("范围内存在其他币种，请分别选择币种查看；暂停完整毛利排行。")
    if summary.gross_known_lines < len(included):
        warnings.append(
            "存在缺失成本、折扣、退款或币种不一致，仅展示可验证子集，暂停完整毛利排行。"
        )
    candidates: list[str] = []
    if scope.intent == "low_margin":
        if complete:
            # Compare unrounded values; rounded percentages are display-only.
            candidates = [
                item.sku
                for item in skus
                if item.sku is not None
                and item.purchased_quantity >= scope.min_quantity
                and item.sales is not None
                and item.sales > 0
                and item.gross_profit is not None
                and item.gross_profit * 100 <= scope.max_margin_percent * item.sales
            ]
            answer = (
                f"按购买数量 ≥ {scope.min_quantity}、"
                f"估算毛利率 ≤ {scope.max_margin_percent}% 筛选，"
                f"命中 {len(candidates)} 个 SKU；"
                "零或负销售额的 SKU 请查看明细，无法定义毛利率。"
            )
        else:
            answer = "数据不足，无法完整判断哪些商品销量高但已知毛利低，请先补齐明细缺口。"
    elif scope.intent == "sales":
        candidates = [
            item.sku
            for item in sorted(skus, key=lambda item: (-item.purchased_quantity, item.sku or ""))[
                :5
            ]
            if item.sku
        ]
        answer = (
            f"所选币种和数据身份内，按原购买数量排列前 {len(candidates)} 个 SKU；"
            "退款未扣退货件数，不能视为净销量。"
        )
    else:
        answer = (
            f"命中 {len(included)} 个已支付订单行，原购买数量 {summary.purchased_quantity}；"
            f"可核对净销售额 {summary.sales_known_lines} 行，"
            f"已知商品毛利 {summary.gross_known_lines} 行。"
        )
    return AnalysisResult(
        calculation_version=2,
        scope=scope,
        source_revision=revision,
        calculated_at=utc_text(calculated_at),
        formula=FORMULA
        if scope.cost_mode == "current_estimate"
        else FORMULA.replace("当前单位采购成本", "卖家确认的订单行历史单位成本"),
        cost_basis=COST_BASIS if scope.cost_mode == "current_estimate" else HISTORICAL_BASIS,
        fee_gaps=FEE_GAPS,
        warnings=warnings,
        summary=summary,
        skus=skus,
        lines=lines,
        ranking_available=complete,
        answer=answer,
        candidates=candidates,
    )
