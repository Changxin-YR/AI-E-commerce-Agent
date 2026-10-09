from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class Expense(Base):
    __tablename__ = "expenses"
    __table_args__ = (
        UniqueConstraint(
            "owner_id",
            "shop_id",
            "data_identity",
            "channel",
            "evidence_key",
            name="uq_expense_evidence",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    data_identity: Mapped[str] = mapped_column(String(16))
    channel: Mapped[str] = mapped_column(String(20))
    evidence_key: Mapped[str | None] = mapped_column(String(64))
    allocation: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), default="active")
    version: Mapped[int] = mapped_column(default=1)
    content_version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ExpenseRevision(Base):
    __tablename__ = "expense_revisions"
    __table_args__ = (
        UniqueConstraint("owner_id", "request_id", name="uq_expense_request"),
        UniqueConstraint("expense_id", "version", name="uq_expense_version"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), index=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    version: Mapped[int]
    request_id: Mapped[str] = mapped_column(String(36))
    request_hash: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(16))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    occurred_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6), index=True)
    snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ExpenseSource(Base):
    __tablename__ = "expense_sources"
    expense_id: Mapped[int] = mapped_column(ForeignKey("expenses.id"), primary_key=True)
    batch_id: Mapped[int] = mapped_column(
        ForeignKey("import_batches.id"), primary_key=True, index=True
    )
