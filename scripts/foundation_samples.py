"""Generate explicitly synthetic, time-consistent foundation acceptance inputs."""

import argparse
import csv
import io
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


def csv_text(header: list[str], rows: list[list[Any]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue()


def samples(as_of: datetime) -> dict[str, Any]:
    if as_of.utcoffset() is None:
        raise ValueError("合成样本时刻须含时区偏移")
    anchor = as_of.astimezone(UTC).replace(microsecond=0) - timedelta(minutes=5)

    def stamp(hours: int) -> str:
        return (anchor - timedelta(hours=hours)).isoformat()

    product_header = [
        "sku",
        "name",
        "facts",
        "price",
        "currency",
        "unit_cost",
        "cost_currency",
    ]
    product_rows = [
        [
            "SYN-CUP",
            "Synthetic steel cup",
            "Material: stainless steel; Capacity: 350 mL",
            "20",
            "USD",
            "18",
            "USD",
        ],
        [
            "SYN-BOX",
            "Synthetic storage box",
            "Dimensions: 20 x 10 x 5 cm",
            "20",
            "USD",
            "8",
            "USD",
        ],
        [
            "SYN-UNKNOWN",
            "Synthetic missing cost sample",
            "Colour: blue",
            "12",
            "USD",
            "",
            "",
        ],
    ]
    order_header = [
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
    ]
    orders = [
        [
            "SYN-O1",
            "1",
            "SYN-CUP",
            2,
            "20",
            "USD",
            stamp(48),
            "paid",
            "0",
            "0",
            "unfulfilled",
        ],
        [
            "SYN-O2",
            "1",
            "SYN-BOX",
            1,
            "20",
            "USD",
            stamp(36),
            "paid",
            "0",
            "0",
            "fulfilled",
        ],
        [
            "SYN-O3",
            "1",
            "SYN-CUP",
            1,
            "20",
            "USD",
            stamp(24),
            "partially_refunded",
            "0",
            "5",
            "fulfilled",
        ],
        [
            "SYN-EUR",
            "1",
            "SYN-BOX",
            1,
            "30",
            "EUR",
            stamp(12),
            "paid",
            "0",
            "0",
            "fulfilled",
        ],
    ]
    files = [
        {
            "filename": "products-synthetic.csv",
            "kind": "products",
            "channel": "generic",
            "text": csv_text(product_header, product_rows),
        },
        {
            "filename": "orders-amazon-synthetic.csv",
            "kind": "orders",
            "channel": "amazon",
            "text": csv_text(order_header, orders[:3]),
        },
        {
            "filename": "orders-shopify-boundaries-synthetic.csv",
            "kind": "orders",
            "channel": "shopify",
            "text": csv_text(
                order_header,
                [
                    orders[3],
                    [
                        "SYN-MISSING",
                        "1",
                        "SYN-UNKNOWN",
                        1,
                        "12",
                        "USD",
                        stamp(24),
                        "paid",
                        "0",
                        "0",
                        "fulfilled",
                    ],
                ],
            ),
        },
        {
            "filename": "inventory-synthetic.csv",
            "kind": "inventory",
            "channel": "amazon",
            "text": csv_text(
                ["sku", "available", "snapshot_at", "safety_threshold"],
                [
                    ["SYN-CUP", 2, stamp(1), 5],
                    ["SYN-BOX", 3, stamp(49), 5],
                    ["SYN-UNKNOWN", 20, stamp(1), 5],
                ],
            ),
        },
        {
            "filename": "messages-synthetic.csv",
            "kind": "messages",
            "channel": "amazon",
            "text": csv_text(
                ["message_id", "sent_at", "body", "language", "order_id"],
                [
                    [
                        "SYN-FAQ",
                        stamp(2),
                        "How should I clean this item?",
                        "en",
                        "SYN-O1",
                    ],
                    [
                        "SYN-MIXED",
                        stamp(1),
                        "Where is my order? Also refund it.",
                        "en",
                        "SYN-O1",
                    ],
                ],
            ),
        },
    ]
    policies = [
        {
            "code": "SYN-" + topic.upper(),
            "title": "合成基础验收政策 " + topic,
            "topic": topic,
            "text": text,
            "market": "US",
            "channel": "amazon",
            "language": "en",
            "data_identity": "synthetic",
            "source": "SoloOps合成基础验收资料",
            "source_version": anchor.isoformat(),
            "source_confirmed": True,
            "valid_from": stamp(24 * 30),
            "valid_until": (anchor + timedelta(days=30)).isoformat(),
        }
        for topic, text in [
            ("faq", "Clean gently with water and dry after use."),
            (
                "shipping",
                "Current tracking must be checked in the original sales channel.",
            ),
            (
                "refund",
                "A person must review return eligibility before confirming a refund.",
            ),
        ]
    ]
    changed = [row.copy() for row in product_rows]
    changed[0][5] = "19"
    return {
        "contract": "soloops-foundation-synthetic-v1",
        "data_identity": "synthetic",
        "generated_at": as_of.astimezone(UTC).isoformat(),
        "scope": {
            "start_at": stamp(24 * 7),
            "end_at": anchor.isoformat(),
            "timezone": "Asia/Shanghai",
            "currency": "USD",
            "data_identity": "synthetic",
            "channel": "amazon",
            "intent": "low_margin",
            "min_quantity": 1,
            "max_margin_percent": "20",
            "max_age_hours": 24,
        },
        "files": files,
        "policies": policies,
        "boundaries": {
            "duplicate_orders": csv_text(order_header, [orders[0], orders[0]]),
            "revised_products": csv_text(product_header, changed),
        },
        "expected": {
            "current_rows": {"products": 3, "orders": 5, "inventory": 3, "messages": 2},
            "amazon_usd": {
                "purchased_quantity": 4,
                "sales": "75",
                "cost": "62",
                "gross_profit": "13",
                "low_margin_skus": ["SYN-CUP"],
            },
            "all_channels_usd": {"sales": "87", "cost": None, "gross_profit": None},
            "amazon_revised_usd": {"sales": "75", "cost": "65", "gross_profit": "10"},
            "low_inventory_skus": ["SYN-CUP"],
            "expired_inventory_skus": ["SYN-BOX"],
            "task_count": 5,
            "sensitive_message": "SYN-MIXED",
            "faq_message": "SYN-FAQ",
            "external_status": "not_submitted",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", help="含偏移ISO时刻；默认当前UTC，只生成合成日期")
    parser.add_argument("--output", type=Path, help="新建输出目录；不会覆盖已有文件")
    args = parser.parse_args()
    data = samples(datetime.fromisoformat(args.as_of) if args.as_of else datetime.now(UTC))
    rendered = json.dumps(data, ensure_ascii=False, indent=2)
    if args.output is None:
        print(rendered)
        return
    args.output.mkdir(parents=True, exist_ok=False)
    for item in data["files"]:
        (args.output / item["filename"]).write_text(item["text"], encoding="utf-8")
    (args.output / "manifest.json").write_text(rendered + "\n", encoding="utf-8")
    (args.output / "orders-duplicate-synthetic.csv").write_text(
        data["boundaries"]["duplicate_orders"], encoding="utf-8"
    )
    (args.output / "products-revised-synthetic.csv").write_text(
        data["boundaries"]["revised_products"], encoding="utf-8"
    )
    print(f"已生成合成样本与预期：{args.output.resolve()}")


if __name__ == "__main__":
    main()
