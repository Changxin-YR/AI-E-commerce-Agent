from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models.statement_reviews import StatementReview, StatementReviewRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseControl
from app.schemas.order_statement_reviews import (
    OrderReviewConclusion,
    OrderReviewCurrent,
    OrderReviewDraft,
    OrderReviewHistory,
    OrderReviewPage,
    OrderReviewPreview,
    OrderReviewSaved,
    OrderReviewSnapshot,
    OrderReviewWrite,
)
from app.services.order_reconciliation import OrderReconciliationService
from app.services.product_quality import digest
from app.services.profit_calculation import utc_text


class OrderStatementReviewService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.statement_reviews

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _review(self, owner: int, shop: int, review: int) -> StatementReview:
        item = self.repo.get(owner, shop, review)
        if item is None or item.kind != "orders":
            raise NotFoundError()
        return item

    def _output(
        self, review: StatementReview, full: bool = True, version: int | None = None
    ) -> OrderReviewSaved:
        revision = self.repo.revision(review, version or review.content_version) if full else None
        if version is not None and revision is None:
            raise NotFoundError()
        return OrderReviewSaved(
            id=review.id,
            shop_id=review.shop_id,
            data_identity=review.data_identity,
            channel=review.channel,
            status=review.status,
            version=review.version,
            content_version=review.content_version,
            created_at=utc_text(review.created_at),
            snapshot=OrderReviewSnapshot.model_validate(revision.snapshot)
            if revision and revision.snapshot
            else None,
            history=[
                OrderReviewHistory(
                    version=v,
                    action=a,
                    created_at=utc_text(t),
                    conclusion=OrderReviewConclusion.model_validate(c) if c else None,
                )
                for v, a, t, c in self.repo.history(review)
            ]
            if full
            else [],
        )

    def _preview(self, owner: int, shop: int, data: OrderReviewDraft) -> OrderReviewPreview:
        self._shop(owner, shop)
        if data.review_id:
            review = self._review(owner, shop, data.review_id)
            if (
                review.status not in {"active", "stale"}
                or review.version != data.version
                or review.data_identity != data.scope.data_identity
                or review.channel != data.scope.channel
            ):
                raise ConflictError("核对记录版本或范围已变化，请重新读取。")
            if len(self.repo.history(review)) >= 100:
                raise BusinessError(
                    "revision_limit", "每份核对存档最多 100 次保存，仍可撤销或清除。", 422
                )
        elif data.version:
            raise ConflictError("新存档版本必须为零。")
        with self.uow.defer_commits():
            result = OrderReconciliationService(self.uow).reconcile(owner, shop, data.scope)
        blockers = []
        if not result.comparisons:
            blockers.append("范围内没有订单核对候选，不能确认一致或差异已说明。")
        if any(c.status == "pending" for c in result.comparisons):
            blockers.append("存在口径、关联、退款、跨期或币种待核事项。")
        differences = any(c.status == "amount_difference" for c in result.comparisons)
        if data.conclusion.outcome != "pending" and blockers:
            raise BusinessError("review_unresolved", "仍有待核事项，只能保存待核结论。", 422)
        if data.conclusion.outcome == "consistent" and differences:
            raise BusinessError("review_difference", "金额存在差异，请说明差异或保持待核。", 422)
        if data.conclusion.outcome == "differences_recorded" and not differences:
            raise BusinessError("review_no_difference", "当前没有可说明的一对一金额差异。", 422)
        snapshot = OrderReviewSnapshot(conclusion=data.conclusion, result=result, blockers=blockers)
        if len(snapshot.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
            raise BusinessError("snapshot_too_large", "存档依据超过 2 MiB，请缩短核对范围。", 422)
        payload = snapshot.model_dump(mode="json")
        del payload["result"]["calculated_at"]
        return OrderReviewPreview(
            snapshot=snapshot,
            preview_hash=digest(
                {
                    "contract": "order-statement-review-v1",
                    "shop": shop,
                    "draft": data.model_dump(mode="json"),
                    "snapshot": payload,
                }
            ),
        )

    def preview(self, owner: int, shop: int, data: OrderReviewDraft) -> OrderReviewPreview:
        output = self._preview(owner, shop, data)
        self.uow.commit()
        return output

    def _replay(
        self, owner: int, shop: int, request: str, request_hash: str
    ) -> OrderReviewSaved | None:
        previous = self.repo.by_request(owner, request)
        if previous is None:
            return None
        if previous.request_hash != request_hash:
            raise ConflictError("请求标识已用于另一项核对存档操作。")
        return self._output(self._review(owner, shop, previous.review_id))

    def write(self, owner: int, shop: int, data: OrderReviewWrite) -> OrderReviewSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "action": "write",
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        draft = OrderReviewDraft.model_validate(
            data.model_dump(exclude={"request_id", "confirm", "preview_hash"})
        )
        current = self._preview(owner, shop, draft)
        if current.preview_hash != data.preview_hash:
            raise ConflictError("订单、账单、口径或结论已变化，请重新预览并确认。")
        if data.review_id:
            review = self._review(owner, shop, data.review_id)
            review.version += 1
            review.content_version = review.version
            review.status = "active"
        else:
            review = StatementReview(
                kind="orders",
                owner_id=owner,
                shop_id=shop,
                data_identity=data.scope.data_identity,
                channel=data.scope.channel,
                status="active",
                version=1,
                content_version=1,
            )
            self.repo.add(review)
        action = "update" if data.review_id else "create"
        self.repo.revise(
            StatementReviewRevision(
                review_id=review.id,
                owner_id=owner,
                version=review.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                snapshot=current.snapshot.model_dump(mode="json"),
            )
        )
        self.repo.dependencies(
            review,
            {s.source.batch_id for s in current.snapshot.result.statements}
            | {o.source.batch_id for o in current.snapshot.result.orders},
            set(),
            set(),
        )
        self.uow.record_event(
            owner,
            f"order_statement_review.{action}",
            "order_statement_review",
            review.id,
            {"version": review.version},
        )
        output = self._output(review)
        self.uow.commit()
        return output

    def get(
        self, owner: int, shop: int, review: int, version: int | None = None
    ) -> OrderReviewSaved:
        self._shop(owner, shop)
        output = self._output(self._review(owner, shop, review), version=version)
        self.uow.commit()
        return output

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> OrderReviewPage:
        self._shop(owner, shop)
        rows = self.repo.page(owner, shop, identity, channel, before, kind="orders")
        output = OrderReviewPage(
            items=[self._output(r, False) for r in rows[:20]],
            next_cursor=rows[19].id if len(rows) > 20 else None,
        )
        self.uow.commit()
        return output

    def current(self, owner: int, shop: int, review_id: int) -> OrderReviewCurrent:
        self._shop(owner, shop)
        review = self._review(owner, shop, review_id)
        saved = self._output(review)
        if saved.snapshot is None:
            self.uow.commit()
            return OrderReviewCurrent(record=saved, preview=None)
        # A current read is evidence only and never changes the saved conclusion/status.
        output = self._preview(
            owner,
            shop,
            OrderReviewDraft(
                scope=saved.snapshot.result.scope,
                conclusion=OrderReviewConclusion(
                    outcome="pending", note="当前依据回读，尚未重新确认。"
                ),
            ),
        )
        self.uow.commit()
        return OrderReviewCurrent(record=saved, preview=output)

    def control(
        self, owner: int, shop: int, review_id: int, action: str, data: ExpenseControl
    ) -> OrderReviewSaved:
        self._shop(owner, shop)
        request_hash = digest(
            {
                "shop": shop,
                "review": review_id,
                "action": action,
                **data.model_dump(mode="json", exclude={"request_id"}),
            }
        )
        replay = self._replay(owner, shop, str(data.request_id), request_hash)
        if replay:
            self.uow.commit()
            return replay
        review = self._review(owner, shop, review_id)
        if review.version != data.version:
            raise ConflictError("核对存档版本已变化，请刷新。")
        if review.status == "cleared" or (action == "withdraw" and review.status == "withdrawn"):
            output = self._output(review)
            self.uow.commit()
            return output
        if action == "clear":
            self.repo.clear(review)
        else:
            review.status = "withdrawn"
            review.version += 1
        self.repo.revise(
            StatementReviewRevision(
                review_id=review.id,
                owner_id=owner,
                version=review.version,
                request_id=str(data.request_id),
                request_hash=request_hash,
                action=action,
                snapshot=None,
            )
        )
        self.uow.record_event(
            owner,
            f"order_statement_review.{action}",
            "order_statement_review",
            review.id,
            {"version": review.version},
        )
        output = self._output(review)
        self.uow.commit()
        return output
