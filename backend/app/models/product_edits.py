from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class ProductEdit(Base):
    __tablename__ = "product_edits"
    __table_args__ = (UniqueConstraint("owner_id", "request_id", name="uq_product_edit_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    output_batch_id: Mapped[int | None] = mapped_column(ForeignKey("import_batches.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    decided_at: Mapped[datetime | None]


class ProductEditSource(Base):
    __tablename__ = "product_edit_sources"
    edit_id: Mapped[int] = mapped_column(ForeignKey("product_edits.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id"), primary_key=True, index=True
    )
