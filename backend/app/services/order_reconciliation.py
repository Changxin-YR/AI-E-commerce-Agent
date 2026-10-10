from app.core.errors import BusinessError, NotFoundError
from app.core.time import utc_now
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.order_reconciliation import (
    OrderReconciliation,
    OrderReconciliationScope,
    ReconciliationOrder,
    ReconciliationStatement,
)
from app.services.import_groups import require_import_coverage
from app.services.order_comparison import compare_orders
from app.services.profit_calculation import reference, utc_text


def check_limit(count: int) -> None:
    if count > 1000:
        raise BusinessError(
            "range_too_large",
            "窗口及同订单关联来源各最多 1000 行订单、1000 行销售/退款账单；"
            "请缩短范围。单订单关联超限时需先在原文件核查，不能返回截断结论。",
            422,
        )


class OrderReconciliationService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    def reconcile(
        self, owner: int, shop: int, scope: OrderReconciliationScope
    ) -> OrderReconciliation:
        self.uow.identity.lock_user(owner)
        store = self.uow.identity.get_shop(owner, shop, lock=True)
        if store is None:
            raise NotFoundError()
        require_import_coverage(
            self.uow, owner, shop, scope.data_identity, {"orders", "statements"}, scope.channel
        )
        repo = self.uow.order_reconciliation
        window_orders = repo.orders(owner, shop, scope)
        window_statements = repo.statements(owner, shop, scope)
        check_limit(len(window_orders))
        check_limit(len(window_statements))
        keys = {o.order_id for o, _, _ in window_orders} | {
            s.order_id for s, _, _ in window_statements if s.order_id
        }
        orders = repo.orders(owner, shop, scope, keys) if keys else []
        statements = repo.statements(owner, shop, scope, keys) if keys else []
        statements.extend(item for item in window_statements if not item[0].order_id)
        check_limit(len(orders))
        check_limit(len(statements))
        window_order_ids = {o.id for o, _, _ in window_orders}
        window_statement_ids = {s.id for s, _, _ in window_statements}
        order_items = [
            ReconciliationOrder(
                id=line.id,
                order_id=line.order_id,
                line_id=line.line_id,
                sku=line.sku,
                quantity=line.quantity,
                unit_price=line.unit_price,
                currency=line.currency,
                ordered_at=utc_text(line.ordered_at),
                status=line.status,
                discount=line.discount,
                refund=line.refund,
                fulfillment_status=line.fulfillment_status,
                in_window=line.id in window_order_ids,
                source=reference(row, batch),
            )
            for line, row, batch in orders
        ]
        statement_items = [
            ReconciliationStatement(
                **(
                    row.normalized
                    | {"amount": line.amount, "occurred_at": utc_text(line.occurred_at)}
                ),
                id=line.id,
                in_window=line.id in window_statement_ids,
                source=reference(row, batch),
            )
            for line, row, batch in sorted(statements, key=lambda item: item[0].id)
        ]
        result = OrderReconciliation(
            scope=scope,
            source_revision=store.data_revision,
            calculated_at=utc_text(utc_now()),
            orders=order_items,
            statements=statement_items,
            comparisons=compare_orders(order_items, statement_items, scope),
            checks=[
                "候选按订单时间或账单发生时间选入半开窗口；同店铺/身份/渠道、"
                "同订单号全部当前行作为关联依据，范围外行只作待核背景。",
                "订单号按已导入原字符精确匹配，区分大小写及全半角；"
                "缺本地来源不代表业务缺失，文件覆盖完整性未知。",
                "销售口径由卖家声明两侧均为退款前、折后商品款，不含运费、税费及其他调整。"
                "只有窗内同当地日期、一对一、同币种、有效已支付状态且折扣已知才计算。",
                "可比订单金额 = 数量 × 折扣前单价 − 行折扣；差额 = 账单销售款 − 可比订单金额。"
                "行退款另列，不从原销售款中重复扣除；金额相同仅适用于本次所选口径。",
                "订单行退款是累计值，缺逐笔退款编号、发生时间、金额组成与支付状态；"
                "退款统一待核，不计算交易差额或确证退款完成。",
                "多行订单、多笔销售/退款、跨日和跨币种保留待核；不合计抵销或猜测分摊。"
                "物流费用差异、完整净利润、银行到账尚无法核实。",
                "本清单为读取时点的只读结果，来源变化后重新读取；不保存人工结论或修改原始记录。",
            ],
        )
        self.uow.commit()
        return result
