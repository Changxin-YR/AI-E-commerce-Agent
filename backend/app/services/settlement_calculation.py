from collections import defaultdict
from decimal import Decimal

from app.schemas.settlements import ManualReceipt, PayoutComparison
from app.schemas.statements import StatementItem, StatementTotal
from app.services.evidence import evidence_key


def compare_payouts(
    statements: list[StatementItem], receipts: list[ManualReceipt]
) -> list[PayoutComparison]:
    bills: dict[str, list[StatementItem]] = defaultdict(list)
    claims: dict[str, list[int]] = defaultdict(list)
    output = []
    for line in statements:
        if line.entry_type != "payout":
            continue
        if not line.evidence_ref:
            output.append(
                PayoutComparison(
                    payout_ref="",
                    status="missing_reference",
                    statement_ids=[line.id],
                    receipt_indexes=[],
                    difference=None,
                )
            )
        else:
            bills[evidence_key(line.evidence_ref)].append(line)
    for index, receipt in enumerate(receipts):
        claims[evidence_key(receipt.payout_ref)].append(index)
    for key in sorted(bills.keys() | claims.keys()):
        lines, indexes = bills[key], claims[key]
        difference = None
        if len(lines) > 1 or len(indexes) > 1:
            status = "ambiguous"
        elif not lines:
            status = "receipt_only"
        elif not indexes:
            status = "statement_only"
        elif lines[0].currency != receipts[indexes[0]].currency:
            status = "currency_mismatch"
        else:
            difference = lines[0].amount - receipts[indexes[0]].amount
            status = "matched" if difference == 0 else "amount_difference"
        output.append(
            PayoutComparison.model_validate(
                {
                    "payout_ref": lines[0].evidence_ref
                    if lines
                    else receipts[indexes[0]].payout_ref,
                    "status": status,
                    "statement_ids": [s.id for s in lines],
                    "receipt_indexes": indexes,
                    "difference": difference,
                }
            )
        )
    return output


def settlement_totals(
    statements: list[StatementItem], receipts: list[ManualReceipt]
) -> list[StatementTotal]:
    totals: dict[tuple[str, str], StatementTotal] = {}
    for currency, kind, amount in [(s.currency, s.entry_type, s.amount) for s in statements] + [
        (r.currency, "manual_receipt", r.amount) for r in receipts
    ]:
        key = (currency, kind)
        if key not in totals:
            totals[key] = StatementTotal(
                currency=currency, entry_type=kind, amount=Decimal(0), count=0
            )
        totals[key].amount += amount
        totals[key].count += 1
    return [totals[k] for k in sorted(totals)]
