from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class FeeRule(Base):
    __tablename__ = "fee_rules"
    __table_args__ = (
        UniqueConstraint(
            "shop_id", "data_identity", "channel", "match_key", name="uq_fee_rule_match"
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    data_identity: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(20))
    match_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    version: Mapped[int] = mapped_column(default=1)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class FeeRuleRevision(Base):
    __tablename__ = "fee_rule_revisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_fee_rule_request"),
        UniqueConstraint("rule_id", "version", name="uq_fee_rule_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    rule_id: Mapped[int] = mapped_column(ForeignKey("fee_rules.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int]
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    content: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
