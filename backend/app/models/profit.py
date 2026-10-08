from datetime import datetime
from decimal import Decimal

from sqlalchemy import ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class ProfitStudy(Base):
    __tablename__ = "profit_studies"
    __table_args__ = (UniqueConstraint("owner_id", "request_key", name="uq_profit_request"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    request_key: Mapped[str] = mapped_column(String(36))
    input_hash: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(120))
    currency: Mapped[str] = mapped_column(String(3))
    data_identity: Mapped[str] = mapped_column(String(24))
    rule_version: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(16), default="saved")
    created_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), default=utc_now)


class ProfitScenario(Base):
    __tablename__ = "profit_scenarios"
    __table_args__ = (UniqueConstraint("study_id", "position", name="uq_profit_position"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("profit_studies.id"))
    position: Mapped[int]
    name: Mapped[str] = mapped_column(String(80))
    price: Mapped[Decimal] = mapped_column(Numeric(13, 4))
    purchase_cost: Mapped[Decimal] = mapped_column(Numeric(13, 4))
    basis: Mapped[str] = mapped_column(String(500))


class ProfitFee(Base):
    __tablename__ = "profit_fees"
    scenario_id: Mapped[int] = mapped_column(ForeignKey("profit_scenarios.id"), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    mode: Mapped[str] = mapped_column(String(10))
    value: Mapped[Decimal | None] = mapped_column(Numeric(13, 4))
    basis: Mapped[str] = mapped_column(String(300))
