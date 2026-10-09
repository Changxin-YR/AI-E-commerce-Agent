from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unicodedata import normalize
from zoneinfo import ZoneInfo

from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.expenses import Expense, ExpenseRevision
from app.models.identity import Shop
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import (
    ExpenseContent,
    ExpenseControl,
    ExpenseHistory,
    ExpenseOrder,
    ExpenseOrders,
    ExpensePage,
    ExpenseSaved,
    ExpenseScope,
    ExpenseSnapshot,
    ExpenseSummary,
    ExpenseTotal,
    ExpenseWrite,
)
from app.services.product_quality import digest
from app.services.profit_calculation import reference, utc_text


def naive_utc(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(tzinfo=None)


class ExpenseService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.expenses

    def _shop(self, owner: int, shop: int) -> Shop:
        self.uow.identity.lock_user(owner)
        store = self.uow.identity.get_shop(owner, shop, lock=True)
        if store is None:
            raise NotFoundError()
        return store

    def _expense(self, owner: int, shop: int, expense_id: int) -> Expense:
        expense = self.repo.get(owner, shop, expense_id)
        if expense is None:
            raise NotFoundError()
        return expense

    def _snapshot(self, revision: ExpenseRevision) -> ExpenseSnapshot | None:
        if revision.snapshot is None or revision.amount is None or revision.occurred_at is None:
            return None
        stored = revision.snapshot
        zone = ZoneInfo(stored["content"]["timezone"])
        return ExpenseSnapshot.model_validate(
            {
                **stored,
                "content": {
                    **stored["content"],
                    "amount": revision.amount,
                    "occurred_at": revision.occurred_at.replace(tzinfo=UTC).astimezone(zone),
                },
            }
        )

    def _output(self, expense: Expense, full: bool = True) -> ExpenseSaved:
        revisions = self.repo.revisions(expense)
        current = next((r for r in revisions if r.version == expense.content_version), None)
        return ExpenseSaved(
            id=expense.id,
            shop_id=expense.shop_id,
            data_identity=expense.data_identity,
            channel=expense.channel,
            version=expense.version,
            status=expense.status,
            created_at=utc_text(expense.created_at),
            snapshot=self._snapshot(current) if current else None,
            history=[
                ExpenseHistory(
                    version=r.version,
                    action=r.action,
                    created_at=utc_text(r.created_at),
                    snapshot=self._snapshot(r),
                )
                for r in revisions
            ]
            if full
            else [],
        )

    def _replay(
        self, owner: int, shop: int, request: str, request_hash: str
    ) -> ExpenseSaved | None:
        previous = self.repo.by_request(owner, request)
        if previous is None:
            return None
        if previous.request_hash != request_hash:
            raise ConflictError("请求标识已用于另一项费用操作。")
        return self._output(self._expense(owner, shop, previous.expense_id))

    def write(
        self, owner: int, shop: int, data: ExpenseWrite, expense_id: int | None = None
    ) -> ExpenseSaved:
        store = self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "expense": expense_id,
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        if expense_id is None:
            if data.version != 0:
                raise ConflictError("新费用不能指定已有版本。")
            expense = Expense(
                owner_id=owner,
                shop_id=shop,
                data_identity=data.data_identity,
                channel=data.channel,
                allocation=data.content.allocation,
                version=1,
                content_version=1,
                status="active",
            )
            action = "create"
        else:
            expense = self._expense(owner, shop, expense_id)
            if (
                expense.version != data.version
                or expense.status not in {"active", "stale"}
                or expense.data_identity != data.data_identity
                or expense.channel != data.channel
            ):
                raise ConflictError("费用版本或范围已变化，或记录已撤销/清除，请刷新。")
            if len(self.repo.revisions(expense)) >= 100:
                raise BusinessError(
                    "revision_limit", "每笔最多 100 次录入/修订，请撤销后新建。", 422
                )
            expense.version += 1
            expense.content_version = expense.version
            action = "update"
        content = data.content
        key = digest(
            {"reference": " ".join(normalize("NFKC", content.evidence_ref).casefold().split())}
        )
        if self.repo.duplicate(expense, key):
            raise ConflictError("该店铺、身份和渠道已有相同凭据编号，请核对原费用并修订。")
        snapshot = self._evidence(owner, store, data)
        expense.evidence_key = key
        expense.status = "active"
        expense.allocation = content.allocation
        if expense_id is None:
            self.repo.add(expense)
        self.repo.add_revision(
            ExpenseRevision(
                expense_id=expense.id,
                owner_id=owner,
                version=expense.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                amount=content.amount,
                occurred_at=naive_utc(content.occurred_at),
                snapshot=snapshot.model_dump(
                    mode="json", exclude={"content": {"amount", "occurred_at"}}
                ),
            ),
            snapshot.source.batch_id if snapshot.source else None,
        )
        self.uow.record_event(
            owner, f"expense.{action}", "expense", expense.id, {"version": expense.version}
        )
        output = self._output(expense)
        self.uow.commit()
        return output

    def _evidence(self, owner: int, store: Shop, data: ExpenseWrite) -> ExpenseSnapshot:
        content: ExpenseContent = data.content
        if naive_utc(content.occurred_at) > utc_now() + timedelta(minutes=5):
            raise BusinessError("future_expense", "实际费用须已发生，请核对发生时间与时区。", 422)
        snapshot = ExpenseSnapshot(content=content)
        if content.allocation == "order_line":
            rows = self.repo.orders(
                owner, store.id, data.data_identity, data.channel, line=content.order_line_id
            )
            if (
                not rows
                or rows[0][1].id != content.expected_source_row_id
                or store.data_revision != content.expected_source_revision
            ):
                raise ConflictError("订单来源或店铺数据已变化，请重新查找并核对订单。")
            order, row, batch = rows[0]
            if order.currency != content.currency:
                raise BusinessError(
                    "currency_mismatch", "直接归属订单行须使用订单币种；本片不换汇。", 422
                )
            snapshot.source = reference(row, batch)
            snapshot.order_id, snapshot.line_id = order.order_id, order.line_id
            snapshot.sku, snapshot.order_status = order.sku, order.status
        return snapshot

    def get(self, owner: int, shop: int, expense_id: int) -> ExpenseSaved:
        self._shop(owner, shop)
        output = self._output(self._expense(owner, shop, expense_id))
        self.uow.commit()
        return output

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> ExpensePage:
        self._shop(owner, shop)
        rows = self.repo.page(owner, shop, identity, channel, before)
        output = ExpensePage(
            items=[self._output(e, False) for e in rows[:20]],
            next_cursor=rows[19].id if len(rows) > 20 else None,
        )
        self.uow.commit()
        return output

    def orders(
        self, owner: int, shop: int, identity: str, channel: str, order_id: str
    ) -> ExpenseOrders:
        store = self._shop(owner, shop)
        rows = self.repo.orders(owner, shop, identity, channel, order_id=order_id)
        if len(rows) > 100:
            raise BusinessError("order_too_large", "该订单超过 100 行，暂不能直接关联。", 422)
        output = ExpenseOrders(
            source_revision=store.data_revision,
            items=[
                ExpenseOrder(
                    id=o.id,
                    order_id=o.order_id,
                    line_id=o.line_id,
                    sku=o.sku,
                    currency=o.currency,
                    status=o.status,
                    source=reference(r, b),
                )
                for o, r, b in rows
            ],
        )
        self.uow.commit()
        return output

    def control(
        self, owner: int, shop: int, expense_id: int, action: str, data: ExpenseControl
    ) -> ExpenseSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "expense": expense_id,
                "action": action,
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        expense = self._expense(owner, shop, expense_id)
        if expense.version != data.version:
            raise ConflictError("费用已变化，请刷新后核对。")
        if expense.status == "cleared" or action == "withdraw" and expense.status == "withdrawn":
            output = self._output(expense)
            self.uow.commit()
            return output
        if action == "clear":
            self.repo.clear(expense)
        else:
            expense.status = "withdrawn"
            expense.evidence_key = None
            expense.version += 1
        self.repo.add_revision(
            ExpenseRevision(
                expense_id=expense.id,
                owner_id=owner,
                version=expense.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                snapshot=None,
                amount=None,
                occurred_at=None,
            )
        )
        self.uow.record_event(
            owner, f"expense.{action}", "expense", expense.id, {"version": expense.version}
        )
        output = self._output(expense)
        self.uow.commit()
        return output

    def summary(self, owner: int, shop: int, scope: ExpenseScope) -> ExpenseSummary:
        self._shop(owner, shop)
        rows = self.repo.period(
            owner,
            shop,
            scope.data_identity,
            scope.channel,
            naive_utc(scope.start_at),
            naive_utc(scope.end_at),
        )
        if len(rows) > 1000:
            raise BusinessError("range_too_large", "该时间范围超过 1000 笔，请缩短区间。", 422)
        totals: dict[tuple[str, str, str], ExpenseTotal] = {}
        included = stale = withdrawn = 0
        for expense, revision in rows:
            if expense.status == "stale":
                stale += 1
                continue
            if expense.status == "withdrawn":
                withdrawn += 1
                continue
            snapshot = self._snapshot(revision)
            assert snapshot is not None
            c = snapshot.content
            key = (c.currency, c.category, c.allocation)
            if key not in totals:
                totals[key] = ExpenseTotal(
                    currency=c.currency,
                    category=c.category,
                    allocation=c.allocation,
                    amount=Decimal(0),
                    count=0,
                )
            totals[key].amount += c.amount
            totals[key].count += 1
            included += 1
        output = ExpenseSummary(
            scope=scope,
            totals=[totals[k] for k in sorted(totals)],
            included_count=included,
            stale_count=stale,
            withdrawn_count=withdrawn,
            checks=[
                "按费用发生时间统计当前有效版本，分币种、类别及归属，不换汇。",
                "人工凭据尚未与平台账单、物流账单或回款核对；费用完整性未知。",
                "店铺费用未分摊至 SKU；订单行费用全额直接归属，费用不随订单数量相乘。",
                "待重核和已撤销费用不计入；已清除内容无法参与统计。",
                "此处仅为已录入费用合计；既有销售毛利和新品假设保持独立，无法确定净利润。",
            ],
        )
        self.uow.commit()
        return output
