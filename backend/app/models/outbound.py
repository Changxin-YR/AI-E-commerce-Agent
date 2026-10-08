from datetime import datetime

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class TestMailChannel(Base):
    __tablename__ = "test_mail_channels"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    config_hash: Mapped[str] = mapped_column(String(64))
    sender: Mapped[str] = mapped_column(String(254))
    recipient: Mapped[str] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(24), default="verifying")
    verification_hash: Mapped[str] = mapped_column(String(64))
    verification_attempts: Mapped[int] = mapped_column(default=0)
    verification_expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    verified_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    receipt_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class OutboundMessage(Base):
    __tablename__ = "outbound_messages"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_outbound_effect"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    channel_id: Mapped[int] = mapped_column(ForeignKey("test_mail_channels.id"))
    run_id: Mapped[int] = mapped_column(ForeignKey("operation_runs.id"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    dispatch_key: Mapped[str] = mapped_column(String(36), unique=True)
    subject: Mapped[str | None] = mapped_column(String(200))
    body: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    source_revision: Mapped[int]
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    status: Mapped[str] = mapped_column(String(24), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    dispatch_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    receipt_id: Mapped[str | None] = mapped_column(String(36))
    provider_event: Mapped[str] = mapped_column(String(32), default="")
    checked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    received_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    receipt_evidence: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class OutboundApproval(Base):
    __tablename__ = "outbound_approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("outbound_messages.id"), index=True)
    message_version: Mapped[int]
    content_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16))
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    used_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
