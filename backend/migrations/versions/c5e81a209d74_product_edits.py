"""Persist product edits and their complete source ancestry.

Revision ID: c5e81a209d74
Revises: 7b92c4d16e80
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "c5e81a209d74"
down_revision = "7b92c4d16e80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_edits",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column(
            "output_batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=True
        ),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("decided_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_product_edit_request"),
    )
    for column in ("owner_id", "shop_id", "output_batch_id"):
        op.create_index(f"ix_product_edits_{column}", "product_edits", [column])
    op.create_table(
        "product_edit_sources",
        sa.Column("edit_id", sa.Integer(), sa.ForeignKey("product_edits.id"), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), primary_key=True),
    )
    op.create_index("ix_product_edit_sources_batch_id", "product_edit_sources", ["batch_id"])


def downgrade() -> None:
    op.drop_table("product_edit_sources")
    op.drop_table("product_edits")
