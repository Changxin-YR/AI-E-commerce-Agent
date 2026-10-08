import hashlib
import secrets
from datetime import timedelta
from uuid import uuid4

from app.core.config import Settings
from app.core.errors import BusinessError, ConflictError, NotFoundError
from app.core.time import utc_now
from app.models.identity import Shop
from app.models.outbound import TestMailChannel
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.outbound import ChannelOutput
from app.services.outbound_provider import MailEnvelope, MailProvider, config_hash, configured
from app.services.profit_calculation import utc_text


class OutboundChannels:
    def __init__(self, uow: UnitOfWork, settings: Settings, provider: MailProvider) -> None:
        self.uow, self.repo, self.settings, self.provider = uow, uow.outbound, settings, provider

    def shop(self, owner: int, shop: int) -> Shop:
        self.uow.identity.lock_user(owner)
        item = self.uow.identity.get_shop(owner, shop, lock=True)
        if item is None:
            raise NotFoundError()
        return item

    def get(self, owner: int, shop: int, channel: int) -> TestMailChannel:
        item = self.repo.channel(owner, shop, channel)
        if item is None:
            raise NotFoundError()
        return item

    def status(self, item: TestMailChannel) -> str:
        if item.revoked_at:
            return "revoked"
        if not configured(self.settings, item.owner_id, item.shop_id):
            return "not_configured"
        if item.config_hash != config_hash(self.settings):
            return "configuration_changed"
        if not item.verified_at and item.verification_expires_at <= utc_now():
            return "expired"
        return item.status

    def output(self, owner: int, shop: int, item: TestMailChannel | None) -> ChannelOutput:
        ready = configured(self.settings, owner, shop)
        return ChannelOutput(
            configured=ready,
            id=item.id if item else None,
            status=self.status(item) if item else "disconnected" if ready else "not_configured",
            sender=item.sender if item else self.settings.outbound_sender if ready else "",
            recipient=item.recipient
            if item
            else self.settings.outbound_test_recipient
            if ready
            else "",
            receipt_id=item.receipt_id if item else None,
            verified_at=utc_text(item.verified_at) if item and item.verified_at else None,
            verification_expires_at=utc_text(item.verification_expires_at) if item else None,
        )

    def current(self, owner: int, shop: int) -> ChannelOutput:
        self.shop(owner, shop)
        rows = self.repo.channels(owner, shop)
        output = self.output(owner, shop, rows[0] if rows else None)
        self.uow.commit()
        return output

    def active(self, owner: int, shop: int) -> TestMailChannel:
        rows = self.repo.channels(owner, shop)
        if not rows or self.status(rows[0]) != "active":
            raise ConflictError("请先连接并验证本人测试邮箱")
        return rows[0]

    def connect(self, owner: int, shop: int) -> ChannelOutput:
        self.shop(owner, shop)
        if not configured(self.settings, owner, shop):
            raise ConflictError("外发未配置；需部署者配置当前账号/店铺的自有发送地址与测试邮箱")
        rows = self.repo.channels(owner, shop)
        now = utc_now()
        if rows and self.status(rows[0]) in {"active", "verifying", "unknown"}:
            return self._finish(owner, shop, rows[0])
        if rows and (now - rows[0].created_at).total_seconds() < 60:
            raise ConflictError("验证邮件间隔至少 60 秒")
        if sum(r.created_at > now - timedelta(days=1) for r in rows) >= 10:
            raise ConflictError("24 小时最多发起 10 次邮箱验证")
        code = f"{secrets.randbelow(100000000):08d}"
        item = TestMailChannel(
            owner_id=owner,
            shop_id=shop,
            config_hash=config_hash(self.settings),
            sender=self.settings.outbound_sender,
            recipient=self.settings.outbound_test_recipient,
            verification_hash=hashlib.sha256(code.encode()).hexdigest(),
            verification_expires_at=now + timedelta(minutes=15),
        )
        self.repo.add(item)
        channel_id = item.id
        envelope = MailEnvelope(
            item.sender,
            item.recipient,
            ChannelOutput.model_fields["verification_subject"].default,
            ChannelOutput.model_fields["verification_template"].default.replace(
                "{8 位随机码}", code
            ),
            str(uuid4()),
        )
        self.uow.record_event(
            owner, "outbound.verification_requested", "test_mail_channel", item.id
        )
        self.uow.commit()
        # No database lock during provider I/O. Consent reserves one verification attempt.
        if not self.provider.verify_domain():
            result_status, receipt = "domain_unverified", None
        else:
            result = self.provider.send(envelope)
            result_status = "verifying" if result.status == "accepted" else result.status
            receipt = result.receipt_id
        self.shop(owner, shop)
        item = self.get(owner, shop, channel_id)
        item.receipt_id = receipt
        if not item.revoked_at and not item.verified_at:
            item.status = result_status
        return self._finish(owner, shop, item)

    def _finish(self, owner: int, shop: int, item: TestMailChannel) -> ChannelOutput:
        output = self.output(owner, shop, item)
        self.uow.commit()
        return output

    def verify(self, owner: int, shop: int, channel: int, code: str) -> ChannelOutput:
        self.shop(owner, shop)
        item = self.get(owner, shop, channel)
        if self.status(item) == "active":
            return self._finish(owner, shop, item)
        if self.status(item) not in {"verifying", "unknown"} or item.verification_attempts >= 5:
            raise ConflictError("此验证已失效或尝试次数已用尽，请重新连接")
        item.verification_attempts += 1
        if not secrets.compare_digest(
            item.verification_hash, hashlib.sha256(code.encode()).hexdigest()
        ):
            if item.verification_attempts >= 5:
                item.status = "locked"
                item.verification_hash = ""
            self.uow.commit()
            raise BusinessError("invalid_verification", "验证码不正确；最多尝试 5 次", 422)
        item.status, item.verified_at, item.verification_hash = "active", utc_now(), ""
        self.uow.record_event(owner, "outbound.mailbox_verified", "test_mail_channel", item.id)
        return self._finish(owner, shop, item)

    def revoke(self, owner: int, shop: int, channel: int) -> ChannelOutput:
        self.shop(owner, shop)
        item = self.get(owner, shop, channel)
        if not item.revoked_at:
            item.revoked_at, item.verification_hash = utc_now(), ""
            self.uow.record_event(owner, "outbound.channel_revoked", "test_mail_channel", item.id)
        return self._finish(owner, shop, item)
