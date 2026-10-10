from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class SupportPolicy(Base):
    __tablename__ = "support_policies"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_key", name="uq_support_policy_request"),
        UniqueConstraint("shop_id", "policy_key", "number", name="uq_support_policy_number"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    policy_key: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(64))
    number: Mapped[int]
    status: Mapped[str] = mapped_column(String(16), default="active")
    valid_from: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ReplyDraft(Base):
    __tablename__ = "reply_drafts"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_reply_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    reviewed_version: Mapped[int | None]
    reviewed_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    reviewed_language: Mapped[str | None] = mapped_column(String(10))
    message_key: Mapped[str] = mapped_column(String(64))
    source_row_id: Mapped[int | None] = mapped_column(ForeignKey("import_rows.id"))
    request_key: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(20))
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    engine: Mapped[str] = mapped_column(String(24), default="local_rules")
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ReplyManualAction(Base):
    __tablename__ = "reply_manual_actions"
    __table_args__ = (UniqueConstraint("draft_id", "request_key", name="uq_reply_manual_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    draft_id: Mapped[int] = mapped_column(ForeignKey("reply_drafts.id"), index=True)
    draft_version: Mapped[int]
    request_key: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    recorded_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))


class ReplySource(Base):
    __tablename__ = "reply_sources"
    draft_id: Mapped[int] = mapped_column(ForeignKey("reply_drafts.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), primary_key=True)


class ReplyPolicy(Base):
    __tablename__ = "reply_policies"
    draft_id: Mapped[int] = mapped_column(ForeignKey("reply_drafts.id"), primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("support_policies.id"), primary_key=True)
