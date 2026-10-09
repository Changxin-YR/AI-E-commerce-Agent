from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.models.statement_reviews import StatementReview, StatementReviewRevision
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.expenses import ExpenseControl
from app.schemas.statement_reviews import (
    ReviewConclusion,
    ReviewCurrent,
    ReviewDraft,
    ReviewHistory,
    ReviewPage,
    ReviewPreview,
    ReviewSaved,
    ReviewSnapshot,
    ReviewWrite,
)
from app.services.expenses import naive_utc
from app.services.product_quality import digest
from app.services.profit_calculation import utc_text
from app.services.statements import StatementService


class StatementReviewService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.statement_reviews

    def _shop(self, owner: int, shop: int) -> None:
        self.uow.identity.lock_user(owner)
        if self.uow.identity.get_shop(owner, shop, lock=True) is None:
            raise NotFoundError()

    def _review(self, owner: int, shop: int, review: int) -> StatementReview:
        item = self.repo.get(owner, shop, review)
        if item is None:
            raise NotFoundError()
        return item

    def _output(
        self, review: StatementReview, full: bool = True, version: int | None = None
    ) -> ReviewSaved:
        revision = self.repo.revision(review, version or review.content_version) if full else None
        if version is not None and revision is None:
            raise NotFoundError()
        return ReviewSaved(
            id=review.id,
            shop_id=review.shop_id,
            data_identity=review.data_identity,
            channel=review.channel,
            status=review.status,
            version=review.version,
            content_version=review.content_version,
            created_at=utc_text(review.created_at),
            snapshot=ReviewSnapshot.model_validate(revision.snapshot)
            if revision and revision.snapshot
            else None,
            history=[
                ReviewHistory(
                    version=v,
                    action=a,
                    created_at=utc_text(t),
                    conclusion=ReviewConclusion.model_validate(c) if c else None,
                )
                for v, a, t, c in self.repo.history(review)
            ]
            if full
            else [],
        )

    def _preview(self, owner: int, shop: int, data: ReviewDraft) -> ReviewPreview:
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
            result = StatementService(self.uow).reconcile(owner, shop, data.scope)
        blockers = []
        if not result.comparisons:
            blockers.append("范围内没有可核对的费用，不能确认一致或差异已说明。")
        if any(c.status not in {"matched", "amount_difference"} for c in result.comparisons):
            blockers.append("存在缺失一侧、重复凭据或异币种记录。")
        if any(m.status != "mapped" for m in result.mappings):
            blockers.append("存在未知收费分类、重复凭据、异币种或类别冲突。")
        if result.stale_expenses or result.withdrawn_expenses:
            blockers.append("范围内有待重核或已撤销费用未参与比较。")
        differences = any(c.status == "amount_difference" for c in result.comparisons)
        if data.conclusion.outcome != "pending" and blockers:
            raise BusinessError("review_unresolved", "仍有待核事项，只能保存待核结论。", 422)
        if data.conclusion.outcome == "consistent" and differences:
            raise BusinessError("review_difference", "金额存在差异，请说明差异或保持待核。", 422)
        if data.conclusion.outcome == "differences_recorded" and not differences:
            raise BusinessError("review_no_difference", "当前没有可说明的一对一金额差异。", 422)
        snapshot = ReviewSnapshot(
            conclusion=data.conclusion,
            result=result,
            expense_revision=self.uow.expenses.scope_revision(
                owner, shop, data.scope.data_identity, data.scope.channel
            ),
            blockers=blockers,
        )
        if len(snapshot.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
            raise BusinessError("snapshot_too_large", "存档依据超过 2 MiB，请缩短核对范围。", 422)
        payload = snapshot.model_dump(mode="json")
        del payload["result"]["calculated_at"]
        return ReviewPreview(
            snapshot=snapshot,
            preview_hash=digest(
                {
                    "contract": "statement-review-v1",
                    "shop": shop,
                    "draft": data.model_dump(mode="json"),
                    "snapshot": payload,
                }
            ),
        )

    def preview(self, owner: int, shop: int, data: ReviewDraft) -> ReviewPreview:
        output = self._preview(owner, shop, data)
        self.uow.commit()
        return output

    def _replay(self, owner: int, shop: int, request: str, request_hash: str) -> ReviewSaved | None:
        previous = self.repo.by_request(owner, request)
        if previous is None:
            return None
        if previous.request_hash != request_hash:
            raise ConflictError("请求标识已用于另一项核对存档操作。")
        return self._output(self._review(owner, shop, previous.review_id))

    def write(self, owner: int, shop: int, data: ReviewWrite) -> ReviewSaved:
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
        draft = ReviewDraft.model_validate(
            data.model_dump(exclude={"request_id", "confirm", "preview_hash"})
        )
        current = self._preview(owner, shop, draft)
        if current.preview_hash != data.preview_hash:
            raise ConflictError("账单、费用、规则或结论已变化，请重新预览并确认。")
        if data.review_id:
            review = self._review(owner, shop, data.review_id)
            review.version += 1
            review.content_version = review.version
            review.status = "active"
        else:
            review = StatementReview(
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
        scope = data.scope
        expenses = self.uow.expenses.period(
            owner,
            shop,
            scope.data_identity,
            scope.channel,
            naive_utc(scope.start_at),
            naive_utc(scope.end_at),
        )
        rules = self.uow.fee_rules.active(owner, shop, scope.data_identity, scope.channel)
        self.repo.dependencies(
            review,
            {s.source.batch_id for s in current.snapshot.result.statements},
            {e.id for e, _ in expenses},
            {r.id for r in rules},
        )
        self.uow.record_event(
            owner,
            f"statement_review.{action}",
            "statement_review",
            review.id,
            {"version": review.version},
        )
        output = self._output(review)
        self.uow.commit()
        return output

    def get(self, owner: int, shop: int, review: int, version: int | None = None) -> ReviewSaved:
        self._shop(owner, shop)
        output = self._output(self._review(owner, shop, review), version=version)
        self.uow.commit()
        return output

    def page(
        self, owner: int, shop: int, identity: str, channel: str, before: int | None
    ) -> ReviewPage:
        self._shop(owner, shop)
        rows = self.repo.page(owner, shop, identity, channel, before)
        output = ReviewPage(
            items=[self._output(r, False) for r in rows[:20]],
            next_cursor=rows[19].id if len(rows) > 20 else None,
        )
        self.uow.commit()
        return output

    def current(self, owner: int, shop: int, review_id: int) -> ReviewCurrent:
        self._shop(owner, shop)
        review = self._review(owner, shop, review_id)
        saved = self._output(review)
        if saved.snapshot is None:
            self.uow.commit()
            return ReviewCurrent(record=saved, preview=None)
        # A current read is evidence only and never changes the saved conclusion/status.
        output = self._preview(
            owner,
            shop,
            ReviewDraft(
                scope=saved.snapshot.result.scope,
                conclusion=ReviewConclusion(outcome="pending", note="当前依据回读，尚未重新确认。"),
            ),
        )
        self.uow.commit()
        return ReviewCurrent(record=saved, preview=output)

    def control(
        self, owner: int, shop: int, review_id: int, action: str, data: ExpenseControl
    ) -> ReviewSaved:
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
            f"statement_review.{action}",
            "statement_review",
            review.id,
            {"version": review.version},
        )
        output = self._output(review)
        self.uow.commit()
        return output
