from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.models.base import Base


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    source_channel: Mapped[str] = mapped_column(String(20))
    data_identity: Mapped[str] = mapped_column(String(20))
    filename: Mapped[str] = mapped_column(String(240))
    sheet_name: Mapped[str] = mapped_column(String(120))
    file_sha256: Mapped[str] = mapped_column(String(64))
    timezone: Mapped[str] = mapped_column(String(64))
    exported_at: Mapped[datetime | None] = mapped_column(DATETIME(fsp=6))
    created_at: Mapped[datetime] = mapped_column(default=utc_now)
    expires_at: Mapped[datetime]
    committed_at: Mapped[datetime | None]
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(default=1)
    preview_revision: Mapped[int | None]
    applied_revision: Mapped[int | None]
    headers: Mapped[list[str]] = mapped_column(JSON)
    raw_data: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON(none_as_null=True))
    mapping: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    errors: Mapped[list[str]] = mapped_column(JSON, default=list)
    total_rows: Mapped[int]
    valid_rows: Mapped[int] = mapped_column(default=0)
    error_rows: Mapped[int] = mapped_column(default=0)
    new_rows: Mapped[int] = mapped_column(default=0)
    updated_rows: Mapped[int] = mapped_column(default=0)
    unchanged_rows: Mapped[int] = mapped_column(default=0)
    currencies: Mapped[list[str]] = mapped_column(JSON, default=list)
    coverage_start: Mapped[str | None] = mapped_column(String(40))
    coverage_end: Mapped[str | None] = mapped_column(String(40))


class ImportRow(Base):
    __tablename__ = "import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_import_rows_batch_row"),
        Index("ix_import_rows_key", "business_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    row_number: Mapped[int]
    business_key: Mapped[str | None] = mapped_column(String(64))
    raw: Mapped[dict[str, str]] = mapped_column(JSON)
    corrections: Mapped[dict[str, str]] = mapped_column(JSON)
    normalized: Mapped[dict[str, Any]] = mapped_column(JSON)
    previous: Mapped[dict[str, Any] | None] = mapped_column(JSON(none_as_null=True))
    errors: Mapped[list[dict[str, str]]] = mapped_column(JSON)
    warnings: Mapped[list[str]] = mapped_column(JSON)
    action: Mapped[str] = mapped_column(String(16))


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("shop_id", "sku", name="uq_products_shop_sku"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    sku: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    name: Mapped[str] = mapped_column(String(240))
    facts: Mapped[str] = mapped_column(Text)
    price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    currency: Mapped[str | None] = mapped_column(String(3))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    cost_currency: Mapped[str | None] = mapped_column(String(3))
    source_row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"))


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        UniqueConstraint("shop_id", "order_id", "line_id", name="uq_orders_shop_line"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    order_id: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    line_id: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    sku: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    quantity: Mapped[int]
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    currency: Mapped[str] = mapped_column(String(3))
    ordered_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6), index=True)
    status: Mapped[str] = mapped_column(String(24))
    discount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    refund: Mapped[Decimal | None] = mapped_column(Numeric(18, 4))
    fulfillment_status: Mapped[str] = mapped_column(String(20))
    source_row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"))


class MappingTemplate(Base):
    __tablename__ = "mapping_templates"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_mapping_owner_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(16))
    source_channel: Mapped[str] = mapped_column(String(20))
    mapping: Mapped[dict[str, str]] = mapped_column(JSON)


class CustomerMessage(Base):
    __tablename__ = "customer_messages"
    __table_args__ = (
        UniqueConstraint("shop_id", "channel", "message_id", name="uq_message_shop_channel_id"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    shop_id: Mapped[int] = mapped_column(ForeignKey("shops.id"), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    message_id: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    sent_at: Mapped[datetime] = mapped_column(DATETIME(fsp=6))
    body: Mapped[str] = mapped_column(Text)
    language: Mapped[str] = mapped_column(String(16))
    order_id: Mapped[str] = mapped_column(String(120, collation="utf8mb4_bin"))
    source_row_id: Mapped[int] = mapped_column(ForeignKey("import_rows.id"))
