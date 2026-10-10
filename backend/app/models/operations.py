from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class OperationRun(Base):
    __tablename__ = "operation_runs"
    __table_args__ = (UniqueConstraint("owner_id", "request_id", name="uq_operation_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_revision: Mapped[int]
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class OperationRunSource(Base):
    __tablename__ = "operation_run_sources"
    run_id: Mapped[int] = mapped_column(ForeignKey("operation_runs.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), primary_key=True)


class OperationTask(Base):
    __tablename__ = "operation_tasks"
    __table_args__ = (UniqueConstraint("owner_id", "dedupe_key", name="uq_operation_task"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    dedupe_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    data_identity: Mapped[str] = mapped_column(String(20))
    channel: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(24), default="pending_approval")
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    version: Mapped[int] = mapped_column(default=1)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    review: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    note: Mapped[str] = mapped_column(Text, default="")
    due_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class OperationTaskSource(Base):
    __tablename__ = "operation_task_sources"
    task_id: Mapped[int] = mapped_column(ForeignKey("operation_tasks.id"), primary_key=True)
    row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)


class OperationTaskEvent(Base):
    __tablename__ = "operation_task_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("operation_tasks.id"), index=True)
    action: Mapped[str] = mapped_column(String(24))
    from_status: Mapped[str] = mapped_column(String(24))
    to_status: Mapped[str] = mapped_column(String(24))
    version: Mapped[int]
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
