"""Build deterministic home-and-living business inputs without performing I/O.

The returned content is authored scenario data. Importers must assign its data
identity explicitly; this module does not claim an external platform source.
"""

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

from scripts.foundation_samples import csv_text

HEADERS = {
    "products": [
        "sku",
        "name",
        "facts",
        "price",
        "currency",
        "unit_cost",
        "cost_currency",
    ],
    "orders": [
        "order_id",
        "line_id",
        "sku",
        "quantity",
        "unit_price",
        "currency",
        "ordered_at",
        "status",
        "discount",
        "refund",
        "fulfillment_status",
    ],
    "inventory": ["sku", "available", "snapshot_at", "safety_threshold"],
    "messages": [
        "message_id",
        "sent_at",
        "body",
        "language",
        "order_id",
        "reply_status",
        "reply_updated_at",
        "reply_evidence",
    ],
}

# SKU, name, product facts, retail price, current unit purchase cost.
CATALOG = (
    (
        "QJ-MUG-350",
        "栖居生活 双层不锈钢随行杯 350mL",
        (
            "Brand: Qiju Living; Material: 304 stainless steel; Capacity: 350 mL; "
            "Colour: oat; Lid: polypropylene; Care: hand wash; Not microwave safe"
        ),
        "22.90",
        "19.60",
    ),
    (
        "QJ-MAT-4060",
        "栖居生活 棉质浴室地垫 40×60cm",
        (
            "Brand: Qiju Living; Material: cotton pile with TPR backing; Size: 40 x 60 cm; "
            "Colour: warm grey; Care: cold gentle wash, air dry; Place on a dry floor"
        ),
        "29.90",
        "25.80",
    ),
    (
        "QJ-BIN-28",
        "栖居生活 竹盖桌面收纳盒 28cm",
        (
            "Brand: Qiju Living; Material: polypropylene box and bamboo lid; "
            "Size: 28 x 18 x 12 cm; Colour: ivory; Care: wipe clean; Quantity: 1"
        ),
        "24.90",
        "9.20",
    ),
    (
        "QJ-BSK-SET2",
        "栖居生活 棉绳收纳篮 两件套",
        (
            "Brand: Qiju Living; Material: cotton rope; Set: 2 baskets; "
            "Sizes: 26 x 20 x 15 cm and 22 x 16 x 12 cm; Colour: natural; "
            "Care: spot clean and air dry"
        ),
        "34.90",
        "13.40",
    ),
    (
        "QJ-TWL-SET3",
        "栖居生活 华夫格厨房擦手巾 三条装",
        (
            "Brand: Qiju Living; Material: cotton; Size: 40 x 60 cm each; Set: 3 towels; "
            "Colours: sage, ivory and sand; Care: machine wash cold, tumble dry low"
        ),
        "18.90",
        "6.10",
    ),
    (
        "QJ-JAR-1000",
        "栖居生活 竹盖玻璃储物罐 1000mL",
        (
            "Brand: Qiju Living; Material: borosilicate glass, bamboo lid and silicone seal; "
            "Capacity: 1000 mL; Size: 10 x 10 x 16 cm; "
            "Care: glass body dishwasher safe, lid hand wash and dry"
        ),
        "19.90",
        "7.30",
    ),
    (
        "QJ-TRAY-30",
        "栖居生活 榉木椭圆托盘 30cm",
        (
            "Brand: Qiju Living; Material: beech wood; Size: 30 x 18 x 2 cm; "
            "Colour: natural wood; Quantity: 1; Care: wipe clean, do not soak"
        ),
        "27.90",
        "10.80",
    ),
    (
        "QJ-PIL-4545",
        "栖居生活 棉麻抱枕套 45×45cm",
        (
            "Brand: Qiju Living; Material: 70% cotton, 30% linen; Size: 45 x 45 cm; "
            "Colour: sand; Hidden zipper; Cushion insert excluded; "
            "Care: machine wash cold on a gentle cycle"
        ),
        "21.90",
        "7.80",
    ),
)


