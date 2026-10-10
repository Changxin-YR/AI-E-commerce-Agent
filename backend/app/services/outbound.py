from datetime import UTC, timedelta
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.outbound import OutboundApproval, OutboundMessage
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.outbound import (
    ApprovalOutput,
    ApproveMail,
    EditMail,
    MailOutput,
    MailPage,
    SendMail,
)
from app.services.listings import digest
from app.services.operations import OperationsService
from app.services.outbound_channels import OutboundChannels
from app.services.outbound_provider import MailEnvelope, MailProvider, MailResult
from app.services.profit_calculation import utc_text
from app.services.qq_mail_provider import smtp_message_id


class OutboundService:
    def __init__(self, uow: UnitOfWork, settings: Settings, provider: MailProvider) -> None:
        self.uow, self.repo, self.provider = uow, uow.outbound, provider
        self.channels = OutboundChannels(uow, settings, provider)

    def _get(self, owner: int, shop: int, message: int) -> OutboundMessage:
        self.channels.shop(owner, shop)
        item = self.repo.message(owner, shop, message)
        if item is None:
            raise NotFoundError()
        if (
            item.status == "sending"
            and item.dispatch_at
            and item.dispatch_at <= utc_now() - timedelta(seconds=60)
        ):
            item.status = "unknown"
            item.version += 1
        self._source(item)
        return item

    def _source(self, item: OutboundMessage) -> bool:
        if item.source_status != "current":
            return False
        with self.uow.defer_commits():
            run = OperationsService(self.uow).get_run(item.owner_id, item.shop_id, item.run_id)
        shop = self.uow.identity.get_shop(item.owner_id, item.shop_id, lock=True)
        if not run.snapshot:
            item.subject = item.body = item.receipt_evidence = None
            item.source_status = "cleared"
        elif (
            run.source_status != "current"
            or shop is None
            or shop.data_revision != item.source_revision
        ):
            item.source_status = "stale"
        if item.source_status != "current":
            item.version += 1
            return False
        return True

    def _envelope(self, item: OutboundMessage) -> MailEnvelope:
        channel = self.channels.get(item.owner_id, item.shop_id, item.channel_id)
        if item.subject is None or item.body is None:
            raise ConflictError("正文已清除，无法按全文核对或发送")
        return MailEnvelope(
            channel.sender,
            item.recipient or channel.recipient,
            item.subject,
            item.body,
            item.dispatch_key,
        )

    def _approval_status(self, grant: OutboundApproval, item: OutboundMessage) -> str:
        if grant.used_at:
            return "used"
        if grant.revoked_at:
            return "revoked"
        if grant.expires_at <= utc_now():
            return "expired"
        if (
            grant.message_version != item.version
            or grant.content_hash != item.content_hash
            or item.source_status != "current"
            or item.status != "draft"
        ):
            return "invalidated"
        channel = self.channels.get(item.owner_id, item.shop_id, item.channel_id)
        return "active" if self.channels.status(channel) == "active" else "channel_unavailable"

    def _output(self, item: OutboundMessage) -> MailOutput:
        channel = self.channels.get(item.owner_id, item.shop_id, item.channel_id)
        return MailOutput(
            id=item.id,
            shop_id=item.shop_id,
            channel_id=item.channel_id,
            provider=channel.provider,
            smtp_message_id=smtp_message_id(item.dispatch_key)
            if channel.provider == "qq_smtp" and item.dispatch_at
            else None,
            run_id=item.run_id,
            sender=channel.sender,
            recipient=item.recipient or channel.recipient,
            subject=item.subject,
            body=item.body,
            content_hash=item.content_hash,
            status=item.status,
            source_status=item.source_status,
            channel_status=self.channels.status(channel),
            version=item.version,
            dispatch_at=utc_text(item.dispatch_at) if item.dispatch_at else None,
            receipt_id=item.receipt_id,
            provider_event=item.provider_event,
            checked_at=utc_text(item.checked_at) if item.checked_at else None,
            received_at=utc_text(item.received_at) if item.received_at else None,
            receipt_evidence=item.receipt_evidence,
            created_at=utc_text(item.created_at),
            approvals=[
                ApprovalOutput(
                    id=g.id,
                    mode=g.mode,
                    status=self._approval_status(g, item),
                    used_count=int(g.used_at is not None),
                    expires_at=utc_text(g.expires_at),
                    created_at=utc_text(g.created_at),
                )
                for g in self.repo.approvals(item.owner_id, item.shop_id, item.id)
            ],
        )

    def _finish(self, item: OutboundMessage) -> MailOutput:
        self.uow.session.flush()
        output = self._output(item)
        self.uow.commit()
        return output

    def create(
        self, owner: int, shop: int, run_id: int, recipient: str | None = None
    ) -> MailOutput:
        self.channels.shop(owner, shop)
        channel = self.channels.active(owner, shop)
        recipient = recipient or channel.recipient
        if channel.provider != "qq_smtp" and recipient != channel.recipient:
            raise ConflictError("此通道仅支持已验证的本人测试收件人")
        # Approval, content edits and credential rotation cannot create a second effect.
        key = digest([owner, shop, run_id, channel.sender, recipient, "daily-summary-v1"])
        prior = self.repo.by_key(owner, key)
        if prior:
            self._source(prior)
            return self._finish(prior)
        with self.uow.defer_commits():
            run = OperationsService(self.uow).get_run(owner, shop, run_id)
        current_shop = self.uow.identity.get_shop(owner, shop, lock=True)
        if (
            not run.snapshot
            or run.source_status != "current"
            or current_shop is None
            or run.source_revision != current_shop.data_revision
        ):
            raise ConflictError("请先运行并保存当前来源的今日运营检查")
        scope, snapshot = run.scope, run.snapshot
        title = f"SoloOps 测试经营摘要 · 检查 #{run.id}"
        body = "\n".join(
            [
                "这是一份发往本人测试邮箱的经营检查摘要。"
                if recipient == channel.recipient
                else "这是一份经营检查摘要。",
                f"店铺 #{shop}；检查 #{run.id}；数据身份 {scope.data_identity}；"
                f"渠道 {scope.channel}",
                f"UTC 窗口 [{scope.start_at.astimezone(UTC).isoformat()}, "
                f"{scope.end_at.astimezone(UTC).isoformat()})；"
                f"币种 {scope.currency}",
                f"规则版本 #{scope.rule_revision_id}；数据截至 {snapshot.data_as_of}",
                *[
                    f"{b.name}：{b.status}；检查记录数 {b.count}；{b.reason}"
                    for b in snapshot.branches
                ],
                f"本次新增候选 {snapshot.created_candidates}；复用 {snapshot.reused_candidates}。",
                "关联候选（最多展示前 50 项）："
                + (", ".join(f"#{t}" for t in snapshot.task_ids[:50]) or "无"),
                "以上为保存时的本地规则结果。待办的当前处理状态请在工作台核对。",
            ]
        )
        envelope = MailEnvelope(channel.sender, recipient, title, body, str(uuid4()))
        item = OutboundMessage(
            owner_id=owner,
            shop_id=shop,
            channel_id=channel.id,
            recipient=recipient,
            run_id=run_id,
            dedupe_key=key,
            dispatch_key=envelope.key,
            subject=title,
            body=body,
            content_hash=envelope.content_hash,
            source_revision=run.source_revision,
        )
        self.repo.add(item)
        self.uow.record_event(
            owner, "outbound.preview_created", "outbound_message", item.id, {"run_id": run_id}
        )
        return self._finish(item)

    def get(self, owner: int, shop: int, message: int) -> MailOutput:
        return self._finish(self._get(owner, shop, message))

    def list(self, owner: int, shop: int, before: int | None) -> MailPage:
        self.channels.shop(owner, shop)
        rows = self.repo.messages(owner, shop, before)
        for item in rows[:50]:
            self._get(owner, shop, item.id)
        output = MailPage(
            items=[self._output(r) for r in rows[:50]],
            next_before_id=rows[49].id if len(rows) > 50 else None,
        )
        self.uow.commit()
        return output

    def _editable(self, item: OutboundMessage, version: int) -> None:
        if item.version != version or item.status != "draft" or item.dispatch_at:
            raise ConflictError("记录已变化或已提交，请刷新；每份摘要最多提交一次")
        if item.source_status != "current":
            raise ConflictError("来源已变化或清除，请重新检查")

    def edit(self, owner: int, shop: int, message: int, data: EditMail) -> MailOutput:
        item = self._get(owner, shop, message)
        self._editable(item, data.version)
        item.subject, item.body = data.subject, data.body
        item.content_hash = self._envelope(item).content_hash
        item.version += 1
        self.uow.record_event(owner, "outbound.preview_edited", "outbound_message", item.id)
        return self._finish(item)

    def approve(self, owner: int, shop: int, message: int, data: ApproveMail) -> MailOutput:
        item = self._get(owner, shop, message)
        self._editable(item, data.version)
        channel = self.channels.get(owner, shop, item.channel_id)
        if self.channels.status(channel) != "active":
            raise ConflictError("发送通道不可用，请重新验证邮箱")
        existing = self.repo.approvals(owner, shop, message)
        if len(existing) >= 100:
            raise ConflictError("此预览的审批历史已达上限，请重新运行检查")
        for grant in existing:
            if self._approval_status(grant, item) == "active":
                grant.revoked_at = utc_now()
        grant = OutboundApproval(
            owner_id=owner,
            shop_id=shop,
            message_id=message,
            message_version=item.version,
            content_hash=item.content_hash,
            mode=data.mode,
            expires_at=utc_now()
            + (timedelta(minutes=10) if data.mode == "once" else timedelta(hours=data.valid_hours)),
        )
        self.repo.add(grant)
        self.uow.record_event(
            owner,
            "outbound.approved",
            "outbound_message",
            item.id,
            {"approval_id": grant.id, "mode": data.mode, "max_submissions": 1},
        )
        return self._finish(item)

    def revoke(self, owner: int, shop: int, message: int, approval: int) -> MailOutput:
        item = self._get(owner, shop, message)
        grant = next(
            (g for g in self.repo.approvals(owner, shop, message) if g.id == approval), None
        )
        if grant is None:
            raise NotFoundError()
        if not grant.revoked_at:
            grant.revoked_at = utc_now()
            self.uow.record_event(
                owner,
                "outbound.approval_revoked",
                "outbound_message",
                item.id,
                {"approval_id": grant.id},
            )
        return self._finish(item)

    def reject(self, owner: int, shop: int, message: int, version: int) -> MailOutput:
        item = self._get(owner, shop, message)
        if item.status == "cancelled":
            return self._finish(item)
        self._editable(item, version)
        item.status, item.version = "cancelled", item.version + 1
        self.uow.record_event(owner, "outbound.cancelled", "outbound_message", item.id)
        return self._finish(item)

    def _grant(self, item: OutboundMessage, data: SendMail) -> OutboundApproval:
        self._editable(item, data.version)
        grant = next(
            (
                g
                for g in self.repo.approvals(item.owner_id, item.shop_id, item.id)
                if g.id == data.approval_id
            ),
            None,
        )
        if grant is None or self._approval_status(grant, item) != "active":
            raise ConflictError("R2 审批不存在、已撤销或已失效，请重新审阅全文")
        if self._envelope(item).content_hash != grant.content_hash:
            raise ConflictError("正文与审批不一致")
        return grant

    def send(self, owner: int, shop: int, message: int, data: SendMail) -> MailOutput:
        item = self._get(owner, shop, message)
        if item.dispatch_at:
            return self._finish(item)
        self._grant(item, data)
        self.uow.commit()
        sender_verified = self.provider.verify_sender()
        item = self._get(owner, shop, message)
        if item.dispatch_at:
            return self._finish(item)
        grant = self._grant(item, data)
        if not sender_verified:
            raise ConflictError("发送账号验证未通过或暂不可核对，请检查通道配置与凭据")
        now = utc_now()
        recent = self.repo.recent_dispatches(owner, now - timedelta(days=1))
        if len(recent) >= 10 or any(t > now - timedelta(seconds=60) for t in recent):
            raise ConflictError("测试外发间隔至少 60 秒，每账号 24 小时最多 10 次提交")
        envelope = self._envelope(item)
        item.status, item.dispatch_at, item.version = "sending", now, item.version + 1
        grant.used_at = now
        self.uow.record_event(
            owner,
            "outbound.dispatch_claimed",
            "outbound_message",
            item.id,
            {"approval_id": grant.id, "max_submissions": 1},
        )
        # Durable consent consumption: a timeout or crash cannot permit another submission.
        self.uow.commit()
        result = self.provider.send(envelope)
        item = self._get(owner, shop, message)
        self._record_result(item, result)
        return self._finish(item)

    def _record_result(self, item: OutboundMessage, result: MailResult) -> None:
        # A late unknown response cannot downgrade a successful read-only reconciliation.
        if item.status != "accepted" or result.status == "accepted":
            item.status = result.status
            item.receipt_id = result.receipt_id or item.receipt_id
            item.provider_event = result.event or item.provider_event
        item.version += 1
        self.uow.record_event(
            item.owner_id,
            "outbound.result_recorded",
            "outbound_message",
            item.id,
            {"status": item.status, "provider_event": item.provider_event},
        )

    def reconcile(self, owner: int, shop: int, message: int, receipt: str | None) -> MailOutput:
        item = self._get(owner, shop, message)
        if not item.dispatch_at or item.status == "sending":
            raise ConflictError("尚未提交或仍在提交中，请稍后只读回查")
        channel = self.channels.get(owner, shop, item.channel_id)
        if channel.provider == "qq_smtp":
            raise ConflictError(
                "QQ SMTP 无回执查询接口，请核对收件箱并记录实际收件证据；勿重复发送"
            )
        # Read-back can continue after consent revocation, with the same configured credentials.
        from app.services.outbound_provider import config_hash, configured

        if not configured(
            self.channels.settings, owner, shop
        ) or channel.config_hash != config_hash(self.channels.settings):
            raise ConflictError("原通道凭据已变化，须到原通道人工核对")
        if item.checked_at and item.checked_at > utc_now() - timedelta(seconds=10):
            raise ConflictError("回查间隔至少 10 秒")
        envelope = self._envelope(item)
        receipt = item.receipt_id or receipt
        item.checked_at = utc_now()
        self.uow.commit()
        result = self.provider.reconcile(envelope, receipt)
        item = self._get(owner, shop, message)
        if result.status == "accepted":
            self._record_result(item, result)
        self.uow.record_event(
            owner,
            "outbound.reconciled",
            "outbound_message",
            item.id,
            {"matched": result.status == "accepted"},
        )
        return self._finish(item)

    def receipt(self, owner: int, shop: int, message: int, evidence: str) -> MailOutput:
        item = self._get(owner, shop, message)
        channel = self.channels.get(owner, shop, item.channel_id)
        accepted = item.status == "accepted" and bool(item.receipt_id)
        smtp_unknown = (
            channel.provider == "qq_smtp" and item.status == "unknown" and bool(item.dispatch_at)
        )
        if not (accepted or smtp_unknown) or item.source_status == "cleared":
            raise ConflictError("须先提交邮件并取得可核对的记录，正文清除后不可追加收件证据")
        # A manual receipt statement never manufactures a provider response.
        item.received_at, item.receipt_evidence = utc_now(), evidence
        self.uow.record_event(owner, "outbound.receipt_attested", "outbound_message", item.id)
        return self._finish(item)
