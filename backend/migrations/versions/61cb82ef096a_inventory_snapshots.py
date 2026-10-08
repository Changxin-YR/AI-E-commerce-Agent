"""Add channel scoped inventory snapshots.

Revision ID: 61cb82ef096a
Revises: 8d34d9c410a2
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "61cb82ef096a"
down_revision = "8d34d9c410a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("shop_id", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("sku", sa.String(120, collation="utf8mb4_bin"), nullable=False),
        sa.Column("available", sa.Integer(), nullable=False),
        sa.Column("snapshot_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.Column("safety_threshold", sa.Integer(), nullable=False),
        sa.Column("source_row_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["shop_id"], ["shops.id"]),
        sa.ForeignKeyConstraint(["source_row_id"], ["import_rows.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shop_id", "channel", "sku", name="uq_inventory_shop_channel_sku"),
    )
    op.create_index("ix_inventory_snapshots_shop_id", "inventory_snapshots", ["shop_id"])


def downgrade() -> None:
    op.drop_table("inventory_snapshots")
