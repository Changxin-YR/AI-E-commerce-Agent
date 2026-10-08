from datetime import datetime
from typing import Any

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    failed_login_count: Mapped[int] = mapped_column(default=0)
    locked_until: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class LoginSession(Base):
    __tablename__ = "login_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(index=True)


class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(80))
    target_market: Mapped[str] = mapped_column(String(2))
    business_model: Mapped[str] = mapped_column(String(80))
    category: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))
    language: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(default=1)
    updated_at: Mapped[datetime] = mapped_column(default=utc_now, onupdate=utc_now)


class Shop(Base):
    __tablename__ = "shops"
    __table_args__ = (UniqueConstraint("owner_id", "code", name="uq_shops_owner_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    platform: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3))
    timezone: Mapped[str] = mapped_column(String(64))
    data_revision: Mapped[int] = mapped_column(default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(default=utc_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
