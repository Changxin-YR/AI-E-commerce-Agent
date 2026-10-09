from app.core.errors import BusinessError
from app.models.fee_rules import FeeRule
from app.schemas.fee_rules import FeeMapping
from app.schemas.statements import FeeComparison, StatementItem


def map_fees(
    lines: list[StatementItem],
    comparisons: list[FeeComparison],
    rules: list[FeeRule],
) -> list[FeeMapping]:
    if len(rules) > 200:
        raise BusinessError("rule_limit", "此范围超过 200 条有效规则，请撤销不再适用的规则。", 422)
    by_name: dict[str, list[FeeRule]] = {}
    for rule in rules:
        if rule.content:
            by_name.setdefault(rule.content["fee_name"], []).append(rule)
    by_line = {line: comparison for comparison in comparisons for line in comparison.statement_ids}
    output = []
    for line in lines:
        if line.entry_type != "fee":
            continue
        matches = by_name.get(line.fee_name.strip(), [])
        item = FeeMapping(statement_id=line.id, status="unmapped")
        comparison = by_line[line.id]
        if len(matches) > 1 or comparison.status == "ambiguous":
            item.status = "ambiguous"
        elif comparison.status == "currency_mismatch":
            item.status = "currency_mismatch"
        elif matches:
            rule = matches[0]
            assert rule.content is not None
            item.category = rule.content["category"]
            item.rule_id, item.rule_version = rule.id, rule.version
            item.status = "mapped"
            if comparison.expenses and comparison.expenses[0].category != item.category:
                item.status = "category_conflict"
        output.append(item)
    return output
