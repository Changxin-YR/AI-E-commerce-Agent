from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class InternalAuthorization(Base):
    __tablename__ = "internal_authorizations"
    __table_args__ = (UniqueConstraint("owner_id", "request_id", name="uq_authorization_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    # Provenance only; scoped service validation avoids a cyclic FK with agent_executions.
    origin_execution_id: Mapped[int]
    skill: Mapped[str] = mapped_column(String(40), default="propose_tasks")
    scope: Mapped[dict[str, Any]] = mapped_column(JSON)
    source_revision: Mapped[int]
    content_hash: Mapped[str] = mapped_column(String(64))
    candidate_count: Mapped[int]
    max_uses: Mapped[int]
    used_count: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    expires_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    source_valid_until: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    revoked_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class AuthorizationUse(Base):
    __tablename__ = "authorization_uses"
    __table_args__ = (UniqueConstraint("execution_id", name="uq_authorization_execution"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    authorization_id: Mapped[int] = mapped_column(
        ForeignKey("internal_authorizations.id"), index=True
    )
    execution_id: Mapped[int] = mapped_column(ForeignKey("agent_executions.id"))
    operation_run_id: Mapped[int] = mapped_column(ForeignKey("operation_runs.id"))
    # IDs, status and versions only. Business text stays in the erasable source-derived records.
    changes: Mapped[list[dict[str, Any]]] = mapped_column(JSON)
    reused_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)
    reverted_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
