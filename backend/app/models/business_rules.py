from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class BusinessRuleRevision(Base):
    __tablename__ = "business_rule_revisions"
    __table_args__ = (
        Index("ix_rule_scope", "owner_id", "shop_id", "channel", "data_identity", "id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    data_identity: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(16))
    previous_id: Mapped[int]
    restored_from_id: Mapped[int | None]
    max_age_hours: Mapped[int]
    min_quantity: Mapped[int]
    max_margin_percent: Mapped[Decimal] = mapped_column(Numeric(7, 2))
    advertising_daily_budget: Mapped[Decimal | None] = mapped_column(Numeric(13, 4))
    currency: Mapped[str] = mapped_column(String(3))
    notes: Mapped[dict[str, Any]] = mapped_column(JSON)
    basis: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
