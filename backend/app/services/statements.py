from collections import defaultdict
from decimal import Decimal

from app.core.errors import BusinessError, NotFoundError
from app.core.time import utc_now
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseScope
from app.schemas.statements import (
    FeeComparison,
    MatchedExpense,
    StatementItem,
    StatementReconciliation,
    StatementTotal,
)
from app.services.evidence import evidence_key
from app.services.expenses import naive_utc
from app.services.fee_mapping import map_fees
from app.services.profit_calculation import reference, utc_text


def compare_fees(lines: list[StatementItem], expenses: list[MatchedExpense]) -> list[FeeComparison]:
    statements_by_key: dict[str, list[StatementItem]] = defaultdict(list)
    expenses_by_key: dict[str, list[MatchedExpense]] = defaultdict(list)
    for line in lines:
        if line.entry_type == "fee":
            statements_by_key[evidence_key(line.evidence_ref)].append(line)
    for expense in expenses:
        expenses_by_key[evidence_key(expense.evidence_ref)].append(expense)
    output = []
    for key in sorted(statements_by_key.keys() | expenses_by_key.keys()):
        bills, fees = statements_by_key[key], expenses_by_key[key]
        status: str
        difference = None
        if len(bills) > 1 or len(fees) > 1:
            status = "ambiguous"
        elif not bills:
            status = "expense_only"
        elif not fees:
            status = "statement_only"
        elif bills[0].currency != fees[0].currency:
            status = "currency_mismatch"
        else:
            difference = bills[0].amount - fees[0].amount
            status = "matched" if difference == 0 else "amount_difference"
        output.append(
            FeeComparison.model_validate(
                {
                    "evidence_ref": bills[0].evidence_ref if bills else fees[0].evidence_ref,
                    "status": status,
                    "statement_ids": [line.id for line in bills],
                    "expenses": fees,
                    "difference": difference,
                }
            )
        )
    return sorted(output, key=lambda item: (item.evidence_ref.casefold(), item.status))


class StatementService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def reconcile(self, owner: int, shop: int, scope: ExpenseScope) -> StatementReconciliation:
        self.uow.identity.lock_user(owner)
        store = self.uow.identity.get_shop(owner, shop, lock=True)
        if store is None:
            raise NotFoundError()
        args = (
            owner,
            shop,
            scope.data_identity,
            scope.channel,
            naive_utc(scope.start_at),
            naive_utc(scope.end_at),
        )
        rows = self.uow.statements.period(*args)
        fees = self.uow.expenses.period(*args)
        if len(rows) > 1000 or len(fees) > 1000:
            raise BusinessError(
                "range_too_large", "核对最多 1000 行账单和 1000 笔费用，请缩短时间范围。", 422
            )
        statements = []
        totals: dict[tuple[str, str], StatementTotal] = {}
        for line, row, batch in rows:
            statements.append(
                StatementItem(
                    **(
                        row.normalized
                        | {"amount": line.amount, "occurred_at": utc_text(line.occurred_at)}
                    ),
                    id=line.id,
                    source=reference(row, batch),
                )
            )
            key = (line.currency, line.entry_type)
            if key not in totals:
                totals[key] = StatementTotal(
                    currency=line.currency, entry_type=line.entry_type, amount=Decimal(0), count=0
                )
            totals[key].amount += line.amount
            totals[key].count += 1
        expenses = []
        stale = withdrawn = 0
        for expense, revision in fees:
            if expense.status == "stale":
                stale += 1
            elif expense.status == "withdrawn":
                withdrawn += 1
            elif expense.status == "active":
                assert (
                    revision.snapshot is not None
                    and revision.amount is not None
                    and revision.occurred_at is not None
                )
                content = revision.snapshot["content"]
                expenses.append(
                    MatchedExpense(
                        id=expense.id,
                        version=expense.version,
                        label=content["label"],
                        category=content["category"],
                        allocation=expense.allocation,
                        evidence_ref=content["evidence_ref"],
                        amount=revision.amount,
                        currency=content["currency"],
                        occurred_at=utc_text(revision.occurred_at),
                    )
                )
        comparisons = compare_fees(statements, expenses)
        rules = self.uow.fee_rules.active(owner, shop, scope.data_identity, scope.channel)
        output = StatementReconciliation(
            scope=scope,
            source_revision=store.data_revision,
            rule_revision=self.uow.fee_rules.scope_revision(
                owner, shop, scope.data_identity, scope.channel
            ),
            calculated_at=utc_text(utc_now()),
            statements=statements,
            totals=[totals[key] for key in sorted(totals)],
            comparisons=comparisons,
            mappings=map_fees(statements, comparisons, rules),
            stale_expenses=stale,
            withdrawn_expenses=withdrawn,
            checks=[
                "收费名去首尾空白后区分大小写完整匹配当前人工规则；规则适用于同范围全部日期与币种。"
                "分类结果仅供核对，未知、重复、异币种与类别冲突保持待核，不新增费用或改变金额。",
                "两侧均按各自发生时间筛选半开窗口；只核对当前同店铺、数据身份与渠道的记录，跨期记录不自动寻找。",
                "费用凭据编号按 NFKC、大小写及空白规范化后精确匹配；"
                "同币种一对一才计算差额（账单费用减人工费用）。",
                "一致仅表示本次范围内的编号、币种和金额一致；收费类别、分摊、订单关系及业务适用性仍须人工核对。",
                "重复编号整组待核，不加总抵销；跨币种不换汇。待重核/撤销费用排除，清除的正文无法参与统计。",
                "销售款、退款、费用、平台记载回款分别合计，回款到账待核；结算周期、期初期末余额及文件覆盖完整性未知。",
                "结果为当前读取时点的本地核对，不保存已核对结论，不修改原账单或人工费用；无法确定净利润。",
            ],
        )
        self.uow.commit()
        return output
