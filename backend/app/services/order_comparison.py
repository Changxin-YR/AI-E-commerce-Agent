from collections import defaultdict
from typing import Literal
from zoneinfo import ZoneInfo

from app.schemas.order_reconciliation import (
    OrderComparison,
    OrderReconciliationScope,
    ReconciliationOrder,
    ReconciliationStatement,
)
from app.services.profit_calculation import PAID_STATUSES


def compare_group(
    order_id: str,
    kind: Literal["sale", "refund"],
    orders: list[ReconciliationOrder],
    statements: list[ReconciliationStatement],
    scope: OrderReconciliationScope,
) -> OrderComparison:
    reasons = []
    if not order_id:
        reasons.append("missing_order_reference")
    if not orders:
        reasons.append("order_not_imported")
    if not statements:
        reasons.append("statement_not_imported")
    if len(orders) > 1:
        reasons.append("multiple_order_lines")
    if len(statements) > 1:
        reasons.append("multiple_statement_lines")
    all_items: list[ReconciliationOrder | ReconciliationStatement] = [*orders, *statements]
    if any(not item.in_window for item in all_items):
        reasons.append("outside_window")
    currencies = {item.currency for item in all_items}
    if len(currencies) > 1:
        reasons.append("currency_mismatch")
    if any(item.status not in PAID_STATUSES for item in orders):
        reasons.append("order_status_uncomparable")
    if kind == "refund":
        # An order-line cumulative refund is not an individual dated payment transaction.
        reasons.append("refund_transaction_unknown")
        if any(item.refund is None for item in orders):
            reasons.append("refund_amount_unknown")
    else:
        if scope.sale_basis == "unknown":
            reasons.append("sale_basis_unknown")
        if any(item.discount is None for item in orders):
            reasons.append("discount_unknown")
        if len(orders) == len(statements) == 1:
            zone = ZoneInfo(scope.timezone)
            if (
                orders[0].ordered_at.astimezone(zone).date()
                != statements[0].occurred_at.astimezone(zone).date()
            ):
                reasons.append("different_local_date")
    result = OrderComparison(
        order_id=order_id,
        entry_type=kind,
        statement_ids=[item.id for item in statements],
        order_line_ids=[item.id for item in orders],
        status="pending",
        reasons=reasons,
    )
    if not reasons:
        order = orders[0]
        assert order.discount is not None
        result.order_amount = order.quantity * order.unit_price - order.discount
        result.difference = statements[0].amount - result.order_amount
        result.currency = order.currency
        result.status = "matched" if result.difference == 0 else "amount_difference"
    return result


def compare_orders(
    orders: list[ReconciliationOrder],
    statements: list[ReconciliationStatement],
    scope: OrderReconciliationScope,
) -> list[OrderComparison]:
    orders_by_key: dict[str, list[ReconciliationOrder]] = defaultdict(list)
    statements_by_key: dict[tuple[str, str], list[ReconciliationStatement]] = defaultdict(list)
    for order in orders:
        orders_by_key[order.order_id].append(order)
    for line in statements:
        if line.order_id:
            statements_by_key[(line.order_id, line.entry_type)].append(line)
    keys = sorted(orders_by_key.keys() | {key[0] for key in statements_by_key})
    output = []
    kinds: tuple[Literal["sale", "refund"], ...] = ("sale", "refund")
    for key in keys:
        group = orders_by_key[key]
        for kind in kinds:
            bills = statements_by_key[(key, kind)]
            # Only window seeds create checklist entries. Other dates provide context only.
            order_seed = any(
                o.in_window
                and (
                    kind == "sale"
                    or o.refund is None
                    or o.refund > 0
                    or o.status in {"refunded", "partially_refunded"}
                )
                for o in group
            )
            if order_seed or any(b.in_window for b in bills):
                output.append(compare_group(key, kind, group, bills, scope))
    for line in statements:
        if not line.order_id and line.in_window:
            assert line.entry_type in {"sale", "refund"}
            kind = "sale" if line.entry_type == "sale" else "refund"
            output.append(compare_group("", kind, [], [line], scope))
    return output
