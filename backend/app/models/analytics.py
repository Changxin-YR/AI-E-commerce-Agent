from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class SavedAnalysis(Base):
    __tablename__ = "saved_analyses"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_analysis_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(64))
    source_revision: Mapped[int]
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    status: Mapped[str] = mapped_column(String(16), default="current")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class AnalysisSource(Base):
    __tablename__ = "analysis_sources"
    analysis_id: Mapped[int] = mapped_column(ForeignKey("saved_analyses.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), primary_key=True)


class AnalysisTodo(Base):
    __tablename__ = "analysis_todos"
    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("saved_analyses.id"), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(16), default="open")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
