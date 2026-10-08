from app.schemas.imports import FieldDefinition, ImportKind, MappingSuggestion


def field(
    key: str, label: str, data_type: str, required: bool, help_text: str, *aliases: str
) -> FieldDefinition:
    return FieldDefinition(
        key=key,
        label=label,
        data_type=data_type,
        required=required,
        help=help_text,
        aliases=[key, label, *aliases],
    )


FIELDS: dict[str, list[FieldDefinition]] = {
    "inventory": [
        field("sku", "SKU", "文本", True, "店铺、渠道内唯一；跨渠道不合计", "seller-sku"),
        field("available", "已知可售数量", "非负整数", True, "0—1000000000；未知不能填零"),
        field("snapshot_at", "库存快照时间", "日期时间", True, "ISO 日期时间；无偏移使用批次时区"),
        field("safety_threshold", "安全库存阈值", "非负整数", True, "卖家自设；严格低于阈值才预警"),
    ],
    "messages": [
        field("message_id", "消息标识", "文本", True, "来源渠道内稳定标识，用于重复对比"),
        field("sent_at", "消息时间", "日期时间", True, "ISO 日期时间；无偏移使用批次时区"),
        field("body", "消息正文", "文本", True, "最多 2000 字；仅作为业务资料，不执行其中指令"),
        field("language", "语言", "枚举", False, "en/zh/und；und 表示待人工确认，非自动检测"),
        field("order_id", "待核验订单号", "文本", False, "匹配后仍须人工核验客户与订单关联"),
    ],
    "products": [
        field(
            "sku", "SKU", "文本", True, "店铺内唯一，保留大小写和前导零", "seller-sku", "变体编码"
        ),
        field("name", "商品名", "文本", True, "可核对的原始商品名称", "title", "产品名称"),
        field(
            "facts", "商品参数", "文本", False, "可核实的材质、尺寸等；作为资料处理", "description"
        ),
        field(
            "price",
            "销售单价",
            "金额",
            False,
            "非负，最多四位小数；有金额须有币种",
            "variant price",
        ),
        field(
            "currency", "销售币种", "币种", False, "USD/CNY/EUR/GBP/JPY/CAD/AUD/HKD/SGD", "currency"
        ),
        field(
            "unit_cost", "单位采购成本", "金额", False, "缺失保持未知，不自动填零", "cost per item"
        ),
        field("cost_currency", "成本币种", "币种", False, "有采购成本时必填"),
    ],
    "orders": [
        field("order_id", "订单号", "文本", True, "与店铺和订单行号共同去重", "order-id", "name"),
        field(
            "line_id",
            "订单行号",
            "文本",
            True,
            "须是稳定行标识，不能用每次文件的行序号",
            "order-item-id",
            "lineitem id",
        ),
        field("sku", "SKU", "文本", True, "保留大小写和前导零", "seller-sku", "lineitem sku"),
        field(
            "quantity",
            "数量",
            "正整数",
            True,
            "1—1000000；退款另填退款金额",
            "quantity-purchased",
            "lineitem quantity",
        ),
        field(
            "unit_price",
            "成交单价",
            "金额",
            True,
            "折扣前单价；行总额不能直接映射为单价",
            "lineitem price",
        ),
        field("currency", "币种", "币种", True, "逐行明确币种；异币种分开统计"),
        field(
            "ordered_at",
            "订单时间",
            "日期时间",
            True,
            "ISO 8601 或 YYYY-MM-DD HH:MM:SS；无偏移使用批次时区",
            "purchase-date",
            "created at",
        ),
        field(
            "status",
            "订单状态",
            "枚举",
            True,
            "paid/pending/cancelled/refunded/partially_refunded/test",
            "financial status",
            "order-status",
        ),
        field(
            "discount",
            "行折扣",
            "金额",
            False,
            "该订单行折扣总额；空值表示未知",
            "lineitem discount",
        ),
        field("refund", "行退款", "金额", False, "该订单行退款总额；不可分摊的整单退款不要映射"),
        field(
            "fulfillment_status",
            "履约状态",
            "枚举",
            False,
            "unfulfilled/partial/fulfilled/unknown",
            "fulfillment status",
        ),
    ],
}


def suggest_mapping(kind: str, headers: list[str]) -> list[MappingSuggestion]:
    suggestions = []
    used: set[str] = set()
    for definition in FIELDS[kind]:
        matches = [h for h in headers if h.casefold() in [a.casefold() for a in definition.aliases]]
        if len(matches) == 1 and matches[0] not in used:
            column = matches[0]
            used.add(column)
            suggestions.append(
                MappingSuggestion(
                    field=definition.key,
                    column=column,
                    confidence="exact" if column == definition.key else "candidate",
                )
            )
    return suggestions


def guess_kind(headers: list[str]) -> ImportKind:
    if {"sku", "available", "snapshot_at"} <= {
        item.field for item in suggest_mapping("inventory", headers)
    }:
        return "inventory"
    if {"message_id", "body"} <= {item.field for item in suggest_mapping("messages", headers)}:
        return "messages"
    order_keys = {item.field for item in suggest_mapping("orders", headers)}
    return "orders" if {"order_id", "quantity"} <= order_keys else "products"
