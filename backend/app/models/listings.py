from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class ListingVersion(Base):
    __tablename__ = "listing_versions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_key", name="uq_listing_request"),
        UniqueConstraint("shop_id", "product_key", "number", name="uq_listing_number"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    product_key: Mapped[str] = mapped_column(String(64))
    request_key: Mapped[str] = mapped_column(String(64))
    number: Mapped[int]
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    source_row_id: Mapped[int | None] = mapped_column(ForeignKey("import_rows.id"))
    # Historical comparison identifier, never followed without owner/shop validation.
    base_version_id: Mapped[int | None]
    engine: Mapped[str] = mapped_column(String(24))
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))


class ListingSource(Base):
    __tablename__ = "listing_sources"
    listing_id: Mapped[int] = mapped_column(ForeignKey("listing_versions.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), primary_key=True)
