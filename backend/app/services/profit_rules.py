from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from app.schemas.profit import (
    FEE_LABELS,
    FeeResult,
    ScenarioInput,
    ScenarioResult,
    SensitivityPoint,
    StudyInput,
    StudyResult,
)

RULE_VERSION = "unit-assumptions-v1"
FORMULA = (
    "采购毛利 = 候选售价 − 单件采购成本；已填费用 = 固定单件费用合计 + 候选售价 × 售价费率合计；"
    "已知费用后余额 = 采购毛利 − 已填费用；余额率 = 余额 ÷ 候选售价 × 100%。"
    "假设保本售价 = (采购成本 + 固定单件费用) ÷ (1 − 售价费率合计)，向上取整到币种最小单位。"
)
SCOPE_NOTE = (
    "单件、手工假设估算，不关联订单或结算，不代表真实净利润。所有金额为所选结算币种，不换汇。"
    "百分比统一按候选售价计费；固定项是已分摊的单件费用。"
    "税费和退款损失是自填情景，不自动判断税制、退款概率或费用返还。"
    "空值表示未知，未计入余额；显式零也需依据。保本价仅覆盖已填模型，不能保证实际不亏损。"
    "计算过程保留精度，金额原值可展开；余额率四舍五入到四位小数。"
)
ZERO = Decimal(0)
HUNDRED = Decimal(100)


def margin(balance: Decimal, price: Decimal) -> Decimal | None:
    if price == 0:
        return None
    return (balance / price * HUNDRED).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def calculate_scenario(data: ScenarioInput, currency: str) -> ScenarioResult:
    fixed = sum(
        (fee.value for fee in data.fees if fee.value is not None and fee.mode == "fixed"), ZERO
    )
    rate = sum(
        (fee.value for fee in data.fees if fee.value is not None and fee.mode == "percent"), ZERO
    )
    fees = fixed + data.price * rate / HUNDRED
    balance = data.price - data.purchase_cost - fees
    missing = [FEE_LABELS[fee.kind] for fee in data.fees if fee.value is None]
    break_even = None
    if missing:
        reason = "费用假设未完整，无法确定保本售价；请逐项补充或明确为零及其依据。"
    elif rate >= HUNDRED:
        reason = "售价费率合计达到或超过 100%，当前模型不能给出可用保本售价。"
    else:
        unit = Decimal("1") if currency == "JPY" else Decimal("0.01")
        break_even = ((data.purchase_cost + fixed) / (1 - rate / HUNDRED)).quantize(
            unit, rounding=ROUND_CEILING
        )
        reason = "仅作为上述单件假设下的最低覆盖价；实际价格还需核对未建模费用与市场。"
    points: list[SensitivityPoint] = []
    for label, price_factor, cost_factor in [
        ("售价 −10%", "0.9", "1"),
        ("原方案", "1", "1"),
        ("售价 +10%", "1.1", "1"),
        ("采购成本 +10%", "1", "1.1"),
    ]:
        price = data.price * Decimal(price_factor)
        cost = data.purchase_cost * Decimal(cost_factor)
        amount = price * (1 - rate / HUNDRED) - cost - fixed
        points.append(
            SensitivityPoint(
                label=label,
                price=price,
                purchase_cost=cost,
                known_balance=amount,
                margin_percent=margin(amount, price),
            )
        )
    return ScenarioResult(
        assumption=data,
        purchase_gross=data.price - data.purchase_cost,
        known_fees=fees,
        known_balance=balance,
        margin_percent=margin(balance, data.price),
        fixed_fees=fixed,
        rate_percent=rate,
        missing_fees=missing,
        fees=[
            FeeResult(
                assumption=fee,
                amount=(
                    None
                    if fee.value is None
                    else fee.value
                    if fee.mode == "fixed"
                    else data.price * fee.value / HUNDRED
                ),
            )
            for fee in data.fees
        ],
        break_even_price=break_even,
        break_even_reason=reason,
        sensitivity=points,
    )


def calculate_study(data: StudyInput, calculated_at: str) -> StudyResult:
    with localcontext() as context:
        context.prec = 40
        return StudyResult(
            input=data,
            rule_version=RULE_VERSION,
            calculated_at=calculated_at,
            formula=FORMULA,
            scope_note=SCOPE_NOTE,
            scenarios=[calculate_scenario(item, data.currency) for item in data.scenarios],
        )
