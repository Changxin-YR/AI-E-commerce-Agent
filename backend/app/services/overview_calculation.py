from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal, localcontext
from zoneinfo import ZoneInfo

from app.core.errors import BusinessError
from app.repositories.analytics import OrderEvidence, ProductEvidence
from app.schemas.analytics import AnalysisInput
from app.schemas.overview import CurrencyTotal, OverviewScope, PeriodMetrics, ShopOverview
from app.services.profit_calculation import PAID_STATUSES, calculate, reference


def midnight(value: date, timezone: str) -> datetime:
    local = datetime.combine(value, time(), ZoneInfo(timezone))
    utc = local.astimezone(UTC)
    if utc.astimezone(ZoneInfo(timezone)).replace(tzinfo=None) != local.replace(tzinfo=None):
        raise BusinessError("invalid_local_date", "此时区的日期起点不存在，请调整范围", 422)
    return utc


def change(
    current: Decimal | None, previous: Decimal | None
) -> tuple[Decimal | None, Decimal | None]:
    if current is None or previous is None:
        return None, None
    with localcontext() as context:
        context.prec = 40
        delta = current - previous
        percent = (delta * 100 / previous).quantize(Decimal("0.01")) if previous > 0 else None
        return delta, percent


def period(
    orders: list[OrderEvidence],
    products: list[ProductEvidence],
    scope: OverviewScope,
    currency: str,
    start: date,
    end: date,
    revision: int,
    now: datetime,
) -> PeriodMetrics:
    start_at, end_at = midnight(start, scope.timezone), midnight(end, scope.timezone)
    if end_at - start_at > timedelta(days=366):
        raise BusinessError(
            "range_too_large", "时区换算后的统计窗超过 366 天，请缩小一个日历日后重试", 422
        )
    analysis_scope = AnalysisInput.model_validate(
        {
            "start_at": start_at,
            "end_at": end_at,
            "timezone": scope.timezone,
            "currency": currency,
            "data_identity": scope.data_identity,
            "intent": "low_margin",
            "min_quantity": scope.min_quantity,
            "max_margin_percent": scope.max_margin_percent,
        }
    )
    result = calculate(orders, products, analysis_scope, revision, now)
    paid = [order for order in orders if order[0].status in PAID_STATUSES]
    known = [order[0].refund for order in paid if order[0].refund is not None]
    pending = [order for order in paid if order[0].fulfillment_status in {"unfulfilled", "partial"}]
    unknown = sum(order[0].fulfillment_status == "unknown" for order in paid)
    with localcontext() as context:
        context.prec = 40
        refund_sum = sum(known, Decimal(0))
    return PeriodMetrics(
        analysis=result,
        orders=len({o[0].order_id for o in paid}) if orders else None,
        refunds=refund_sum if paid and len(known) == len(paid) else None,
        known_refunds=refund_sum,
        refund_known_lines=len(known),
        pending_orders=len({o[0].order_id for o in pending}) if paid and not unknown else None,
        unknown_fulfillment_lines=unknown,
        pending_sources=[reference(row, batch) for _, row, batch in pending],
        top_skus=[
            s.sku
            for s in sorted(result.skus, key=lambda s: (-s.purchased_quantity, s.sku or ""))[:5]
            if s.sku
        ],
    )


def complete(values: list[Decimal | None]) -> Decimal | None:
    return (
        sum((value for value in values if value is not None), Decimal(0))
        if values and all(value is not None for value in values)
        else None
    )


def totals(shops: list[ShopOverview]) -> list[CurrencyTotal]:
    result: list[CurrencyTotal] = []
    currencies = sorted({group.currency for shop in shops for group in shop.currencies})
    with localcontext() as context:
        context.prec = 40
        for currency in currencies:
            groups = [
                (shop.shop_id, group)
                for shop in shops
                for group in shop.currencies
                if group.currency == currency
            ]
            current = [g.current for _, g in groups]
            sales = complete([p.analysis.summary.sales for p in current])
            previous = complete([g.comparison.analysis.summary.sales for _, g in groups])
            delta, percent = change(sales, previous)
            result.append(
                CurrencyTotal(
                    currency=currency,
                    shop_ids=[s for s, _ in groups],
                    sales=sales,
                    known_sales=sum(
                        (p.analysis.summary.known_sales_subtotal for p in current), Decimal(0)
                    ),
                    comparison_sales=previous,
                    sales_change=delta,
                    sales_change_percent=percent,
                    gross_profit=complete([p.analysis.summary.gross_profit for p in current]),
                    known_gross_profit=sum(
                        (p.analysis.summary.known_gross_subtotal for p in current), Decimal(0)
                    ),
                    refunds=complete([p.refunds for p in current]),
                    known_refunds=sum((p.known_refunds for p in current), Decimal(0)),
                    observed_orders=sum(p.orders or 0 for p in current),
                    warnings=[
                        "仅加总下列店铺中此币种的已导入行；未覆盖店铺和空窗口不能证明零销售。",
                        "订单数在每店每币种内去重；跨币种订单可能出现在多个分组，不可再加总。",
                        "利润为当前采购成本估算的商品毛利；实际净利润与营销表现未获取。",
                    ],
                )
            )
    return result
