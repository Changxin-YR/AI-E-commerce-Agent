import re
import unicodedata
from collections import Counter, defaultdict
from typing import Literal

from app.models.imports import Product
from app.schemas.product_quality import QualityCoverage, QualityIssue

RULE_VERSION = "product-quality-v1"
PLACEHOLDERS = {"n/a", "na", "none", "null", "unknown", "tbd", "待补充", "未知", "暂无", "无"}
CLAIMS = re.compile(
    r"100\s*%\s*(?:guaranteed|effective)|\bbest in the world\b|零风险|全网第一|永久有效",
    re.IGNORECASE,
)
LIMITATIONS = [
    "检查对象为所选范围内当前生效的商品导入主档；不包含 Listing 版本、历史导入行或实时平台数据。",
    "同店精确 SKU 由导入和数据库去重。相似 SKU 只在本次范围内比较全半角、大小写与空白；"
    "不同变体可能合法，不自动合并。",
    "参数冲突只识别按行填写的‘属性:值’或‘属性：值’，不解析自然语言、单位换算或类目必填属性。",
    "描述关键词仅匹配 100% guaranteed、100% effective、best in the world、"
    "零风险、全网第一、永久有效；未命中不代表真实或合规。",
    "价格和采购成本仅核对缺失、零值与币种一致性；零成本允许存在，缺失不按零处理，不判断实际利润或平台售价。",
]


def normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def coverage(has_products: bool) -> list[QualityCoverage]:
    checked = [
        ("name_facts", "名称与参数", "检查空值、占位文字、重复参数行、同名属性的多个值。"),
        ("amounts", "价格与采购成本", "检查已导入金额及币种；仅将零售价标记待核。"),
        ("similar_sku", "范围内相似 SKU", "按全半角、大小写与空白规范化分组，提供待核线索。"),
        ("description", "描述关键词", "仅检查已列出的六类绝对化表达，需人工结合上下文核对。"),
    ]
    excluded = [
        (
            "brand_codes",
            "品牌与商品编码",
            "主档没有品牌、GTIN/MPN 字段，无法核验真实性、格式或唯一性。",
        ),
        ("media", "图片与规格一致性", "主档没有图片、视频或变体关联，无法比对素材和实物。"),
        ("category", "类目必填属性", "尚无类目属性模板，无法判断类目要求的缺失属性。"),
        ("platform", "平台与多店铺一致性", "尚未连接实时平台，本次不跨店比较、不判断刊登合规。"),
    ]
    return [
        QualityCoverage(
            code=code,
            label=label,
            status="checked" if has_products else "not_checked",
            reason=reason if has_products else "本次范围无当前商品记录，未检查。",
        )
        for code, label, reason in checked
    ] + [
        QualityCoverage(code=code, label=label, status="not_checked", reason=reason)
        for code, label, reason in excluded
    ]


def assess(product: Product, similar_count: int) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    def add(
        code: str, field: str, status: Literal["missing", "review"], reason: str, suggestion: str
    ) -> None:
        issues.append(
            QualityIssue(
                code=code, field=field, status=status, reason=reason, suggestion=suggestion
            )
        )

    for field, text, label in [
        ("name", product.name, "商品名称"),
        ("facts", product.facts, "商品参数"),
    ]:
        if not text.strip():
            add(
                f"{field}_missing",
                field,
                "missing",
                f"{label}为空。",
                "核实真实商品资料，补充源文件后重新导入预览。",
            )
        elif normalized(text) in PLACEHOLDERS:
            add(
                f"{field}_placeholder",
                field,
                "review",
                f"{label}为占位文字，不能据此判断已完整填写。",
                "对照商品资料补充具体名称或参数。",
            )
        if CLAIMS.search(unicodedata.normalize("NFKC", text)):
            add(
                f"{field}_claim",
                field,
                "review",
                f"{label}命中已列出的描述关键词。",
                "核对上下文和可验证依据；本提示不构成真实性或合规结论。",
            )

    lines = [normalized(line) for line in product.facts.splitlines() if line.strip()]
    if any(count > 1 for count in Counter(lines).values()):
        add(
            "facts_duplicate",
            "facts",
            "review",
            "参数中存在规范化后相同的重复行。",
            "检查是否重复粘贴；保留真实且必要的参数后重新导入。",
        )
    attributes: dict[str, set[str]] = defaultdict(set)
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            if key.strip() and value.strip():
                attributes[key.strip()].add(value.strip())
    if any(len(values) > 1 for values in attributes.values()):
        add(
            "facts_conflict",
            "facts",
            "review",
            "同名参数出现多个不同值，可能为冲突或未说明的变体。",
            "逐行核对规格与变体归属，不自动选择其中一个值。",
        )
    for field, amount, currency, label in [
        ("price", product.price, product.currency, "售价"),
        ("unit_cost", product.unit_cost, product.cost_currency, "采购成本"),
    ]:
        if amount is None or currency is None:
            add(
                f"{field}_missing",
                field,
                "missing",
                f"{label}金额或币种未提供。",
                "补充有来源的金额与币种；未知时保持缺失。",
            )
    if product.price == 0:
        add(
            "price_zero",
            "price",
            "review",
            "导入售价为零。",
            "确认是否为赠品或录入错误；本地不自动改价。",
        )
    if (
        product.price is not None
        and product.unit_cost is not None
        and product.currency != product.cost_currency
    ):
        add(
            "cost_currency_mismatch",
            "cost_currency",
            "review",
            "售价与采购成本币种不同，不能直接比较。",
            "核对原币种；有汇率依据前分别保留。",
        )
    if similar_count:
        add(
            "similar_sku",
            "sku",
            "review",
            f"本次范围内另有 {similar_count} 个规范化后相同的 SKU。",
            "对照来源核对是否为独立变体或重复编码；不自动合并。",
        )
    return issues
