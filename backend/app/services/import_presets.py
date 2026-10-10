"""Evidence-backed mapping candidates; never transform or commit source rows."""

from app.schemas.imports import ImportPreset

SHOPIFY_PRODUCTS = ImportPreset(
    id="shopify-products-2026-10-10-v1",
    name="Shopify 商品 CSV · 当前字段子集 v1",
    kind="products",
    source_channel="shopify",
    verified_on="2026-10-10",
    reference_url="https://help.shopify.com/en/manual/products/import-export/using-csv",
    mapping={"sku": "SKU", "name": "Title", "price": "Price", "unit_cost": "Cost per item"},
    notes=[
        "字段格式候选：请与本次导出说明核对。合成字段子集已测试，真实卖家文件兼容待验证。",
        "销售币种和成本币种须按来源逐行补齐或手工映射；有金额但缺币种时不能提交。",
        "每行须有唯一 SKU 和完整商品名。空白变体名称请依据原商品补齐；"
        "纯图片行请在本地准备文件时移除，不会自动向下填充或跳过。",
        "仅使用 Price 基础单价；国际售价、比较价及 Description 不自动映射。"
        "缺失金额保持未知。文件仍限 64 列，每格 2000 字符。",
        "应用会重置当前映射与逐行修正；请重新预览并确认关键字段含义。",
    ],
)

# Removing an ID retires its candidate while saved/manual mappings keep working.
ACTIVE_PRESET_IDS = frozenset({SHOPIFY_PRODUCTS.id})


def matching_presets(kind: str, channel: str, headers: list[str]) -> list[ImportPreset]:
    preset = SHOPIFY_PRODUCTS
    signature = {"URL handle", *preset.mapping.values()}
    if (
        preset.id not in ACTIVE_PRESET_IDS
        or kind != preset.kind
        or channel != preset.source_channel
        or not signature.issubset(headers)
    ):
        return []
    return [preset.model_copy(deep=True)]
