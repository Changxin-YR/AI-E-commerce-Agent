from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class ProductQualityReport(Base):
    __tablename__ = "product_quality_reports"
    __table_args__ = (UniqueConstraint("owner_id", "request_id", name="uq_quality_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="current")
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ProductQualitySource(Base):
    __tablename__ = "product_quality_sources"
    report_id: Mapped[int] = mapped_column(
        ForeignKey("product_quality_reports.id"), primary_key=True
    )
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id"), primary_key=True, index=True
    )
