from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (UniqueConstraint("owner_id", "request_id", name="uq_agent_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    template: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="ready")
    reason: Mapped[str] = mapped_column(String(80), default="")
    version: Mapped[int] = mapped_column(default=1)
    next_node: Mapped[str] = mapped_column(String(32))
    source_status: Mapped[str] = mapped_column(String(16), default="current")
    source_revision: Mapped[int]
    input: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    result: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    steps_used: Mapped[int] = mapped_column(default=0)
    elapsed_ms: Mapped[int] = mapped_column(default=0)
    budget: Mapped[dict[str, Any]] = mapped_column(JSON)
    spent_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    reserved_usd: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal(0))
    model_status: Mapped[str] = mapped_column(String(24), default="not_used")
    lease_token: Mapped[str | None] = mapped_column(String(36))
    lease_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    valid_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id: Mapped[int] = mapped_column(primary_key=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id"), index=True)
    node: Mapped[str] = mapped_column(String(32))
    skill: Mapped[str] = mapped_column(String(40), default="")
    skill_version: Mapped[str] = mapped_column(String(16), default="1")
    status: Mapped[str] = mapped_column(String(24))
    reason: Mapped[str] = mapped_column(String(80), default="")
    next_node: Mapped[str] = mapped_column(String(32), default="")
    input: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    duration_ms: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class AgentSource(Base):
    __tablename__ = "agent_sources"
    execution_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), primary_key=True)


class AgentPolicySource(Base):
    __tablename__ = "agent_policy_sources"
    execution_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id"), primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("support_policies.id"), primary_key=True)
