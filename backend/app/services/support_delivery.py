from app.core.errors import BusinessError, ConflictError
from app.core.time import utc_now
from app.models.support import ReplyDraft, ReplyManualAction
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.support import ReplyOutput
from app.schemas.support_delivery import (
    ManualActionDetails,
    ManualActionOutput,
    RecordManualAction,
    ReviewReply,
    SupportDelivery,
)
from app.services.listings import digest
from app.services.manual_delivery import delivery_csv, delivery_text
from app.services.profit_calculation import utc_text
from app.services.support import SupportService, reply_output


def manual_output(item: ReplyManualAction) -> ManualActionOutput:
    return ManualActionOutput(
        id=item.id,
        draft_id=item.draft_id,
        draft_version=item.draft_version,
        occurred_at=utc_text(item.occurred_at),
        recorded_at=utc_text(item.recorded_at),
        details=ManualActionDetails.model_validate(item.payload) if item.payload else None,
    )


def require_review(item: ReplyDraft, version: int) -> None:
    if item.version != version or item.reviewed_version != item.version or not item.reviewed_at:
        raise ConflictError("请刷新并完成当前版本全文审阅后再操作")


class SupportDeliveryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow
        self.support = SupportService(uow)
        self.repo = uow.support

    def review(self, owner: int, shop: int, draft: int, data: ReviewReply) -> ReplyOutput:
        _, item, _ = self.support.delivery_context(owner, shop, draft)
        if not data.confirmed:
            raise BusinessError("review_required", "请核对全文、目标语言和接管原因后确认", 422)
        if (
            item.reviewed_version == item.version
            and item.reviewed_language == data.target_language
            and data.expected_version in {item.version, item.version - 1}
        ):
            result = reply_output(item)
            self.uow.commit()
            return result
        if data.expected_version != item.version:
            raise ConflictError("草稿已变化，请刷新后重新审阅")
        item.version += 1
        item.reviewed_version = item.version
        item.reviewed_language = data.target_language
        item.reviewed_at = item.updated_at = utc_now()
        self.uow.record_event(
            owner,
            "support.reply_reviewed",
            "reply_draft",
            item.id,
            {"version": item.version, "risk": "R1"},
        )
        self.uow.session.flush()
        result = reply_output(item)
        self.uow.commit()
        return result

    def delivery(self, owner: int, shop: int, draft: int, version: int) -> SupportDelivery:
        store, item, snapshot = self.support.delivery_context(owner, shop, draft)
        require_review(item, version)
        checked_at = utc_text(utc_now())
        source = snapshot.message.source
        orders = (
            "未核验关联；请在原渠道核实身份和订单"
            if not snapshot.order_verified
            else "\n".join(
                f"{o.order_id} / 行 {o.line_id} / SKU {o.sku} / 来源批次 {o.source.batch_id}"
                for o in snapshot.orders
            )
        )
        policies = []
        for policy in snapshot.policies:
            data = policy.data
            if data:
                policies.append(
                    f"{data.title} (#{policy.id} / v{policy.number})；{data.source} / "
                    f"{data.source_version}；{data.market}/{data.channel}/{data.language}；"
                    f"有效期 UTC {utc_text(data.valid_from)} 至 "
                    f"{utc_text(data.valid_until) if data.valid_until else '未设结束日期'}（不含）"
                )
        fields = [
            ("成果类型", "客服通用草稿 · 当前版本已审阅 · 平台未发送 / 外部未提交"),
            ("店铺", f"{store.name} (#{shop})"),
            ("市场", store.market),
            ("草稿版本", f"#{item.id} / v{item.version}"),
            ("原消息索引", f"{snapshot.message.message_id} (#{snapshot.message.id})"),
            ("来源渠道", snapshot.message.channel),
            ("数据身份", source.data_identity),
            ("消息来源", f"批次 {source.batch_id} / 行 {source.row_number} (#{source.row_id})"),
            ("来源导入时间 UTC", source.imported_at),
            ("来源导出时间 UTC", source.exported_at or "未提供"),
            ("订单关联", orders),
            ("适用政策与有效期", "\n".join(policies) or "未选用适用政策"),
            ("目标语言", item.reviewed_language or "待核对"),
            ("人工接管与不确定提示", "\n".join(snapshot.reasons) or "请在原渠道核对后使用"),
            ("审阅时间 UTC", utc_text(item.reviewed_at) if item.reviewed_at else "未审阅"),
            ("核对时间 UTC", checked_at),
            ("回复正文", snapshot.reply),
        ]
        result = SupportDelivery(
            draft_id=item.id,
            version=item.version,
            target_language=item.reviewed_language or "",
            checked_at=checked_at,
            plain_text=delivery_text(fields),
            csv_text=delivery_csv(fields),
            filename=f"reply-{item.id}-v{item.version}.csv",
        )
        self.uow.commit()
        return result

    def history(
        self, owner: int, shop: int, draft: int, before: int | None
    ) -> list[ManualActionOutput]:
        self.support._shop(owner, shop)
        self.support._draft(owner, shop, draft)
        result = [manual_output(i) for i in self.repo.manual_actions(owner, shop, draft, before)]
        self.uow.commit()
        return result

    def record(
        self, owner: int, shop: int, draft: int, data: RecordManualAction
    ) -> ManualActionOutput:
        # Validate scope before the idempotent read; completed retries remain readable after edits.
        self.support._shop(owner, shop)
        self.support._draft(owner, shop, draft)
        fingerprint = digest(data.model_dump(mode="json"))
        prior = self.repo.manual_request(owner, shop, draft, str(data.request_id))
        if prior:
            if prior.request_hash != fingerprint:
                raise ConflictError("该请求编号已用于其他内容，请刷新并核对原记录")
            result = manual_output(prior)
            self.uow.commit()
            return result
        _, item, _ = self.support.delivery_context(owner, shop, draft)
        require_review(item, data.expected_version)
        occurred = data.occurred_at.replace(tzinfo=None)
        if not data.confirmed or occurred > utc_now():
            raise BusinessError("evidence_required", "请确认人工自报，并填写已发生的操作时间", 422)
        details = ManualActionDetails(
            method=data.method, evidence_ref=data.evidence_ref, note=data.note
        )
        record = ReplyManualAction(
            owner_id=owner,
            shop_id=shop,
            draft_id=draft,
            draft_version=item.version,
            request_key=str(data.request_id),
            request_hash=fingerprint,
            occurred_at=occurred,
            payload=details.model_dump(mode="json"),
        )
        self.repo.add_manual_action(record)
        self.uow.record_event(
            owner,
            "support.manual_action_recorded",
            "reply_draft",
            draft,
            {"record_id": record.id, "version": item.version},
        )
        result = manual_output(record)
        self.uow.commit()
        return result
