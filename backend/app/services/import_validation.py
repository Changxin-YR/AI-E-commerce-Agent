import hashlib
import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError

from app.core.time import utc_now
from app.schemas.imports import (
    InventoryData,
    MessageData,
    OrderData,
    ParsedRow,
    ProductData,
    RowIssue,
    RowOutput,
)
from app.services.import_catalog import FIELDS

DECIMAL_PATTERN = re.compile(r"^-?\d+(?:\.\d{1,4})?$")


def parse_time(value: str, timezone: str) -> datetime:
    if not re.match(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", value):
        raise ValueError("使用 ISO 日期时间（含时分），不接受含糊的日/月顺序")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("日期时间无效") from error
    if parsed.year < 1000:
        raise ValueError("日期须在 MySQL 支持的 1000—9999 年范围内")
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC)
    zone = ZoneInfo(timezone)
    possibilities = {
        parsed.replace(tzinfo=zone, fold=fold).astimezone(UTC)
        for fold in (0, 1)
        if parsed.replace(tzinfo=zone, fold=fold)
        .astimezone(UTC)
        .astimezone(zone)
        .replace(tzinfo=None)
        == parsed
    }
    if len(possibilities) != 1:
        raise ValueError("时间处于夏令时重复或缺失区间，请填写明确的 UTC 偏移")
    return possibilities.pop()


def unsafe_text(value: str) -> bool:
    trimmed = value.lstrip()
    return trimmed.startswith(("=", "+", "@")) or (
        trimmed.startswith("-") and DECIMAL_PATTERN.fullmatch(trimmed) is None
    )


def business_key(kind: str, normalized: dict[str, Any], channel: str = "generic") -> str:
    if kind == "messages":
        parts = [channel, normalized["message_id"]]
    elif kind == "inventory":
        parts = ["inventory", channel, normalized["sku"]]
    elif kind == "products":
        parts = [normalized["sku"]]
    else:
        parts = [normalized["order_id"], normalized["line_id"]]
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False).encode()).hexdigest()


