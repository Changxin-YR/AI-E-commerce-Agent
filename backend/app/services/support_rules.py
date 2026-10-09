import re
from collections import Counter

from app.schemas.support import MessageFacts, OrderFact, PolicyOutput, ReplySnapshot

PATTERNS = {
    "shipping": (
        r"\b(where.*order|track\w*|deliver\w*|shipping|shipment|parcel)\b"
        r"|物流|快递|到货|没收到"
    ),
    "refund": r"\b(refund\w*|return\w*)\b|退款|退货",
    "address_change": r"\b(address|redirect|intercept)\b|改地址|修改地址|拦截",
    "cancel": r"\bcancel\w*\b|取消",
    "dispute": (
        r"\b(dispute\w*|chargeback|lawyer|sue|compensation|claim)\b"
        r"|争议|赔偿|律师|起诉|投诉"
    ),
    "warranty": r"\b(warranty|broken|defect\w*)\b|保修|损坏|故障",
    "faq": r"\b(how|instruction\w*|manual|care|clean\w*)\b|如何|怎么|说明书|清洗",
}
INTENT_LABELS = {
    "shipping": "物流查询",
    "refund": "退款/退货",
    "address_change": "地址变更/拦截",
    "cancel": "取消订单",
    "dispute": "争议/赔偿",
    "warranty": "保修/故障",
    "faq": "一般使用咨询",
    "unknown": "意图待确认",
}


def classify(body: str) -> list[str]:
    return [key for key, pattern in PATTERNS.items() if re.search(pattern, body, re.I)] or [
        "unknown"
    ]


def prepare_reply(
    message: MessageFacts,
    orders: list[OrderFact],
    verified: bool,
    policies: list[PolicyOutput],
    conflicts: bool,
    model_intents: list[str] | None = None,
    review_reasons: list[str] | None = None,
) -> ReplySnapshot:
    intents = classify(message.body)
    if model_intents:
        intents = list(dict.fromkeys([*intents, *model_intents]))
    reasons = []
    sensitive = {"refund", "address_change", "cancel", "dispute", "warranty"} & set(intents)
    if sensitive:
        reasons.append(
            "包含敏感诉求：" + "、".join(INTENT_LABELS[i] for i in intents if i in sensitive)
        )
    if "shipping" in intents:
        reasons.append("没有可验证且满足时效要求的物流轨迹；订单 CSV 履约状态不能证明当前物流")
    if (sensitive or "shipping" in intents) and not verified:
        reasons.append("客户与订单尚未核验关联；订单号匹配不等于客户身份已核实")
    if "unknown" in intents:
        reasons.append("本地规则无法可靠识别此消息意图，请人工阅读完整原文")
    if message.language not in {"en", "zh"}:
        reasons.append("消息语言待确认；当前本地模板仅支持英文和中文，需人工翻译")
    if conflicts or any(n > 1 for n in Counter(p.data.topic for p in policies if p.data).values()):
        reasons.append("同一主题存在多份适用政策，需核对冲突与优先级")
    if not policies or any(not p.data or not p.data.source_confirmed for p in policies):
        reasons.append("缺少已核对的适用政策；不能作退款、保修或时效承诺")

    reasons = list(dict.fromkeys([*reasons, *(review_reasons or [])]))
    english = message.language == "en"
    parts = ["Thank you for your message." if english else "感谢您的来信。"]
    if "shipping" in intents:
        parts.append(
            "I cannot verify the current tracking status or delivery date "
            "from the available records."
            if english
            else "根据现有记录，我无法核实当前物流进度或送达日期。"
        )
    if "refund" in intents:
        parts.append(
            "Your refund or return request needs manual review; no refund has been confirmed."
            if english
            else "您的退款或退货诉求需要人工核实，目前尚未确认退款。"
        )
    if sensitive - {"refund"}:
        parts.append(
            "Your requested action needs manual review before it can be confirmed."
            if english
            else "您提出的处理请求需要人工核实后才能确认。"
        )
    # Only a single, explicitly reviewed FAQ excerpt can enter the template.
    # Other policy text remains internal evidence; it never grants tool permissions.
    if intents == ["faq"] and not reasons and len(policies) == 1:
        policy = policies[0].data
        if policy and policy.topic == "faq":
            parts.append(
                (
                    "For reference, the provided FAQ states:\n"
                    if english
                    else "供参考，所提供的 FAQ 原文为：\n"
                )
                + policy.text
            )
    if reasons or intents == ["unknown"]:
        parts.append(
            "Further verification is needed before a confirmed answer can be provided."
            if english
            else "提供确定答复前，还需要进一步核实相关信息。"
        )
    reply = "\n\n".join(parts) if message.language in {"en", "zh"} else ""
    summary = "诉求：" + "、".join(INTENT_LABELS[i] for i in intents)
    summary += (
        f"。订单关联：{'人工已核验' if verified else '待关联'}；选用政策 {len(policies)} 份。"
    )
    summary += "请核对消息原文、证据缺口和全部诉求；当前仅有本地草稿。"
    return ReplySnapshot(
        message=message,
        orders=orders,
        order_verified=verified,
        policies=policies,
        intents=intents,
        reasons=reasons,
        handoff_summary=summary,
        reply=reply,
    )
