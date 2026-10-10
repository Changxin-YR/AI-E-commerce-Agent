"""Seller-confirmed historical order-line unit costs.

Revision ID: b37e820ca491
Revises: a12c4b907e61
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

revision = "b37e820ca491"
down_revision = "a12c4b907e61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_cost_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("shop_id", sa.Integer(), sa.ForeignKey("shops.id"), nullable=False),
        sa.Column("source_key", sa.String(64), nullable=False),
        sa.Column("source_row_id", sa.Integer(), sa.ForeignKey("import_rows.id"), nullable=True),
        sa.Column(
            "source_batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("action", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=True),
        sa.Column("evidence_ref", sa.String(500), nullable=True),
        sa.Column("evidence_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column("created_at", mysql.DATETIME(fsp=6), nullable=False),
        sa.UniqueConstraint("owner_id", "request_id", name="uq_order_cost_request"),
        sa.UniqueConstraint("shop_id", "source_key", "version", name="uq_order_cost_version"),
    )
    for field in ("owner_id", "shop_id", "source_key", "source_row_id", "source_batch_id"):
        op.create_index(f"ix_order_cost_revisions_{field}", "order_cost_revisions", [field])


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM order_cost_revisions")):
        raise RuntimeError("存在成本凭据历史；请备份并保留当前结构，不能通过降级删除凭据版本")
    op.drop_table("order_cost_revisions")