def _money(amount: Decimal) -> str:
    return str(amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _scope(anchor: datetime, days: int, channel: str | None = None) -> dict[str, Any]:
    return {
        "start_at": (anchor - timedelta(days=days)).isoformat(),
        "end_at": anchor.isoformat(),
        "timezone": "America/Los_Angeles",
        "currency": "USD",
        "channel": channel,
        "intent": "low_margin",
        "min_quantity": 1,
        "max_margin_percent": "20",
        "max_age_hours": 24,
    }


def _orders(anchor: datetime, platform: str, offset: int) -> list[dict[str, Any]]:
    rows = []
    for day in range(30):
        for slot in range(2):
            index = day * 2 + slot
            sku, _, _, price_text, _ = CATALOG[(day * 3 + slot + offset) % len(CATALOG)]
            price = Decimal(price_text)
            quantity = 3 if index % 23 == 0 else 2 if index % 9 == 0 or index == 55 else 1
            subtotal = price * quantity
            rate = Decimal("0.10") if index % 11 == 0 else Decimal("0.05")
            discount = (
                Decimal(_money(subtotal * rate))
                if index % 11 == 0 or index % 7 == 0
                else Decimal("0.00")
            )
            status = "paid"
            refund = Decimal("0.00")
            fulfillment = "fulfilled" if day < 26 else "unfulfilled"
            if index == 9:
                status, fulfillment = "cancelled", "unfulfilled"
                discount = Decimal("0.00")
            elif index == 20:
                status, refund = "refunded", subtotal - discount
            elif index == 35:
                status, refund = "partially_refunded", Decimal("5.00")
            elif index in {57, 58}:
                status, fulfillment = "pending", "unfulfilled"
            elif index == 55:
                fulfillment = "partial"
            order_id = (
                f"114-5083201-{1004001 + index:07d}" if platform == "amazon" else f"#{1041 + index}"
            )
            ordered_at = anchor - timedelta(
                days=29 - day,
                hours=10 - slot * 5,
                minutes=(index * 13) % 47,
            )
            rows.append(
                {
                    "order_id": order_id,
                    "line_id": "1",
                    "sku": sku,
                    "quantity": quantity,
                    "unit_price": _money(price),
                    "currency": "USD",
                    "ordered_at": ordered_at.isoformat(),
                    "status": status,
                    "discount": _money(discount),
                    "refund": _money(refund),
                    "fulfillment_status": fulfillment,
                }
            )
    return rows


def _messages(
    anchor: datetime,
    platform: str,
    orders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    content = (
        (
            (
                "Could you confirm when my order will be dispatched? "
                "The order page still shows that it has not shipped."
            ),
            56,
        ),
        (
            (
                "I received my order but the size does not fit the space I had in mind. "
                "The item is unused. Could you explain the return process?"
            ),
            40,
        ),
        (
            (
                "For the 1000 mL glass storage jar, is the bamboo lid dishwasher safe? "
                "I would also like to confirm the jar dimensions."
            ),
            None,
        ),
        (
            (
                "One item in my parcel arrived damaged. I can provide a photo. "
                "Could you help with a replacement or refund?"
            ),
            45,
        ),
        (
            (
                "How should I clean the 350 mL stainless steel travel cup? "
                "Can the cup go in the microwave?"
            ),
            None,
        ),
    )
    rows = []
    for index, (body, order_index) in enumerate(content):
        sent_at = anchor - timedelta(hours=18 - index * 4, minutes=7 * index)
        replied = index == 4
        rows.append(
            {
                "message_id": f"QJ-{platform.upper()}-C{2201 + index}",
                "sent_at": sent_at.isoformat(),
                "body": body,
                "language": "en",
                "order_id": orders[order_index]["order_id"] if order_index is not None else "",
                "reply_status": "replied" if replied else "awaiting_reply",
                "reply_updated_at": (
                    sent_at + timedelta(minutes=25) if replied else sent_at
                ).isoformat(),
                "reply_evidence": f"QJ-{platform.upper()}-R2205" if replied else "",
            }
        )
    return rows


def _policies(anchor: datetime, platform: str) -> list[dict[str, Any]]:
    policies = (
        (
            "faq",
            "商品材质与护理说明",
            (
                "Use the recorded product specifications when answering care or size questions. "
                "Wash the stainless steel cup by hand; it is not microwave safe. "
                "The glass jar body is dishwasher safe; hand wash and dry the bamboo lid. "
                "Do not promise properties that are absent from the product record."
            ),
        ),
        (
            "shipping",
            "订单发货与物流查询",
            (
                "Paid orders are normally prepared within 2 business days. "
                "Confirm dispatch and tracking details in the sales channel before quoting them. "
                "Delivery dates depend on the carrier and destination; "
                "do not guarantee an arrival date."
            ),
        ),
        (
            "refund",
            "退换货处理流程",
            (
                "Invite the customer to request a return through the original sales channel. "
                "A person must review the order, delivery date, item condition "
                "and applicable channel "
                "policy before confirming eligibility, a replacement or a refund amount. "
                "For damage, request a product photo without personal details."
            ),
        ),
    )
    return [
        {
            "code": f"QJ-{platform.upper()}-{topic.upper()}",
            "title": title,
            "topic": topic,
            "text": body,
            "market": "US",
            "channel": platform,
            "language": "en",
            "source": "栖居生活经营政策草案",
            "source_version": anchor.strftime("%Y.%m"),
            "source_confirmed": False,
            "valid_from": (anchor - timedelta(days=60)).isoformat(),
            "valid_until": (anchor + timedelta(days=90)).isoformat(),
        }
        for topic, title, body in policies
    ]


def _expected(orders: list[dict[str, Any]]) -> dict[str, Any]:
    included = [
        row for row in orders if row["status"] in {"paid", "refunded", "partially_refunded"}
    ]
    cost_lookup = {row[0]: Decimal(row[4]) for row in CATALOG}
    sales = cost = discount = refunds = subtotal = Decimal("0.00")
    sku_totals: dict[str, dict[str, Decimal]] = {}
    with localcontext() as context:
        context.prec = 40
        for row in included:
            quantity = row["quantity"]
            line_subtotal = Decimal(row["unit_price"]) * quantity
            line_sales = line_subtotal - Decimal(row["discount"]) - Decimal(row["refund"])
            line_cost = cost_lookup[row["sku"]] * quantity
            subtotal += line_subtotal
            discount += Decimal(row["discount"])
            refunds += Decimal(row["refund"])
            sales += line_sales
            cost += line_cost
            sku_total = sku_totals.setdefault(row["sku"], {"sales": Decimal(0), "cost": Decimal(0)})
            sku_total["sales"] += line_sales
            sku_total["cost"] += line_cost
        low_margin = sorted(
            sku
            for sku, values in sku_totals.items()
            if values["sales"] > 0
            and (values["sales"] - values["cost"]) * 100 <= values["sales"] * 20
        )
        return {
            "order_rows": len(orders),
            "paid_order_rows": len(included),
            "purchased_quantity": sum(row["quantity"] for row in included),
            "subtotal": _money(subtotal),
            "discount": _money(discount),
            "refund": _money(refunds),
            "sales": _money(sales),
            "cost": _money(cost),
            "gross_profit": _money(sales - cost),
            "margin_percent": str(((sales - cost) * 100 / sales).quantize(Decimal("0.01"))),
            "low_margin_skus": low_margin,
            "fulfillment_review_orders": [
                row["order_id"] for row in included if row["fulfillment_status"] != "fulfilled"
            ],
            "status_counts": {
                status: sum(row["status"] == status for row in orders)
                for status in sorted({row["status"] for row in orders})
            },
        }


def build_scenario(now: datetime) -> dict[str, Any]:
    """Return a fresh 30-day scenario; callers choose and persist its data identity.

    ``now`` must be timezone-aware. Monetary expectations follow the application's
    current-purchase-cost basis, excluding pending/cancelled orders. No files,
    database records, network calls or real customer records are used.
    """
    if now.utcoffset() is None:
        raise ValueError("生成时刻必须包含时区偏移")
    generated_at = now.astimezone(UTC).replace(microsecond=0)
    exported_at = generated_at - timedelta(minutes=10)
    snapshot_at = generated_at - timedelta(minutes=20)
    anchor = generated_at - timedelta(minutes=30)
    products = [
        dict(
            zip(
                HEADERS["products"],
                [sku, name, facts, price, "USD", cost, "USD"],
                strict=True,
            )
        )
        for sku, name, facts, price, cost in CATALOG
    ]
    shops = []
    all_orders = []
    for offset, platform in enumerate(("amazon", "shopify")):
        orders = _orders(anchor, platform, offset)
        all_orders.extend(orders)
        available = (
            (3, 42, 68, 4, 96, 51, 34, 75)
            if platform == "amazon"
            else (5, 26, 39, 6, 58, 32, 25, 48)
        )
        thresholds = (8, 12, 15, 10, 20, 12, 10, 15)
        inventory = [
            {
                "sku": product[0],
                "available": stock,
                "snapshot_at": snapshot_at.isoformat(),
                "safety_threshold": threshold,
            }
            for product, stock, threshold in zip(CATALOG, available, thresholds, strict=True)
        ]
        messages = _messages(anchor, platform, orders)
        files = [
            {
                "filename": f"qiju-{platform}-{kind}.csv",
                "kind": kind,
                "channel": platform,
                "exported_at": exported_at.isoformat(),
                "text": csv_text(
                    HEADERS[kind],
                    [[row[column] for column in HEADERS[kind]] for row in rows],
                ),
            }
            for kind, rows in (
                ("products", products),
                ("orders", orders),
                ("inventory", inventory),
                ("messages", messages),
            )
        ]
        expected = _expected(orders)
        expected.update(
            {
                "current_rows": {
                    "products": 8,
                    "orders": 60,
                    "inventory": 8,
                    "messages": 5,
                },
                "low_inventory_skus": ["QJ-MUG-350", "QJ-BSK-SET2"],
                "awaiting_reply_messages": 4,
                "recent_7_days": _expected(
                    [
                        row
                        for row in orders
                        if datetime.fromisoformat(row["ordered_at"]) >= anchor - timedelta(days=7)
                    ]
                ),
            }
        )
        shops.append(
            {
                "code": f"qiju-{platform}-us",
                "name": f"栖居生活 · {'Amazon' if platform == 'amazon' else 'Shopify'} 美国店",
                "platform": platform,
                "market": "US",
                "currency": "USD",
                "timezone": "America/Los_Angeles",
                "scope": _scope(anchor, 30, platform),
                "recent_scope": _scope(anchor, 7, platform),
                "files": files,
                "policies": _policies(anchor, platform),
                "expected": expected,
            }
        )
    expected = _expected(all_orders)
    expected["current_rows"] = {
        "shops": 2,
        "products": 16,
        "orders": 120,
        "inventory": 16,
        "messages": 10,
    }
    return {
        "contract": "qiju-living-operations-v1",
        "generated_at": generated_at.isoformat(),
        "exported_at": exported_at.isoformat(),
        "profile": {
            "display_name": "栖居生活",
            "target_market": "US",
            "business_model": "家居自有品牌，多渠道零售",
            "category": "家居收纳、厨房用品与日用纺织品",
            "currency": "USD",
            "timezone": "America/Los_Angeles",
            "language": "zh-CN",
            "version": 0,
        },
        "scope": _scope(anchor, 30),
        "recent_scope": _scope(anchor, 7),
        "shops": shops,
        "expected": expected,
    }
