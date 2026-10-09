from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class Settlement(Base):
    __tablename__ = "settlements"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "shop_id",
            "data_identity",
            "channel",
            "statement_key",
            name="uq_settlement_statement",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    data_identity: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(20))
    statement_key: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    version: Mapped[int] = mapped_column(default=1)
    content_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class SettlementRevision(Base):
    __tablename__ = "settlement_revisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_settlement_request"),
        UniqueConstraint("settlement_id", "version", name="uq_settlement_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("settlements.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int]
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class SettlementSource(Base):
    __tablename__ = "settlement_sources"
    settlement_id: Mapped[int] = mapped_column(ForeignKey("settlements.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id"), primary_key=True, index=True
    )


class SettlementReceipt(Base):
    __tablename__ = "settlement_receipts"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "shop_id",
            "data_identity",
            "channel",
            "receipt_key",
            name="uq_settlement_receipt",
        ),
        UniqueConstraint("revision_id", "position", name="uq_settlement_receipt_position"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    settlement_id: Mapped[int] = mapped_column(ForeignKey("settlements.id"), index=True)
    revision_id: Mapped[int] = mapped_column(ForeignKey("settlement_revisions.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    data_identity: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(20))
    receipt_key: Mapped[str | None] = mapped_column(String(64))
    position: Mapped[int]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    received_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