def normalize_row(
    kind: str,
    row: ParsedRow,
    headers: list[str],
    mapping: dict[str, str],
    corrections: dict[str, str],
    timezone: str,
) -> RowOutput:
    raw = {field: row.values[headers.index(column)] for field, column in mapping.items()}
    values: dict[str, Any] = {key: value.strip() for key, value in (raw | corrections).items()}
    errors: list[RowIssue] = []
    warnings: list[str] = []

    def issue(field: str, message: str) -> None:
        errors.append(RowIssue(field=field, message=message))

    for index, value in enumerate(row.values):
        targets = [key for key, column in mapping.items() if column == headers[index]]
        if (index in row.unsafe_columns or unsafe_text(value)) and not (
            targets and targets[0] in corrections and not unsafe_text(corrections[targets[0]])
        ):
            issue(
                targets[0] if targets else headers[index],
                "源单元格含公式或不安全表达式，请改为核对后的文本/数值",
            )
    for key, value in values.items():
        if unsafe_text(value):
            issue(key, "不接受公式或可执行表达式")
    money_fields = (
        {"price", "unit_cost"} if kind == "products" else {"unit_price", "discount", "refund"}
    )
    if kind == "inventory":
        money_fields = set()
        for key in ("available", "safety_threshold"):
            if not re.fullmatch(r"\d+", values.get(key, "")):
                issue(key, "数量和阈值须为非负整数；未知请补充来源，不要填零")
        try:
            values["snapshot_at"] = parse_time(values.get("snapshot_at", ""), timezone)
            if values["snapshot_at"].replace(tzinfo=None) > utc_now():
                issue("snapshot_at", "快照时间不能晚于当前时间，请核对时区和源文件")
        except ValueError as error:
            issue("snapshot_at", str(error))
    if kind == "messages":
        money_fields = set()
        values["language"] = values.get("language", "").lower() or "und"
        try:
            values["sent_at"] = parse_time(values.get("sent_at", ""), timezone)
        except ValueError as error:
            issue("sent_at", str(error))
    for key in money_fields:
        value = values.get(key, "")
        if not value:
            values[key] = None
        elif not DECIMAL_PATTERN.fullmatch(value):
            issue(key, "金额须为不带千分位/货币符号的数字，最多四位小数")
    for key in ("currency", "cost_currency"):
        if key in values:
            values[key] = values[key].upper() or None
    if kind == "orders":
        if not re.fullmatch(r"\d+", values.get("quantity", "")):
            issue("quantity", "数量须为正整数")
        try:
            values["ordered_at"] = parse_time(values.get("ordered_at", ""), timezone)
        except ValueError as error:
            issue("ordered_at", str(error))
        for key in ("status", "fulfillment_status"):
            if key in values:
                values[key] = values[key].lower()
        if not values.get("fulfillment_status"):
            values["fulfillment_status"] = "unknown"
    normalized: dict[str, Any] = {}
    if not errors:
        try:
            schemas: dict[
                str, type[ProductData] | type[OrderData] | type[MessageData] | type[InventoryData]
            ] = {
                "products": ProductData,
                "orders": OrderData,
                "messages": MessageData,
                "inventory": InventoryData,
            }
            schema = schemas[kind]
            model = schema.model_validate(values)
            normalized = model.model_dump(mode="json")
            for key in money_fields:
                if normalized.get(key) is not None:
                    normalized[key] = format(Decimal(normalized[key]), ".4f")
        except ValidationError as error:
            labels = {field.key: field for field in FIELDS[kind]}
            for item in error.errors(include_input=False, include_context=False):
                key = str(item["loc"][0])
                field = labels.get(key)
                issue(
                    key, f"{field.label if field else key}无效或缺失；{field.help if field else ''}"
                )
    if normalized:
        if kind == "products":
            for amount, currency in (("price", "currency"), ("unit_cost", "cost_currency")):
                if normalized[amount] is not None and normalized[currency] is None:
                    issue(currency, "有金额时必须明确币种")
            if normalized["unit_cost"] is None:
                warnings.append("缺单位采购成本，不能计算该 SKU 已知毛利")
            elif normalized["currency"] is None:
                warnings.append("缺销售币种，毛利分析须核对订单币种与成本币种")
            elif normalized["currency"] != normalized["cost_currency"]:
                warnings.append("销售与成本币种不一致，不能直接计算毛利")
        elif kind == "orders":
            gross = Decimal(normalized["unit_price"]) * normalized["quantity"]
            discount = (
                Decimal(normalized["discount"]) if normalized["discount"] is not None else None
            )
            refund = Decimal(normalized["refund"]) if normalized["refund"] is not None else None
            if discount is not None and discount > gross:
                issue("discount", "行折扣不能超过行销售金额")
            if refund is not None and refund > gross - (discount or Decimal(0)):
                issue("refund", "行退款不能超过扣除折扣后的行销售金额")
            if normalized["status"] in {"refunded", "partially_refunded"} and (
                refund is None or refund <= 0
            ):
                issue("refund", "退款状态须提供正数的行退款金额")
            if discount is None or refund is None:
                warnings.append("折扣或退款金额未知，后续净销售额/毛利分析须说明缺口")
            if normalized["status"] in {"pending", "cancelled", "test"}:
                warnings.append("该状态不计入已支付销售")
        elif kind == "inventory":
            warnings.append("仅表示该渠道在快照时刻的可售数量；跨渠道不合计，不代表实时库存")
        else:
            warnings.append("消息及订单号仅为来源记录；客户与订单关联需人工核验，未取得外发权限")
    return RowOutput(
        row_number=row.row_number,
        raw=raw,
        corrections=corrections,
        normalized=normalized,
        previous=None,
        errors=errors,
        warnings=warnings,
        action="error" if errors else "new",
    )
