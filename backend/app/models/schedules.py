from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class OperationSchedule(Base):
    __tablename__ = "operation_schedules"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_schedule_request"),
        Index("ix_schedule_due", "status", "next_run_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active")
    version: Mapped[int] = mapped_column(default=1)
    config: Mapped[dict[str, Any]] = mapped_column(JSON)
    next_run_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ScheduleOccurrence(Base):
    __tablename__ = "schedule_occurrences"
    __table_args__ = (UniqueConstraint("schedule_id", "slot_key", name="uq_schedule_slot"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("operation_schedules.id"), index=True)
    schedule_version: Mapped[int]
    slot_key: Mapped[str] = mapped_column(String(64))
    trigger: Mapped[str] = mapped_column(String(16))
    scheduled_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    coalesced_from: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    execution_id: Mapped[int | None] = mapped_column(ForeignKey("agent_executions.id"))
    status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(64), default="")
    notify_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    read_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
