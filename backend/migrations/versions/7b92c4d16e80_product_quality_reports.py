"""Persist product quality reports and their source dependencies.

Revision ID: 7b92c4d16e80
Revises: 54df8f2c09a1
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "7b92c4d16e80"
down_revision = "54df8f2c09a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_quality_reports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_quality_request"),
    )
    op.create_index("ix_product_quality_reports_owner_id", "product_quality_reports", ["owner_id"])
    op.create_index("ix_product_quality_reports_shop_id", "product_quality_reports", ["shop_id"])
    op.create_table(
        "product_quality_sources",
        sa.Column(
            "report_id", sa.Integer(), sa.ForeignKey("product_quality_reports.id"), primary_key=True
        ),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), primary_key=True),
    )
    op.create_index("ix_product_quality_sources_batch_id", "product_quality_sources", ["batch_id"])


def downgrade() -> None:
    op.drop_table("product_quality_sources")
    op.drop_table("product_quality_reports")
