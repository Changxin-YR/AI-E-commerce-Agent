from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class OrderCostRevision(Base):
    __tablename__ = "order_cost_revisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_order_cost_request"),
        UniqueConstraint("shop_id", "source_key", "version", name="uq_order_cost_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    source_key: Mapped[str] = mapped_column(String(64), index=True)
    source_row_id: Mapped[int | None] = mapped_column(ForeignKey("import_rows.id"), index=True)
    source_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    version: Mapped[int]
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    evidence_ref: Mapped[str | None] = mapped_column(String(500))
    evidence_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
