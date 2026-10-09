from collections import Counter
from typing import TypeVar

from app.core.errors import BusinessError, ConflictError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.support import ReplyDraft, SupportPolicy
from app.repositories.support import MessageEvidence
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.support import (
    EditReply,
    GenerateReply,
    MessageFacts,
    OrderFact,
    PolicyData,
    PolicyInput,
    PolicyOutput,
    ReplyAction,
    ReplyOutput,
    ReplySnapshot,
    SupportCandidateInput,
    SupportPreparation,
    SupportWorkspace,
)
from app.services.listings import digest
from app.services.profit_calculation import reference, utc_text
from app.services.support_composition import compose_support
from app.services.support_rules import classify, prepare_reply

T = TypeVar("T")


def policy_output(item: SupportPolicy) -> PolicyOutput:
    availability = item.status
    if item.status == "active":
        availability = "effective"
        if item.valid_from > utc_now():
            availability = "future"
        elif item.valid_until is not None and item.valid_until <= utc_now():
            availability = "expired"
    return PolicyOutput(
        id=item.id,
        number=item.number,
        status=item.status,
        availability=availability,
        data=PolicyData.model_validate(item.payload) if item.payload else None,
        created_at=utc_text(item.created_at),
    )


def message_output(evidence: MessageEvidence) -> MessageFacts:
    m, r, b = evidence
    return MessageFacts(
        id=m.id,
        message_id=m.message_id,
        body=m.body,
        language=m.language,
        channel=m.channel,
        sent_at=utc_text(m.sent_at),
        order_id=m.order_id,
        source=reference(r, b),
    )


def reply_output(item: ReplyDraft) -> ReplyOutput:
    return ReplyOutput(
        id=item.id,
        version=item.version,
        status=item.status,
        source_status=item.source_status,
        engine=item.engine,
        snapshot=ReplySnapshot.model_validate(item.snapshot) if item.snapshot else None,
        created_at=utc_text(item.created_at),
        updated_at=utc_text(item.updated_at),
    )


class SupportService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.repo = uow.support

    def _finish(self, value: T) -> T:
        self.uow.commit()
        return value

    def _shop(self, owner: int, shop: int) -> Shop:
        self.uow.identity.lock_user(owner)
        item = self.uow.identity.get_shop(owner, shop, lock=True)
        if item is None:
            raise BusinessError("not_found", "店铺不存在", 404)
        self.repo.expire_policies(owner, shop)
        return item

    def _message(self, owner: int, shop: int, message_id: int) -> MessageFacts:
        item = self.repo.message(owner, shop, message_id)
        if item is None:
            raise BusinessError("not_found", "消息不存在或来源已撤销", 404)
        return message_output(item)

    def _draft(self, owner: int, shop: int, draft_id: int) -> ReplyDraft:
        item = self.repo.draft(owner, shop, draft_id)
        if item is None:
            raise BusinessError("not_found", "草稿不存在", 404)
        return item

    def messages(self, owner: int, shop: int, query: str, offset: int) -> list[MessageFacts]:
        self._shop(owner, shop)
        return self._finish(
            [message_output(m) for m in self.repo.messages(owner, shop, query, offset)]
        )

    def policies(self, owner: int, shop: int, query: str, offset: int) -> list[PolicyOutput]:
        self._shop(owner, shop)
        return self._finish(
            [policy_output(p) for p in self.repo.policies(owner, shop, query, offset)]
        )

    def save_policy(self, owner: int, shop: int, data: PolicyInput) -> PolicyOutput:
        self._shop(owner, shop)
        key = digest([shop, data.data.code])
        request_key = digest(
            [shop, data.model_dump(mode="json"), self.repo.policy_epoch(owner, shop, key)]
        )
        prior = self.repo.policy_request(owner, shop, request_key)
        if prior:
            return self._finish(policy_output(prior))
        latest = self.repo.latest_policy(owner, shop, key)
        expected = latest.id if latest and latest.status != "cleared" else None
        if expected != data.expected_policy_id:
            raise ConflictError("政策版本已变化，请打开最新版本再修改")
        if latest and latest.status != "cleared":
            latest.status = "superseded"
        item = SupportPolicy(
            owner_id=owner,
            shop_id=shop,
            policy_key=key,
            request_key=request_key,
            number=latest.number + 1 if latest else 1,
            status="active",
            valid_from=data.data.valid_from.replace(tzinfo=None),
            valid_until=data.data.valid_until.replace(tzinfo=None)
            if data.data.valid_until
            else None,
            payload=data.data.model_dump(mode="json"),
        )
        self.repo.add_policy(item)
        self.repo.invalidate(owner, shop, "policy")
        self.uow.agent.invalidate(owner, shop)
        self.uow.record_event(
            owner, "support.policy_saved", "support_policy", item.id, {"number": item.number}
        )
        return self._finish(policy_output(item))

    def clear_policy(self, owner: int, shop: int, policy_id: int) -> PolicyOutput:
        self._shop(owner, shop)
        item = self.repo.policy(owner, shop, policy_id)
        if item is None:
            raise BusinessError("not_found", "政策不存在", 404)
        if item.status != "cleared":
            self.repo.purge_policy(owner, shop, item.id)
            self.uow.agent.purge_policy(owner, shop, item.id)
            item.payload = None
            item.status = "cleared"
            self.uow.record_event(owner, "support.policy_cleared", "support_policy", item.id)
        return self._finish(policy_output(item))

    def _orders(self, owner: int, shop: int, message: MessageFacts) -> list[OrderFact]:
        if not message.order_id:
            return []
        evidence = self.repo.orders(
            owner, shop, message.order_id, message.source.data_identity, message.channel
        )
        if len(evidence) > 100:
            raise BusinessError("evidence_limit", "该订单超过 100 行，请拆分核验，未截断取证", 422)
        return [
            OrderFact(
                order_id=o.order_id,
                line_id=o.line_id,
                sku=o.sku,
                status=o.status,
                fulfillment_status=o.fulfillment_status,
                source=reference(r, b),
            )
            for o, r, b in evidence
        ]

    def _policies(self, owner: int, shop: Shop, message: MessageFacts) -> list[PolicyOutput]:
        items = self.repo.active_policies(owner, shop.id)
        if len(items) > 500:
            raise BusinessError("evidence_limit", "有效政策条目过多，请先整理知识库", 422)
        topics = set(classify(message.body)) & {"faq", "shipping", "refund", "warranty"}
        result = []
        for item in items:
            policy = policy_output(item)
            data = policy.data
            if (
                data
                and policy.availability == "effective"
                and data.topic in topics
                and (
                    data.market == shop.market
                    and data.channel == message.channel
                    and data.data_identity == message.source.data_identity
                    and data.language == message.language
                )
            ):
                result.append(policy)
        return result

    def workspace(self, owner: int, shop: int, message_id: int) -> SupportWorkspace:
        store = self._shop(owner, shop)
        message = self._message(owner, shop, message_id)
        key = digest([shop, message.channel, message.message_id])
        return self._finish(
            SupportWorkspace(
                message=message,
                orders=self._orders(owner, shop, message),
                policies=self._policies(owner, store, message),
                market=store.market,
                drafts=[reply_output(d) for d in self.repo.drafts(owner, shop, key)],
            )
        )

    def history(self, owner: int, shop: int) -> list[ReplyOutput]:
        self._shop(owner, shop)
        return self._finish([reply_output(d) for d in self.repo.drafts(owner, shop)])

    def get(self, owner: int, shop: int, draft_id: int) -> ReplyOutput:
        self._shop(owner, shop)
        return self._finish(reply_output(self._draft(owner, shop, draft_id)))

    def generate(self, owner: int, shop: int, message_id: int, data: GenerateReply) -> ReplyOutput:
        store = self._shop(owner, shop)
        message = self._message(owner, shop, message_id)
        if message.source.row_id != data.expected_source_row_id:
            raise ConflictError("消息来源已变化，请刷新后核对原文")
        orders = self._orders(owner, shop, message) if data.order_verified else []
        if data.order_verified and (
            not orders
            or sorted(o.source.row_id for o in orders) != sorted(data.expected_order_row_ids)
        ):
            raise ConflictError("订单证据已变化或没有匹配，请重新核验客户与订单关联")
        candidates = self._policies(owner, store, message)
        ids = set(data.policy_ids)
        selected = [p for p in candidates if p.id in ids]
        if len(selected) != len(ids):
            raise ConflictError("所选政策不适用、已过期或版本已变化，请刷新政策")
        conflicts = any(n > 1 for n in Counter(p.data.topic for p in candidates if p.data).values())
        key = digest([shop, message.channel, message.message_id])
        request_key = digest(
            [
                shop,
                message.source.row_id,
                sorted(o.source.row_id for o in orders),
                sorted(ids),
                [p.id for p in candidates],
                self.repo.epoch(owner, shop, key),
                "local_rules_v1",
            ]
        )
        prior = self.repo.draft_request(owner, shop, request_key)
        if prior:
            return self._finish(reply_output(prior))
        snapshot = prepare_reply(message, orders, data.order_verified, selected, conflicts)
        item = ReplyDraft(
            owner_id=owner,
            shop_id=shop,
            message_key=key,
            source_row_id=message.source.row_id,
            request_key=request_key,
            version=1,
            status="human_review" if snapshot.reasons else "draft",
            source_status="current",
            engine="local_rules",
            snapshot=snapshot.model_dump(mode="json"),
        )
        batches = {message.source.batch_id} | {o.source.batch_id for o in orders}
        self.repo.add_draft(item, batches, ids)
        self.uow.record_event(
            owner,
            "support.reply_created",
            "reply_draft",
            item.id,
            {"order_verified": data.order_verified, "intents": snapshot.intents},
        )
        return self._finish(reply_output(item))

    def prepare_candidate(
        self, owner: int, shop: int, message_id: int, data: GenerateReply
    ) -> SupportPreparation:
        store = self._shop(owner, shop)
        message = self._message(owner, shop, message_id)
        if message.source.row_id != data.expected_source_row_id:
            raise ConflictError("消息与同意发送的来源版本不同，请刷新后重新确认")
        orders = self._orders(owner, shop, message) if data.order_verified else []
        if data.order_verified and (
            not orders
            or sorted(o.source.row_id for o in orders) != sorted(data.expected_order_row_ids)
        ):
            raise ConflictError("订单证据已变化，请重新核验关联")
        candidates = self._policies(owner, store, message)
        selected = [p for p in candidates if p.id in data.policy_ids]
        if len(selected) != len(data.policy_ids):
            raise ConflictError("所选政策重复、不适用、已过期或版本变化")
        conflicts = any(n > 1 for n in Counter(p.data.topic for p in candidates if p.data).values())
        return self._finish(
            SupportPreparation(
                snapshot=prepare_reply(message, orders, data.order_verified, selected, conflicts),
                conflicts=conflicts,
            )
        )

    def save_candidate(self, owner: int, shop: int, data: SupportCandidateInput) -> ReplyOutput:
        with self.uow.defer_commits():
            prepared = self.prepare_candidate(owner, shop, data.message_id, data.context)
        if digest(prepared.model_dump(mode="json")) != data.preparation_hash:
            raise ConflictError("客服依据已变化，请重新审阅候选")
        try:
            snapshot = compose_support(prepared, data.selection)
        except ValueError as error:
            raise BusinessError("invalid_model_output", "客服候选未通过事实校验", 422) from error
        message = snapshot.message
        key = digest([shop, message.channel, message.message_id])
        request_key = digest(
            [
                shop,
                data.model_dump(mode="json"),
                self.repo.epoch(owner, shop, key),
            ]
        )
        prior = self.repo.draft_request(owner, shop, request_key)
        if prior:
            return self._finish(reply_output(prior))
        item = ReplyDraft(
            owner_id=owner,
            shop_id=shop,
            message_key=key,
            source_row_id=message.source.row_id,
            request_key=request_key,
            version=1,
            status="human_review" if snapshot.reasons else "draft",
            source_status="current",
            engine=data.engine,
            snapshot=snapshot.model_dump(mode="json"),
        )
        self.repo.add_draft(
            item,
            {message.source.batch_id} | {o.source.batch_id for o in snapshot.orders},
            {p.id for p in prepared.snapshot.policies},
        )
        self.uow.record_event(
            owner,
            "support.model_candidate_saved",
            "reply_draft",
            item.id,
            {"order_verified": snapshot.order_verified, "intents": snapshot.intents},
        )
        return self._finish(reply_output(item))

    def edit(self, owner: int, shop: int, draft_id: int, data: EditReply) -> ReplyOutput:
        self._shop(owner, shop)
        item = self._draft(owner, shop, draft_id)
        if item.source_status != "current" or item.snapshot is None:
            raise ConflictError("草稿来源已失效，请从当前消息重新核验并建稿")
        if item.status == "archived":
            raise ConflictError("请先重新打开草稿，再修改")
        snapshot = ReplySnapshot.model_validate(item.snapshot)
        if snapshot.reply == data.reply:
            return self._finish(reply_output(item))
        if item.version != data.expected_version:
            raise ConflictError("草稿已被修改，请刷新后合并您的内容")
        snapshot.reply = data.reply
        item.snapshot = snapshot.model_dump(mode="json")
        item.engine = "manual"
        item.version += 1
        item.updated_at = utc_now()
        self.uow.record_event(
            owner, "support.reply_edited", "reply_draft", item.id, {"version": item.version}
        )
        return self._finish(reply_output(item))

    def act(self, owner: int, shop: int, draft_id: int, data: ReplyAction) -> ReplyOutput:
        self._shop(owner, shop)
        item = self._draft(owner, shop, draft_id)
        target = "archived" if data.action == "archive" else "human_review"
        if item.status == target:
            return self._finish(reply_output(item))
        if item.version != data.expected_version:
            raise ConflictError("处理状态已变化，请刷新后重试")
        if item.source_status == "cleared":
            raise ConflictError("来源已清除，只有无正文处理记录")
        if item.source_status != "current" and target != "archived":
            raise ConflictError("来源已失效，请从当前消息重新建稿")
        item.status = target
        item.version += 1
        item.updated_at = utc_now()
        self.uow.record_event(
            owner, "support." + data.action, "reply_draft", item.id, {"version": item.version}
        )
        return self._finish(reply_output(item))
